#!/usr/bin/env python3
import time
import sys
import can

# ---- CONFIG ----
CAN_CHANNEL = "can0"          # socketcan interface name
FRAME_ID    = 0x164           # Example arbitration ID
FRAME_DATA  = [0x80, 0x01, 0x06, 0x00, 0x00, 0x00, 0x00, 0x00]  # 8 bytes
PERIOD_S    = 0.5             # 500 ms
# ---------------

def main():
    print(f"[DEBUG] Starting CAN spammer on {CAN_CHANNEL}...")
    print(f"[DEBUG] Expected bitrate: 100 kbps (configure with 'ip link' first).")

    try:
        bus = can.interface.Bus(channel=CAN_CHANNEL, interface="socketcan")
        print(f"[DEBUG] Successfully opened CAN interface '{CAN_CHANNEL}'.")
    except Exception as e:
        print(f"[ERROR] Could not open CAN interface '{CAN_CHANNEL}': {e}")
        sys.exit(1)

    msg = can.Message(
        arbitration_id=FRAME_ID,
        is_extended_id=False,
        data=FRAME_DATA
    )

    print(f"[DEBUG] Frame configured: ID=0x{FRAME_ID:X}, Data=" +
          " ".join(f"{b:02X}" for b in FRAME_DATA))
    print(f"[DEBUG] Sending every {int(PERIOD_S*1000)} ms. Press Ctrl+C to stop.\n")

    try:
        while True:
            try:
                bus.send(msg)
                print(f"[TX] {time.strftime('%H:%M:%S')}  ID=0x{msg.arbitration_id:X} "
                      f"[{len(msg.data)}] " + " ".join(f"{b:02X}" for b in msg.data))
            except can.CanError as e:
                print(f"[ERROR] Failed to transmit (network issue?): {e}")
                break
            time.sleep(PERIOD_S)
    except KeyboardInterrupt:
        print("\n[DEBUG] Interrupted by user.")
    finally:
        bus.shutdown()
        print("[DEBUG] CAN bus closed. Exiting.")

if __name__ == "__main__":
    main()
