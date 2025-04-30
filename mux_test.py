import time
import smbus
from collections import defaultdict

# Hardware Configuration
TCA9548A_ADDR = 0x70  # Mux address
BUS_NUMBER = 1  # 1 for Pi 3/4, 0 for older models
SCAN_DELAY = 0.1  # Delay for I2C stability


class MuxManager:
    def __init__(self, bus):
        self.bus = bus

    def select_channel(self, channel):
        """Select a mux channel (0-7) and verify isolation"""
        try:
            # Disable all channels first (reset)
            self.bus.write_byte(TCA9548A_ADDR, 0x00)
            time.sleep(SCAN_DELAY)

            # Enable only the target channel
            self.bus.write_byte(TCA9548A_ADDR, 1 << channel)
            time.sleep(SCAN_DELAY)

            # Verify only this channel is active
            active = self.bus.read_byte(TCA9548A_ADDR)
            if active != (1 << channel):
                raise IOError(f"Mux channel {channel} not isolated!")

            return True
        except Exception as e:
            print(f"⚠️ Mux channel {channel} error: {e}")
            return False


class SeesawADC:
    def __init__(self, bus, address):
        self.bus = bus
        self.address = address

    def read_adc(self, pin):
        """Read ADC value (0-7) from Seesaw device"""
        try:
            # Seesaw protocol: base=0x09, offset=0x07
            self.bus.write_i2c_block_data(self.address, 0x09, [0x07 + pin])
            time.sleep(0.02)  # Conversion delay
            data = self.bus.read_i2c_block_data(self.address, 0x09, 2)
            return (data[0] << 8) | data[1]  # Combine into 16-bit value
        except Exception as e:
            print(f"ADC read error: {e}")
            return None


# Initialize
bus = smbus.SMBus(BUS_NUMBER)
mux = MuxManager(bus)
adc = SeesawADC(bus, 0x49)  # Your ADC address

# 1. Scan for ADCs on each mux channel
print("=== Scanning for ADCs on each mux channel ===")
adc_channels = []

for channel in range(8):
    if mux.select_channel(channel):
        try:
            # Check if ADC responds
            bus.write_quick(0x49)
            print(f"✓ Found ADC on Mux Channel {channel}")
            adc_channels.append(channel)
        except:
            print(f"× No ADC on Mux Channel {channel}")

if not adc_channels:
    print("No ADCs found! Check wiring & power.")
    exit()

# 2. Continuous reading from detected ADCs
print("\n=== Starting ADC Readings ===")
try:
    while True:
        for channel in adc_channels:
            if mux.select_channel(channel):
                for pin in range(8):  # Read all 8 ADC pins
                    val = adc.read_adc(pin)
                    if val is not None:
                        voltage = (val / 65535) * 3.3  # Convert to voltage
                        print(f"CH{channel}-Pin{pin}: {voltage:.2f}V (raw: {val})")
                    else:
                        print(f"CH{channel}-Pin{pin}: Read failed")
        print("------------------")
        time.sleep(1)

except KeyboardInterrupt:
    print("\nStopping...")
finally:
    bus.write_byte(TCA9548A_ADDR, 0x00)  # Reset mux
    bus.close()