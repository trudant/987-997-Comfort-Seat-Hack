import csv
import time
import can
import sys
import select
import datetime
import termios
import fcntl
import os
from can.bus import BusState
from init_can import ensure_can_interface

SOURCE_LOG_FILE = "./2025-4-4_canlog_1_savvycan.csv"  # Adjust path as needed
CAN_CHANNEL = "can0"
CAN_BUSTYPE = "socketcan"
CAN_BITRATE = 100000  # Comfort CAN runs at 100kbps (usually set via ip link)
RUN_LOGS_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "runlogs")

# How long to wait for TX confirmation (loopback) after each send
TX_CONFIRM_TIMEOUT_S = 0.300  # 300 ms is plenty for normal CAN @ 100 kbps
TIME_SCALE_FACTOR = 1.0 # time scaling. 1.1 means that 1 uS spreads out realtive time to 1.1uS

def _parse_timestamp_us(ts_val):
    """
    Accept either:
      - integer microseconds (e.g., 1234567)
      - float seconds (e.g., 1.234567)
    Return integer microseconds.
    """
    s = str(ts_val).strip()
    if not s:
        raise ValueError("Empty timestamp")
    if "." in s:
        # seconds as float
        return int(float(s) * 1_000_000)
    # microseconds as int
    return int(s)

def _is_blank_row(row: dict) -> bool:
    # A row is blank if all values are empty / whitespace / None
    if row is None:
        return True
    for v in row.values():
        if v is None:
            continue
        if str(v).strip() != "":
            return False
    return True

def parse_savvycan_csv(filename):
    with open(filename, newline='') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    messages = []
    if not rows:
        return messages

    # Skip leading blank rows
    idx = 0
    while idx < len(rows) and _is_blank_row(rows[idx]):
        idx += 1
    if idx >= len(rows):
        return messages

    # Establish t0 from the first non-blank row
    t0_us = _parse_timestamp_us(rows[idx]["Time Stamp"])

    for row in rows[idx:]:
        # Skip blank lines (human readability separators)
        if _is_blank_row(row):
            continue

        try:
            timestamp_us_abs = _parse_timestamp_us(row["Time Stamp"])
        except Exception:
            # If the timestamp is missing/invalid, skip the row
            continue

        rel_us = timestamp_us_abs - t0_us
        if rel_us < 0:
            # Keep negative relative times (indicates a "back in time" segment)
            # We'll handle the reset at playback time.
            pass

        # Make a copy before mutating
        row = dict(row)

        # Normalize string columns to safe defaults
        raw_id = row.get("ID", "")
        if not raw_id:
            # Can't form a CAN frame without an ID; skip
            continue

        try:
            can_id = int(raw_id, 16)
        except ValueError:
            # Bad ID; skip
            continue

        # Some logs may use "Extended" as "0/1" or "True/False"
        ext_field = (row.get("Extended", "0") or "").strip().lower()
        extended = ext_field in ("1", "true", "yes")

        dlc_str = row.get("LEN", "0")
        try:
            dlc = int(dlc_str)
        except ValueError:
            dlc = 0
        dlc = max(0, min(8, dlc))

        data = []
        for i in range(1, 9):
            d = row.get(f"D{i}", "")
            d = "" if d is None else d.strip()
            if d == "":
                continue
            try:
                data.append(int(d, 16))
            except ValueError:
                # Bad byte; treat as 0x00
                data.append(0x00)
        if len(data) < dlc:
            data += [0] * (dlc - len(data))
        data = data[:dlc]

        # Update the raw dict so any saved playback CSV is relative, too
        # Keep as string for CSV writing; allow negative here (reset handled later)
        row["Time Stamp"] = str(rel_us)

        messages.append({
            "timestamp_us": rel_us,       # RELATIVE microseconds; may be negative for segment resets
            "can_id": can_id,
            "extended": extended,
            "dlc": dlc,
            "data": data,
            "raw": row                    # raw now has relative "Time Stamp" (can be negative)
        })
    return messages

def key_pressed():
    dr, _, _ = select.select([sys.stdin], [], [], 0)
    return dr != []

