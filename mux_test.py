import time
import smbus
from collections import defaultdict

# Hardware Configuration
TCA9548A_ADDR = 0x70  # Mux address
BUS_NUMBER = 1  # 1 for Pi 3/4, 0 for older models


class I2CScanner:
    def __init__(self, bus):
        self.bus = bus

    def scan_channel(self, mux_channel=None):
        """Scan for devices on a specific mux channel or main bus"""
        found = []

        if mux_channel is not None:
            # Select mux channel
            self.bus.write_byte(TCA9548A_ADDR, 1 << mux_channel)
            time.sleep(0.01)

        # Scan all possible I2C addresses
        for addr in range(0x03, 0x78):
            try:
                self.bus.write_quick(addr)
                found.append(addr)
                time.sleep(0.001)
            except:
                pass

        # Reset mux if used
        if mux_channel is not None:
            self.bus.write_byte(TCA9548A_ADDR, 0x00)

        return found


class SeesawADC:
    def __init__(self, bus, address):
        self.bus = bus
        self.address = address

    def read_adc(self, pin):
        """Read ADC value from specified pin (0-7)"""
        try:
            # Seesaw command format
            self.bus.write_i2c_block_data(self.address, 0x09, [0x07 + pin])
            time.sleep(0.01)
            data = self.bus.read_i2c_block_data(self.address, 0x09, 2)
            return (data[0] << 8) | data[1]
        except Exception as e:
            print(f"Read error on 0x{self.address:02x}: {e}")
            return None


# Initialize
bus = smbus.SMBus(BUS_NUMBER)
scanner = I2CScanner(bus)

print("=== Scanning for devices ===")

# 1. First detect all connected ADCs
device_map = defaultdict(dict)  # {mux_channel: {address: device}}

for channel in range(8):
    found = scanner.scan_channel(channel)
    if found:
        print(f"Mux {channel}: Found devices at {[hex(x) for x in found]}")
        for addr in found:
            # Test if it's a seesaw device
            try:
                ss = SeesawADC(bus, addr)
                if ss.read_adc(0) is not None:  # Test read
                    device_map[channel][addr] = ss
                    print(f"  ✓ Confirmed Seesaw at 0x{addr:02x}")
            except:
                pass

if not device_map:
    print("No Seesaw devices found!")
    exit()

# 2. Continuous reading of found devices
print("\n=== Starting continuous reading ===")
try:
    while True:
        for channel, devices in device_map.items():
            # Select mux channel
            bus.write_byte(TCA9548A_ADDR, 1 << channel)
            time.sleep(0.01)

            for addr, adc in devices.items():
                print(f"\nMux {channel}, ADC 0x{addr:02x}:")
                for pin in range(8):
                    val = adc.read_adc(pin)
                    if val is not None:
                        voltage = (val / 65535) * 3.3
                        print(f"  Pin {pin}: {voltage:.2f}V (raw: {val})")

        time.sleep(1)  # Delay between full scans

except KeyboardInterrupt:
    print("\nStopping...")
    bus.write_byte(TCA9548A_ADDR, 0x00)  # Reset mux