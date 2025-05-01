import time
import smbus
from functools import partial

# Hardware Config
TCA9548A_ADDR = 0x70
BUS_NUMBER = 1
SCAN_DELAY = 0.15  # Increased delay for stability

# Seesaw Registers (from Adafruit Seesaw library)
SEESAW_STATUS_BASE = 0x00
SEESAW_GPIO_BASE = 0x01
SEESAW_ADC_BASE = 0x09
SEESAW_ADC_CHANNEL_OFFSET = 0x07
SEESAW_ADC_PINMODE = 0x00  # Set pin to analog input

ADC_PINS = [0, 1, 2, 3, 6, 7, 18, 19, 20]


class TCA9548A:
    def select_channel(self, channel):
        """Select channel with verification"""
        try:
            print(f"Attempting to select CH{channel}...")
            # Disable all channels first
            self.bus.write_byte(TCA9548A_ADDR, 0x00)
            time.sleep(SCAN_DELAY)

            # Enable target channel
            print(f"Enabling CH{channel}...")
            self.bus.write_byte(TCA9548A_ADDR, 1 << channel)
            time.sleep(SCAN_DELAY)

            # Verify selection
            active = self.bus.read_byte(TCA9548A_ADDR)
            print(f"Active channels: {bin(active)}")
            if active != (1 << channel):
                raise IOError(f"Channel {channel} not activated (got {bin(active)})")
            return True
        except Exception as e:
            print(f"Mux Error (CH{channel}): {str(e)}")
            return False


class SeesawADC:
    def __init__(self, bus, address):
        self.bus = bus
        self.address = address
        self._verify_device()

    def _verify_device(self):
        """Verify the device is present and responding"""
        try:
            # Read status register (should always work if device is present)
            status = self._read_reg(SEESAW_STATUS_BASE, 1)
            print(f"Device 0x{self.address:02x} verified (status: 0x{status[0]:02x})")
            return True
        except Exception as e:
            print(f"Device verification failed at 0x{self.address:02x}: {str(e)}")
            return False

    def _read_reg(self, reg, length=2):
        """More robust register read"""
        for attempt in range(5):  # Increased retry count
            try:
                # Ensure channel is still selected
                mux.select_channel(TARGET_CHANNEL)

                # Add small delay before each attempt
                time.sleep(0.05 * (attempt + 1))

                return self.bus.read_i2c_block_data(self.address, reg, length)
            except OSError as e:
                if e.errno == 121:  # Remote I/O error
                    print(f"Attempt {attempt + 1} failed for reg 0x{reg:02x}")
                    if attempt == 4:  # Last attempt
                        raise IOError(f"Failed after 5 retries (reg 0x{reg:02x})")
                    continue
                raise

    def read_adc(self, pin):
        """Modified ADC read with better error handling"""
        try:
            # First verify device is responsive
            if not self._verify_device():
                return None

            # Use correct register (0x10 for ADC readings)
            reg = 0x10

            # Write pin number (single byte)
            mux.select_channel(TARGET_CHANNEL)
            self.bus.write_byte_data(self.address, reg, pin)

            # Wait for conversion (longer delay)
            time.sleep(0.2)

            # Read result
            mux.select_channel(TARGET_CHANNEL)
            data = self._read_reg(reg, 2)

            # Combine bytes (MSB first)
            return (data[0] << 8) | data[1]

        except Exception as e:
            print(f"ADC Read Error (Pin {pin}): {str(e)}")
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
        print(f"Scanning CH{channel}...")
        for addr in [0x36, 0x37, 0x38, 0x39, 0x49, 0x4A, 0x4B]:  # Common seesaw addresses
            try:
                bus.write_quick(addr)
                print(f"Found device at 0x{addr:02x} (CH{channel})")

                # Test if it's a seesaw
                test_adc = SeesawADC(bus, addr)
                if test_adc._verify_device():  # First verify basic communication
                    print(f"✓ Device at 0x{addr:02x} responds to status request")
                    # Test actual ADC reading
                    raw = test_adc.read_adc(0)  # Test pin 0
                    if raw is not None:
                        ADC_ADDRESS = addr
                        TARGET_CHANNEL = channel
                        print(f"✓ Confirmed ADC at 0x{addr:02x} (CH{channel}) - Initial reading: {raw}")
                        break
            except Exception as e:
                print(f"Scan error at 0x{addr:02x} (CH{channel}): {str(e)}")

if not ADC_ADDRESS:
    print("No valid ADC found!")
    exit()

print(f"\nUsing ADC at 0x{ADC_ADDRESS:02x} on CH{TARGET_CHANNEL}")

# Continuous reading
adc = SeesawADC(bus, ADC_ADDRESS)
try:
    while True:
        if not mux.select_channel(TARGET_CHANNEL):
            print("Mux channel selection failed!")
            time.sleep(1)
            continue

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