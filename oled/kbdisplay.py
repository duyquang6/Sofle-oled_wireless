#!/usr/bin/env python3
"""Feeds the Sofle left OLED (zmk-nice-oled Raw HID widgets) from this PC.

- time (hour, minute), refreshed every 30 s so the keyboard keeps the HID area on
- EN/VI from fcitx5 (layout index into CONFIG_NICE_OLED_WIDGET_RAW_HID_LAYOUT_LIST="EN,VI")
- one text slot (5 chars fit the 32 px column) cycling Genshin pages from genshin-redeem /api/status
SIGUSR1 jumps to the next page (niri binds F13, sent by NAV + left encoder press).
Stdlib only; writes to every Sofle hidraw node with the 0xFF60 usage page (USB and BT).
"""
import glob, json, math, os, signal, subprocess, time, urllib.request

STATUS_URL = os.environ.get("KBD_STATUS_URL", "http://192.168.1.203:8788/api/status")
PAGE_SECONDS = 6
STATUS_EVERY = 300
RESIN_EVERY = 8 * 60

T_TIME, T_LAYOUT, T_TEXT = 0xAA, 0xAC, 0xAE
REPORT = 32

def devices():
    out = []
    for d in glob.glob("/sys/class/hidraw/hidraw*"):
        try:
            ev = open(f"{d}/device/uevent").read().upper()
            desc = open(f"{d}/device/report_descriptor", "rb").read(3)
        except OSError:
            continue
        if ":00001D50:0000615E" in ev and desc == b"\x06\x60\xff":
            out.append("/dev/" + os.path.basename(d))
    return out

def send(payload):
    pkt = b"\x00" + bytes(payload).ljust(REPORT, b"\x00")[:REPORT]
    for dev in devices():
        try:
            fd = os.open(dev, os.O_WRONLY | os.O_NONBLOCK)
            try:
                os.write(fd, pkt)
            finally:
                os.close(fd)
        except OSError:
            pass

def fcitx_vi():
    try:
        r = subprocess.run(["fcitx5-remote"], capture_output=True, text=True, timeout=1)
        return r.stdout.strip() == "2"
    except Exception:
        return False

def fetch_status():
    with urllib.request.urlopen(STATUS_URL, timeout=10) as r:
        return json.load(r)

def until(ts, now):
    left = max(0, ts - now)
    h, m = divmod(left // 60, 60)
    return f"{h}h" if h else f"{m}m"

def pages(s, now):
    if not s:
        return ["no data"]
    full_at = s.get("resin_full_at", 0)
    mx = s.get("max_resin", 200)
    resin = mx if not full_at or full_at <= now else mx - math.ceil((full_at - now) / RESIN_EVERY)
    out = [f"R{resin}"]
    if s.get("expeditions"):
        done = s["expeditions"] if s.get("expeditions_back_at", 0) <= now else s.get("expeditions_done", 0)
        out.append(f"Ex{done}/{s['expeditions']}")
    if s.get("commissions_total"):
        out.append(f"Dl{s['commissions']}/{s['commissions_total']}")
    if s.get("max_realm"):
        out.append(f"Po{s['realm'] * 100 // s['max_realm']}%")
    if "pity" in s:
        out.append(f"Pi{s['pity']}")
    return out

class State:
    page = 0
    jump = False

def on_usr1(*_):
    State.page += 1
    State.jump = True

def main():
    signal.signal(signal.SIGUSR1, on_usr1)
    status, status_at = None, 0.0
    last_vi = None
    last_time = last_page = 0.0
    last_min = -1
    while True:
        now = time.time()
        if now - status_at > STATUS_EVERY:
            try:
                status = fetch_status()
            except Exception:
                pass
            status_at = now
        vi = fcitx_vi()
        lt = time.localtime(now)
        tick = now - last_time > 30 or lt.tm_min != last_min
        if vi != last_vi or tick:
            send([T_LAYOUT, 1 if vi else 0])
            last_vi = vi
        if tick:
            send([T_TIME, lt.tm_hour, lt.tm_min])
            last_time, last_min = now, lt.tm_min
        if State.jump or now - last_page > PAGE_SECONDS:
            if not State.jump:
                State.page += 1
            State.jump = False
            ps = pages(status, int(now))
            text = ps[State.page % len(ps)].encode("ascii", "replace")[:10]
            send([T_TEXT, *text])
            last_page = now
        time.sleep(0.3)

if __name__ == "__main__":
    main()
