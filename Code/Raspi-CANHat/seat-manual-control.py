#!/usr/bin/env python3
import can, os, sys, time, subprocess

# bring up can0 at 100 kbps
for cmd in [
    ["sudo","ip","link","set","can0","down"],
    ["sudo","ip","link","set","can0","type","can","bitrate","100000"],
    ["sudo","ip","link","set","can0","up"],
]:
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

CAN_IFACE = os.getenv("CAN_IFACE","can0")
FRAMES = [
    {"id":0x165,"data":"02",                        "period":60.0,"offset":0.0},
    {"id":0x325,"data":"00 00 00 00 00 00 00 00",   "period":0.10,"offset":0.10},
]

hx=lambda s:bytes.fromhex(s.replace(" ",""))
try: bus=can.interface.Bus(channel=CAN_IFACE,interface="socketcan")
except Exception as e: print(f"[ERROR] {e}"); sys.exit(1)

start=time.monotonic()
for f in sorted(FRAMES,key=lambda x:x["offset"]):
    wait=start+f["offset"]-time.monotonic()
    if wait>0: time.sleep(wait)
    msg=can.Message(arbitration_id=f["id"],is_extended_id=False,data=hx(f["data"]))
    if bus.send_periodic(msg,f["period"]) is None: print(f"[ERROR] 0x{f['id']:X}"); sys.exit(1)
    print(f"ID=0x{f['id']:X} every {f['period']}s | {f['data']}")

print(f"[INFO] {CAN_IFACE} streaming. CTRL-C to quit.")
while True: time.sleep(3600)
