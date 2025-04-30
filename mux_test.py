import time
import board
import busio
from adafruit_tca9548a import TCA9548A
from adafruit_seesaw.seesaw import Seesaw
from adafruit_seesaw.analoginput import AnalogInput

# Initialize I2C bus
i2c = busio.I2C(board.SCL, board.SDA)

# Initialize TCA9548A multiplexer with address 0x70
mux = TCA9548A(i2c, address=0x70)  # Explicitly set address

# List of ADC channels (pins) you want to read on each ATtiny817
ADC_CHANNELS = [0, 1, 2, 3, 4, 5, 6, 7]  # Adjust based on your setup

# Dictionary to store ADC objects for each multiplexer channel
adcs = {}

# Scan for connected ATtiny817 ADCs on each multiplexer channel
for mux_channel in range(8):
    try:
        # Try to initialize an ATtiny817 on this multiplexer channel
        seesaw = Seesaw(mux[mux_channel], addr=0x36)  # Default ATtiny817 I2C address
        adcs[mux_channel] = seesaw
        print(f"Found ATtiny817 on multiplexer channel {mux_channel}")
    except (ValueError, OSError):
        print(f"No ATtiny817 found on multiplexer channel {mux_channel}")
        continue

if not adcs:
    print("No ATtiny817 ADCs found!")
    exit()


def read_all_adcs():
    """Read all ADC channels from all detected ATtiny817 devices"""
    readings = {}

    for mux_channel, seesaw in adcs.items():
        channel_readings = {}
        for channel in ADC_CHANNELS:
            try:
                # Create analog input for this channel
                analog_in = AnalogInput(seesaw, channel)
                # Read voltage (0-3.3V)
                voltage = analog_in.value * 3.3
                channel_readings[f"Pin {channel}"] = voltage
            except (ValueError, OSError):
                channel_readings[f"Pin {channel}"] = None

        readings[f"Mux Channel {mux_channel}"] = channel_readings

    return readings


# Main loop to continuously read ADC values
try:
    while True:
        print("\nReading all ADC channels...")
        all_readings = read_all_adcs()

        for mux_channel, channel_readings in all_readings.items():
            print(f"\n{mux_channel}:")
            for pin, voltage in channel_readings.items():
                if voltage is not None:
                    print(f"  {pin}: {voltage:.2f}V")
                else:
                    print(f"  {pin}: Not available")

        time.sleep(1)  # Delay between readings

except KeyboardInterrupt:
    print("\nExiting...")