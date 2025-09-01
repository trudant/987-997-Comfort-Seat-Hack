# play_savvy_log.py

This script replays CAN messages from a SavvyCAN-formatted CSV log file on a Raspberry Pi using a CAN Hat. Each message is sent to the CAN bus (`can0`) with the exact timing recorded in the log.

## Features

- Reads a SavvyCAN CSV log file.
- Sends each CAN message to the bus with original timing.
- Displays each sent message in the console.
- Press any key to stop playback at any time.
- When stopped, saves all played messages to a timestamped CSV file (`YYYY-MM-DD_HH-MM-SS_playback.csv`).

## Requirements

- Raspberry Pi with CAN Hat and `can0` interface enabled.
- Python 3.
- `python-can` library (`pip install python-can`).

## Usage

1. Place your SavvyCAN CSV log file in the project directory.
2. Adjust the `LOG_FILE` path in the script if needed.
3. Run the script in the terminal:

   ```sh
   python play_savvy_log.py
   ```

4. Press any key to stop playback. The played messages will be saved to a new CSV file.

## Output

- Each message sent is printed to the console.
- Stopped playback saves all played messages to a file named like `2025-08-16_14-30-05_playback.csv`.

## Notes

- Make sure your CAN interface (`can0`) is up and running.
- The script uses non-blocking keyboard input and restores terminal settings after execution.

---

## Part I: One-time Raspberry Pi CAN Hat Setup

**Comfort CAN runs at 100kb/s. Use this bitrate when bringing up the interface.**

1. **Enable SPI and CAN modules:**
   ```sh
   sudo raspi-config
   ```
   - Go to *Interfacing Options* and enable SPI.
   - Exit and reboot if prompted.

2. **Edit `/boot/config.txt`:**
   ```sh
      # sudo nano /boot/config.txt (OLD PATH)
      sudo nano /boot/firmware/config.txt
   ```
   Add these lines at the end (adjust `dtoverlay` for your hardware if needed):
   ```
   dtparam=spi=on
   dtoverlay=mcp2515-can0,oscillator=16000000,interrupt=25
   dtoverlay=spi-bcm2835
   ```
   Save and exit (`Ctrl+O`, `Enter`, `Ctrl+X`).

3. **Install CAN utilities:**
   ```sh
   sudo apt-get update
   sudo apt-get install can-utils
   ```

4. **Reboot:**
   ```sh
   sudo reboot
   ```

5. **Bring up the CAN interface at 100kb/s:**
   ```sh
   sudo ip link set can0 up type can bitrate 100000
   ```

6. **Check CAN interface status:**
   ```sh
   ifconfig can0
   ```

---
### Expected Result
```sh
can0: flags=193<UP,RUNNING,NOARP>  mtu 16
        unspec 00-00-00-00-00-00-00-00-00-00-00-00-00-00-00-00  txqueuelen 10  (UNSPEC)
        RX packets 0  bytes 0 (0.0 B)
        RX errors 0  dropped 0  overruns 0  frame 0
        TX packets 0  bytes 0 (0.0 B)
        TX errors 0  dropped 0 overruns 0  carrier 0  collisions 0
```


---

## Part II: Python Environment Setup

1. **Create a Python virtual environment:**
   ```sh
   python3 -m venv venv
   source venv/bin/activate
   ```

2. **Install requirements:**
   ```sh
   pip install -r requirements.txt
   ```

3. **Test CAN configuration:**

   Run the test:
   ```sh
   python test-can.py
   ```

   If you see `CAN on your Raspberry Pi is Successfully Configured`, your setup

   ## If you can't get out through the Wifi Connection
   ```sh
   sudo ip route del default
   sudo ip route add default via 192.168.4.1 dev wlan0
   ```
   where 192.168.4.1 is the wifi router IP Address



   ## Added a function to load venv on startup.


```sh
nano ~/.bashrc

# run the canpi venv on startup whenever I load this ssh session
if [ -n "$SSH_CONNECTION" ]; then
   /home/saleae/documents/venv/bin/activate
fi

source /home/saleae/documents/venv/bin/activate

```



## Connection Debug. Use this to cycle the resource on the Raspberry Pi

```sh
sudo ip link set can0 down
sudo ip link set can0 type can bitrate 100000
sudo ip link set can0 up
```


## Setup for automatic login using a key for SSH startup

