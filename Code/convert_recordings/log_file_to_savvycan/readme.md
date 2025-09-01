# Convert Recordings - CAN Log Converter

This folder contains a utility script for converting raw CAN log files (semicolon-delimited) into a format compatible with SavvyCAN.

## What does it do?

The script [`convert_file.py`](Code/Convert%20Recordings/convert_file.py) reads a CAN log file where each line contains a timestamp, CAN ID, and data bytes separated by semicolons. It outputs a CSV file with the correct header and formatting for SavvyCAN, including:

- Normalized timestamps (relative to the first message, in microseconds)
- CAN ID in 8-digit hexadecimal
- Extended frame detection
- Data bytes padded to 8 columns

## How to use

Run the script from the root of your workspace or from the `Code/Convert Recordings` directory. Provide the path to your raw CAN log file as the argument.

**Example:**
```sh
python "Code/Convert Recordings/log to savvycan/convert_log_file_for-savvycan.py" "Reference/Recordings/2025-4-4_raw_recording/2025-4-4_canlog_1.txt"
```

This will create a new file named `2025-4-4_canlog_1_savvycan.csv` in your workspace.

## Output

The output CSV file will have the following columns:

- Time Stamp
- ID
- Extended
- Dir
- Bus
- LEN
- D1 ... D8 (data bytes)

You can import this file directly into SavvyCAN for analysis.

## Script location

-