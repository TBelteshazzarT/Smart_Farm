import time
import smbus
from functools import partial

# Hardware Config
TCA9548A_ADDR = 0x70
BUS_NUMBER = 1
SCAN_DELAY = 0.15  # Increased delay for stability

# ADC Configuration
ADC_PINS = [0, 1, 2, 3, 6, 7, 18, 19, 20]
SEESAW_ADC_BASE = 0x09
ADC_READ_DELAY = 0.05  # Longer delay for ADC conversion


class TCA9548A:
    def __init__(self, bus):
        self.bus = bus

    def select_channel(self, channel):
        """Select channel with verification"""
        try:
            # Disable all channels first
            self.bus.write_byte(TCA9548A_ADDR, 0x00)
            time.sleep(SCAN_DELAY)

            # Enable target channel
            self.bus.write_byte(TCA9548A_ADDR, 1 << channel)
            time.sleep(SCAN_DELAY)

            # Verify selection
            active = self.bus.read_byte(TCA9548A_ADDR)
            if active != (1 << channel):
                raise IOError(f"Channel {channel} not activated")
            return True
        except Exception as e:
            print(f"Mux Error (CH{channel}): {str(e)}")
            return False


class SeesawADC:
    def __init__(self, bus, address):
        self.bus = bus
        self.address = address

    def _read_reg(self, reg, length=2):
        """Generic register read with retries"""
        for _ in range(3):
            try:
                data = self.bus.read_i2c_block_data(self.address, reg, length)
                print(f"Debug: reg 0x{reg:02x} = {data}")  # Debug output
                return data
            except OSError as e:
                print(f"Retrying... Error: {e}")
                time.sleep(0.1)
        raise IOError(f"Failed after 3 retries (reg 0x{reg:02x})")

    def read_adc(self, pin):
        try:
            # Request conversion on pin
            self.bus.write_i2c_block_data(self.address, 0x09, [pin])
            time.sleep(0.01)  # 10ms delay for conversion

            # Read result from 0x09
            data = self._read_reg(0x09)
            print(f"Raw bytes from 0x09: {data}")  # Expect [high_byte, low_byte]
            return (data[0] << 8) | data[1]
        except Exception as e:
            print(f"Error: {e}")
            return None

# Initialize
bus = smbus.SMBus(BUS_NUMBER)
mux = TCA9548A(bus)

# Scan for devices
print("=== Scanning for ADCs ===")
ADC_ADDRESS = None
TARGET_CHANNEL = None

for channel in range(8):
    if mux.select_channel(channel):
        for addr in [0x49, 0x4A, 0x4B]:  # Common seesaw addresses
            try:
                bus.write_quick(addr)
                print(f"Found device at 0x{addr:02x} (CH{channel})")
                # Test if it's a seesaw
                test_adc = SeesawADC(bus, addr)
                if test_adc.read_adc(0) is not None:  # Test pin 0
                    ADC_ADDRESS = addr
                    TARGET_CHANNEL = channel
                    print(f"✓ Confirmed ADC at 0x{addr:02x} (CH{channel})")
                    break
            except:
                pass

if not ADC_ADDRESS:
    print("No valid ADC found!")
    exit()

# Continuous reading
adc = SeesawADC(bus, ADC_ADDRESS)
try:
    while True:
        if mux.select_channel(TARGET_CHANNEL):
            print(f"\nReading ADC 0x{ADC_ADDRESS:02x} (CH{TARGET_CHANNEL}):")
            for pin in ADC_PINS:
                raw = adc.read_adc(pin)
                if raw is not None:
                    voltage = (raw / 1023) * 3.3
                    print(f"  Pin {pin}: {voltage:.2f}V (raw: {raw})")
        time.sleep(1)
except KeyboardInterrupt:
    print("\nStopping...")
finally:
    bus.write_byte(TCA9548A_ADDR, 0x00)
    bus.close()