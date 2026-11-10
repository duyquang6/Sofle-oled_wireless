#!/usr/bin/env python3
"""Feeds the Sofle left OLED (zmk-nice-oled Raw HID widgets) from this PC.

- time (hour, minute) and EN/VI from fcitx5 (layout index into "EN,VI")
- a 3-line info block in the text slot (23 chars, patched module; the 32 px column
  wraps at spaces, 5 chars per line), one of three modes:
    Genshin  R129  Ex0/5  Po71%    resin, expeditions, teapot coins (genshin-redeem)
    market   U25.8 Au142  S+2.4    USDT buy (k VND), DOJI SJC sell (M VND), SPY today
    PC       C56   G48    M41%     CPU temp, GPU temp, RAM used
SIGUSR1 switches mode (niri binds F13, sent by NAV + left encoder press).
Stdlib only; writes to every Sofle hidraw node with the 0xFF60 usage page (USB and BT).
"""
import glob, json, math, os, signal, subprocess, time, urllib.request

STATUS_URL = os.environ.get("KBD_STATUS_URL", "http://192.168.1.203:8788/api/status")
P2P_URL = os.environ.get("KBD_P2P_URL", "http://192.168.1.203:6868")
PAGE_SECONDS = 10  # resend so live values update
MODES = ("genshin", "market", "pc")
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

def get_json(url):
    with urllib.request.urlopen(url, timeout=10) as r:
        return json.load(r)

def genshin_lines(s, now):
    if not s:
        return ["no", "data"]
    full_at = s.get("resin_full_at", 0)
    mx = s.get("max_resin", 200)
    resin = mx if not full_at or full_at <= now else mx - math.ceil((full_at - now) / RESIN_EVERY)
    out = [f"R{resin}"]
    if s.get("expeditions"):
        done = s["expeditions"] if s.get("expeditions_back_at", 0) <= now else s.get("expeditions_done", 0)
        out.append(f"Ex{done}/{s['expeditions']}")
    if s.get("max_realm"):
        out.append(f"Po{s['realm'] * 100 // s['max_realm']}%")
    return out

def market_lines(latest, market):
    out = []
    for a in (latest or {}).get("assets", []):
        if a.get("asset") == "USDT" and a.get("buy"):
            out.append(f"U{a['buy'] / 1000:.1f}")
    for g in (latest or {}).get("gold", []):
        if g.get("symbol") == "MIENG-1L-DOJI" and g.get("sell"):
            out.append(f"Au{round(g['sell'] / 1e6)}")
    if market and "day_move" in market:
        out.append(f"S{market['day_move'] * 100:+.1f}")
    return out or ["no", "data"]

def hwmon(name, label=None):
    for d in glob.glob("/sys/class/hwmon/hwmon*"):
        try:
            if open(f"{d}/name").read().strip() != name:
                continue
            for f in sorted(glob.glob(f"{d}/temp*_input")):
                lab = f.replace("_input", "_label")
                if label is None or (os.path.exists(lab) and open(lab).read().strip() == label):
                    return int(open(f).read()) // 1000
        except OSError:
            pass
    return None

def pc_lines():
    out = []
    cpu = hwmon("k10temp", "Tctl") or hwmon("coretemp")
    out.append(f"C{cpu}" if cpu is not None else "C?")
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader"],
                           capture_output=True, text=True, timeout=3)
        out.append(f"G{int(r.stdout.split()[0])}")
    except Exception:
        out.append("G?")
    mem = {}
    for line in open("/proc/meminfo"):
        k, v = line.split(":")
        mem[k] = int(v.split()[0])
    out.append(f"M{100 - mem['MemAvailable'] * 100 // mem['MemTotal']}%")
    return out

class State:
    page = 0
    jump = False

def on_usr1(*_):
    State.page += 1
    State.jump = True

def main():
    signal.signal(signal.SIGUSR1, on_usr1)
    data, data_at = {}, 0.0
    last_vi = None
    last_time = last_page = 0.0
    last_min = -1
    while True:
        now = time.time()
        if now - data_at > STATUS_EVERY:
            for key, url in (("genshin", STATUS_URL), ("latest", P2P_URL + "/api/latest"),
                             ("market", P2P_URL + "/api/market")):
                try:
                    data[key] = get_json(url)
                except Exception:
                    pass
            data_at = now
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
            State.jump = False
            mode = MODES[State.page % len(MODES)]
            if mode == "genshin":
                lines = genshin_lines(data.get("genshin"), int(now))
            elif mode == "market":
                lines = market_lines(data.get("latest"), data.get("market"))
            else:
                lines = pc_lines()
            text = " ".join(lines[:3]).encode("ascii", "replace")[:23]
            send([T_TEXT, *text])
            last_page = now
        time.sleep(0.3)

if __name__ == "__main__":
    main()
