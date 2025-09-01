#!/usr/bin/env python3
# Raspberry Pi SocketCAN streaming playback (with logs)
# Requires: python-can  (pip install python-can)
# Assumes:  can0 is UP and set to 100 kbps via `ip link`

import time
import sys
import can

# -------- CONFIG --------
CAN_IFACE = "can0"   # SocketCAN interface name

# (arbitration_id, payload, period_seconds, delay_after_seconds)
FRAMES = [
    (0x165, bytes([0b00000010]), 90.0, 0.100),  # same behavior as your original, with delay_after
    (0x325, bytes([0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]), 0.100, 0),  # same behavior as your original, with delay_after
]
# ------------------------

def main():
    try:
        bus = can.interface.Bus(channel=CAN_IFACE, interface="socketcan")
    except Exception as e:
        print(f"[ERROR] Could not open {CAN_IFACE}: {e}")
        sys.exit(1)

    # Prepare messages and scheduling (first send is immediate, like before)
    msgs = []
    start_monotonic = time.monotonic()
    now = start_monotonic
    for arb_id, payload, period, delay_after in FRAMES:
        msgs.append({
            "msg": can.Message(arbitration_id=arb_id, is_extended_id=False, data=payload),
            "period": float(period),
            "delay_after": float(delay_after),
            "next_due": now,   # first shot immediately
            "count": 0,
        })

    print(f"[INFO] Streaming playback on {CAN_IFACE} at 100 kbps. Ctrl+C to stop.")
    for m in msgs:
        print(f"  ID=0x{m['msg'].arbitration_id:X} every {int(m['period']*1000)} ms")

    last_status = start_monotonic

    try:
        while True:
            now = time.monotonic()

            for m in msgs:
                if now >= m["next_due"]:
                    try:
                        bus.send(m["msg"])
                        m["count"] += 1
                        print(
                            f"[TX] {time.strftime('%H:%M:%S')} "
                            f"ID=0x{m['msg'].arbitration_id:X} "
                            f"[{len(m['msg'].data)}] "
                            + " ".join(f"{b:02X}" for b in m['msg'].data)
                        )
                        if m["delay_after"] > 0:
                            time.sleep(m["delay_after"])  # optional pause after this frame
                    except can.CanError as e:
                        print(f"[ERROR] TX failed for 0x{m['msg'].arbitration_id:X}: {e}")
                    m["next_due"] += m["period"]

            # heartbeat every 5 seconds
            if now - last_status >= 5.0:
                uptime = int(now - start_monotonic)
                totals = ", ".join([f"0x{m['msg'].arbitration_id:X}:{m['count']}" for m in msgs])
                print(f"[STATUS] Uptime {uptime} s | Frames sent: {totals}")
                last_status = now

            # tiny idle to avoid busy spin
            time.sleep(0.001)

    except KeyboardInterrupt:
        pass
    finally:
        bus.shutdown()
        print("\n[INFO] Stopped.")

if __name__ == "__main__":
    main()
