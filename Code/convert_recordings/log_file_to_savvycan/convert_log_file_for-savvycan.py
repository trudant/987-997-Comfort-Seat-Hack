import csv
import os
import sys

def parse_canlog_semicolon(input_file, output_file):
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter=';')
        lines = list(reader)

    with open(output_file, 'w', newline='') as f_out:
        writer = csv.writer(f_out)
        # SavvyCAN header
        writer.writerow([
            "Time Stamp", "ID", "Extended", "Dir", "Bus", "LEN",
            "D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8"
        ])

        t0 = None
        for i, parts in enumerate(lines):
            if i == 0:
                continue  # skip header

            if len(parts) < 4:
                continue

            try:
                timestamp = float(parts[0])
                can_id = int(parts[1])
                data_str = parts[3].strip()
                data_bytes = data_str.split()
                data_len = len(data_bytes)
                data_bytes += [''] * (8 - data_len)
            except Exception:
                continue

            # Use first timestamp as t0
            if t0 is None:
                t0 = timestamp
            timestamp_us = int((timestamp - t0) * 1_000_000)

            # Extended frame detection (if ID > 0x7FF)
            extended = 1 if can_id > 0x7FF else 0

            # Direction: always "R" (Receive) for log files
            direction = "R"
            bus = 0

            writer.writerow([
                timestamp_us, f"{can_id:08X}", extended, direction, bus, data_len,
                *data_bytes
            ])

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python convert_file.py <input_file>")
        sys.exit(1)

    input_file = sys.argv[1]
    file_name, _ = os.path.splitext(os.path.basename(input_file))
    output_file = f"{file_name}_savvycan.csv"
    parse_canlog_semicolon(input_file, output_file)