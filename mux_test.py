import time
import smbus
from collections import defaultdict

# Hardware Configuration
TCA9548A_ADDR = 0x70  # Mux address
DEFAULT_ADC_ADDR = 0x49  # Default ADC address
BUS_NUMBER = 1  # 1 for Pi 3/4, 0 for older Pis
SCAN_DELAY = 0.1  # Delay for I2C stability

# Valid ADC pins on ATtiny817 (0,1,2,3,6,7,18,19,20)
ADC_PINS = [0, 1, 2, 3, 6, 7, 18, 19, 20]


class MuxManager:
    def __init__(self, bus):
        self.bus = bus

    def select_channel(self, channel):
        """Select and verify a mux channel (0-7)"""
        try:
            self.bus.write_byte(TCA9548A_ADDR, 0x00)  # Disable all first
            time.sleep(SCAN_DELAY)
            self.bus.write_byte(TCA9548A_ADDR, 1 << channel)
            time.sleep(SCAN_DELAY)
            return True
        except Exception as e:
            print(f"⚠️ Mux channel {channel} error: {e}")
            return False


class ATtiny817_ADC:
    def __init__(self, bus, address):
        self.bus = bus
        self.address = address

    def ping(self):
        """More reliable device check (reads a register)"""
        try:
            # Read the hardware ID register (0x01) of the Seesaw
            data = self.bus.read_i2c_block_data(self.address, 0x01, 1)
            # ATtiny817 should return 0x81 or similar
            return True if data else False
        except:
            return False

    def read_adc(self, pin):
        """Read a 10-bit ADC value from the specified pin (0-20)"""
        try:
            self.bus.write_i2c_block_data(self.address, 0x09, [pin])
            time.sleep(0.02)
            data = self.bus.read_i2c_block_data(self.address, 0x09, 2)
            return (data[0] << 8 | data[1]) & 0x3FF  # 10-bit mask
        except Exception as e:
            print(f"ADC read error (Pin {pin}): {e}")
            return None


def scan_i2c_addresses(bus, mux_channel=None):
    """Scan all I2C addresses on a specific mux channel"""
    found_addresses = []
    if mux_channel is not None:
        bus.write_byte(TCA9548A_ADDR, 1 << mux_channel)
        time.sleep(SCAN_DELAY)

    for addr in range(0x03, 0x78):
        try:
            bus.write_quick(addr)
            found_addresses.append(addr)
            time.sleep(0.001)
        except:
            pass

    if mux_channel is not None:
        bus.write_byte(TCA9548A_ADDR, 0x00)

    return found_addresses


# Initialize
bus = smbus.SMBus(BUS_NUMBER)
mux = MuxManager(bus)

print("=== Debug Steps ===")

# 1. Verify mux is present
try:
    bus.write_quick(TCA9548A_ADDR)
    print("✓ Mux detected at 0x70")
except:
    print("× Mux missing! Check wiring.")
    exit()

# 2. Scan for ADCs on target channel
TARGET_CHANNEL = 1  # Change to your mux channel
print(f"\nScanning mux channel {TARGET_CHANNEL}...")

# First try default address
mux.select_channel(TARGET_CHANNEL)
adc = ATtiny817_ADC(bus, DEFAULT_ADC_ADDR)

if adc.ping():
    print(f"✓ Found ADC at default address 0x{DEFAULT_ADC_ADDR:02x}")
else:
    print(f"× No ADC at default address 0x{DEFAULT_ADC_ADDR:02x}")
    print("Scanning all addresses on this channel...")

    found_addresses = scan_i2c_addresses(bus, TARGET_CHANNEL)
    if found_addresses:
        print(f"Found devices at: {[hex(x) for x in found_addresses]}")

        # Test each found address to see if it's an ADC
        for addr in found_addresses:
            test_adc = ATtiny817_ADC(bus, addr)
            if test_adc.ping():
                print(f"✓ Found potential ADC at 0x{addr:02x}")
                print("Verifying by reading a pin...")
                val = test_adc.read_adc(0)  # Try reading pin 0
                if val is not None:
                    print(f"Confirmed ADC at 0x{addr:02x} (read value: {val})")
                    adc = test_adc
                    break
        else:
            print("× No valid ADC found on this channel")
            exit()
    else:
        print("× No I2C devices found on this channel")
        exit()

# Continuous reading
try:
    print("\n=== Starting Readings ===")
    while True:
        if mux.select_channel(TARGET_CHANNEL):
            for pin in ADC_PINS:
                raw = adc.read_adc(pin)
                if raw is not None:
                    voltage = (raw / 1023) * 3.3
                    print(f"Pin {pin}: {voltage:.2f}V (raw: {raw})")
                else:
                    print(f"Pin {pin}: Read failed")
        time.sleep(1)
except KeyboardInterrupt:
    print("\nStopping...")
finally:
    bus.write_byte(TCA9548A_ADDR, 0x00)  # Reset mux
    bus.close()