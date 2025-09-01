# test-can.py
import can

try:
    bus = can.interface.Bus(channel='can0', interface='socketcan')
    print("CAN on your Raspberry Pi is Successfully Configured")
    bus.shutdown()
except Exception as e:
    print("CAN configuration failed:", e)