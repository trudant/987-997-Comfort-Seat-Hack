#!/usr/bin/env python3
"""
init_can.py
Utility to safely initialize a CAN interface.
Only configures and brings the interface up if it's currently down.
"""

import subprocess
import sys
import os


def ensure_can_interface(channel="can0", bitrate=100000) -> bool:
    """
    Ensure CAN interface is configured and up, but only if currently down.
    Returns True if interface is ready, False otherwise.
    """
    operstate_path = f"/sys/class/net/{channel}/operstate"

    if not os.path.exists(operstate_path):
        print(f"ERROR: Interface '{channel}' not found.")
        return False

    try:
        with open(operstate_path) as f:
            state = f.read().strip()
    except Exception as e:
        print(f"ERROR: Could not read {operstate_path}: {e}")
        return False

    if state != "down":
        print(f"INFO: {channel} is '{state}', leaving unchanged.")
        return True

    print(f"INFO: {channel} is down. Configuring (bitrate={bitrate})...")

    try:
        subprocess.run(["sudo", "ip", "link", "set", channel, "down"], check=False)
        subprocess.run(["sudo", "ip", "link", "set", channel, "type", "can", "bitrate", str(bitrate)], check=True)
        subprocess.run(["sudo", "ip", "link", "set", channel, "up"], check=True)
        print(f"INFO: {channel} configured and brought up.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Failed to configure {channel}: {e}")
        return False


if __name__ == "__main__":
    # Allow running standalone: python3 init_can.py [channel] [bitrate]
    ch = sys.argv[1] if len(sys.argv) > 1 else "can0"
    br = int(sys.argv[2]) if len(sys.argv) > 2 else 100000

    ok = ensure_can_interface(ch, br)
    sys.exit(0 if ok else 1)
