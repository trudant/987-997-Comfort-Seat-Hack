#!/usr/bin/env python3
import can
import sys

# ---- CONFIG ----
CAN_CHANNEL = "can0"   # socketcan interface name
# ---------------

def main():
    print(f"[DEBUG] Starting CAN RX listener on {CAN_CHANNEL}...")
    print("[DEBUG] Waiting for frames. Press Ctrl+C to stop.\n")

    try:
        bus = can.interface.Bus(channel=CAN_CHANNEL, interface="socketcan")
    except Exception as e:
        print(f"[ERROR] Could not open CAN interface '{CAN_CHANNEL}': {e}")
        sys.exit(1)

    try:
        while True:
            msg = bus.recv(timeout=1.0)  # wait up to 1s for a message
            if msg is None:
                continue  # no message, keep looping
            print(f"[RX]  ID=0x{msg.arbitration_id:X} [{msg.dlc}] " +
                  " ".join(f"{b:02X}" for b in msg.data))
    except KeyboardInterrupt:
        print("\n[DEBUG] Interrupted by user.")
    finally:
        bus.shutdown()
        print("[DEBUG] CAN bus closed. Exiting.")

if __name__ == "__main__":
    main()
