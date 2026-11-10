#!/usr/bin/env python3
"""Tells the Sofle left OLED whether fcitx5 is in Vietnamese, so it shows the VN or US flag.

Sends the zmk-nice-oled Raw HID "layout" report (0xAC, index into "EN,VI") on every
change and every 30 s (the keyboard treats 65 s of silence as "PC feed gone").
Stdlib only; writes to every Sofle hidraw node with the 0xFF60 usage page (USB and BT).
If Bluetooth stops working after a firmware change that alters the GATT table (BlueZ logs
"Write output report failed: Invalid handle"), remove and re-pair the keyboard.
"""
import glob, os, subprocess, time

T_LAYOUT = 0xAC
REPORT = 32
KEEPALIVE = 30

def devices():
    out = []
    for d in glob.glob("/sys/class/hidraw/hidraw*"):
        try:
            ev = open(f"{d}/device/uevent").read().upper()
            desc = open(f"{d}/device/report_descriptor", "rb").read(3)
        except OSError:
            continue
        if ":00001D50:0000615E" in ev and desc == b"\x06\x60\xff":
            out.append(("/dev/" + os.path.basename(d), "HID_ID=0005:" in ev))
    return out

def send(payload):
    body = bytes(payload).ljust(REPORT, b"\x00")[:REPORT]
    for dev, bluetooth in devices():
        pkt = b"\x00" + body  # leading report number 0, same for USB and Bluetooth
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

def main():
    last_vi, last_sent = None, 0.0
    while True:
        vi = fcitx_vi()
        now = time.monotonic()
        if vi != last_vi or now - last_sent > KEEPALIVE:
            send([T_LAYOUT, 1 if vi else 0])
            last_vi, last_sent = vi, now
        time.sleep(0.3)

if __name__ == "__main__":
    main()