def save_played_messages(played_msgs):
    if not played_msgs:
        print("No messages to save.")
        return
    os.makedirs(RUN_LOGS_FOLDER, exist_ok=True)
    now = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"{now}_playback.csv"
    file_path = os.path.join(RUN_LOGS_FOLDER, filename)
    fieldnames = played_msgs[0]["raw"].keys()
    with open(file_path, "w", newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for msg in played_msgs:
            writer.writerow(msg["raw"])
    print(f"Played messages saved to {file_path}")

def save_playback_csv(csv_data):
    os.makedirs(RUN_LOGS_FOLDER, exist_ok=True)
    file_path = os.path.join(RUN_LOGS_FOLDER, "_playback.csv")
    with open(file_path, "w") as f:
        f.write(csv_data)

def format_raw_csv_line(raw_dict):
    # Preserve original column order from DictReader
    return ",".join([(raw_dict.get(f, "") or "") for f in raw_dict.keys()])

def is_same_frame(a: can.Message, b: can.Message) -> bool:
    return (
        a.arbitration_id == b.arbitration_id and
        a.is_extended_id == b.is_extended_id and
        bytes(a.data) == bytes(b.data) and
        a.dlc == b.dlc
    )

def wait_for_tx_confirmation(bus: can.BusABC, sent: can.Message, timeout_s: float):
    """
    Wait for either:
      - Loopback of our own just-sent frame (success)
      - Error frames / bus state change indicating trouble (failure)
      - Timeout (treat as failure: likely no ACK)
    Returns (ok: bool, reason: str)
    """
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        # Fast check for bus state degradation
        try:
            state = bus.state
            if state in (BusState.ERROR_PASSIVE, BusState.BUS_OFF):
                return (False, f"CAN bus entered {state.name.replace('_',' ').title()} state")
        except Exception:
            pass

        try:
            msg = bus.recv(timeout=0.01)
        except Exception as e:
            return (False, f"bus.recv failed: {e}")

        if msg is None:
            continue

        if getattr(msg, "is_error_frame", False):
            return (False, "Received CAN error frame during transmission")

        if is_same_frame(msg, sent):
            return (True, "Tx confirmed (loopback)")

    return (False, f"No TX confirmation within {timeout_s*1000:.0f} ms (likely no ACK)")

def play_log(messages, channel=CAN_CHANNEL, bitrate=CAN_BITRATE):
    try:
        # Ensure we can observe our own looped-back frames to confirm TX
        bus = can.interface.Bus(
            channel=channel,
            interface=CAN_BUSTYPE,
            bitrate=bitrate,
            receive_own_messages=True  # critical for TX confirmation
        )
    except Exception as e:
        print(f"ERROR: Could not open CAN interface '{channel}' at {bitrate}bps.\n{e}")
        return

    # Playback pacing state
    segment_anchor_wall = time.time()  # wall-clock time when current segment started
    last_rel_s = None                  # last message's relative time (seconds) within current segment

    played_msgs = []

    print("Press any key to stop playback...")

    # Set stdin to non-blocking
    fd = sys.stdin.fileno()
    old_term = termios.tcgetattr(fd)
    new_term = termios.tcgetattr(fd)
    new_term[3] = new_term[3] & ~termios.ICANON & ~termios.ECHO
    termios.tcsetattr(fd, termios.TCSAFLUSH, new_term)
    old_flags = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, old_flags | os.O_NONBLOCK)

    try:
        for i, msg in enumerate(messages):
            rel_s = msg["timestamp_us"] / 1_000_000.0

            # Handle "back in time" -> start a new segment:
            #  - play this frame immediately
            #  - reset segment anchor so future frames keep their relative spacing
            reset_segment = (last_rel_s is not None and rel_s < last_rel_s)

            if reset_segment:
                # Start a new wall-clock anchor such that future sleeps are relative to now
                segment_anchor_wall = time.time()
                sleep_time = 0.0
            else:
                # Normal pacing: wait until (segment_anchor_wall + rel_s)
                now = time.time()
                target_wall = segment_anchor_wall + rel_s
                sleep_time = max(0.0, target_wall - now)

            if sleep_time > 0:
                time.sleep(sleep_time)

            can_msg = can.Message(
                arbitration_id=msg["can_id"],
                is_extended_id=msg["extended"],
                data=msg["data"],
                dlc=msg["dlc"]
            )

            raw = msg["raw"]
            csv_line = format_raw_csv_line(raw)
            print(csv_line)

            try:
                bus.send(can_msg)
            except can.CanError as e:
                print(f"ERROR: Message NOT queued/sent: {csv_line}\n{e}")
                print("Stopping playback due to immediate CAN send error.")
                save_played_messages(played_msgs)
                break

            # Wait for confirmation / detect trouble
            ok, reason = wait_for_tx_confirmation(bus, can_msg, TX_CONFIRM_TIMEOUT_S)
            if not ok:
                print(f"\nERROR DURING PLAYBACK at line {i+1}: {reason}")
                print("Last line attempted:")
                print(csv_line)
                save_played_messages(played_msgs)
                break

            played_msgs.append(msg)
            last_rel_s = rel_s

            if reset_segment:
                # After immediately sending the segment's first frame,
                # align future waits to its relative time (0 at the anchor).
                # We accomplish this by backdating the anchor by rel_s.
                # That way, the next frame at rel_s_next sleeps for (rel_s_next - rel_s).
                segment_anchor_wall = time.time() - rel_s

            if key_pressed():
                print("\nPlayback stopped by user.")
                print("Last confirmed line:")
                print(csv_line)
                save_played_messages(played_msgs)
                break
        else:
            # Completed
            save_played_messages(played_msgs)

    finally:
        try:
            termios.tcsetattr(fd, termios.TCSAFLUSH, old_term)
            fcntl.fcntl(fd, fcntl.F_SETFL, old_flags)
        except Exception:
            pass
        try:
            bus.shutdown()
        except Exception:
            pass

if __name__ == "__main__":
    # Default log file (relative to script’s folder)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    SOURCE_LOG_FILE = os.path.join(script_dir, "2025-4-4_canlog_1_savvycan.csv")

    # Allow override from first command-line argument
    if len(sys.argv) > 1:
        override_path = sys.argv[1]
        SOURCE_LOG_FILE = os.path.join(script_dir, override_path)

    if ensure_can_interface(CAN_CHANNEL, CAN_BITRATE):
        messages = parse_savvycan_csv(SOURCE_LOG_FILE)
        if not messages:
            print(f"No messages found in CSV: {SOURCE_LOG_FILE}")
            sys.exit(1)
        # Note: messages may contain negative relative timestamps if the source jumped back.
        # Playback handles these by starting new segments.
        play_log(messages)
    else:
        print("Aborting: CAN interface not ready.")
