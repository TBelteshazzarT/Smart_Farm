import time
import smbus

# Hardware Configuration
TCA9548A_ADDR = 0x70  # Mux address
BUS_NUMBER = 1  # 1 for Pi 3/4, 0 for older Pis
SCAN_DELAY = 0.1  # Delay for I2C stability


class TCA9548A:
    def __init__(self, bus, address=TCA9548A_ADDR):
        self.bus = bus
        self.address = address

    def select_channel(self, channel):
        """Select a single channel (0-7)"""
        try:
            self.bus.write_byte(self.address, 1 << channel)
            time.sleep(SCAN_DELAY)
            return True
        except Exception as e:
            print(f"Mux channel {channel} error: {e}")
            return False

    def scan_channel(self, channel):
        """Scan devices on specific channel (like code 1)"""
        devices = []
        if self.select_channel(channel):
            for addr in range(0x03, 0x78):
                try:
                    self.bus.write_quick(addr)
                    devices.append(addr)
                except:
                    pass
        return devices


class ATtiny817_ADC:
    def __init__(self, bus, address):
        self.bus = bus
        self.address = address

    def read_adc(self, pin):
        """Read ADC value from specified pin (like code 2)"""
        try:
            # Seesaw protocol for ADC
            self.bus.write_i2c_block_data(self.address, 0x09, [pin])
            time.sleep(0.02)
            data = self.bus.read_i2c_block_data(self.address, 0x09, 2)
            return (data[0] << 8 | data[1]) & 0x3FF  # 10-bit value
        except Exception as e:
            print(f"Read error: {e}")
            return None


# Initialize
bus = smbus.SMBus(BUS_NUMBER)
mux = TCA9548A(bus)

# 1. First scan all channels (like code 1)
print("=== Scanning all channels ===")
for channel in range(8):
    devices = mux.scan_channel(channel)
    print(f"Channel {channel}: {[hex(x) for x in devices if x != 0x70]}")

# 2. Then read from specific channel (like code 2)
TARGET_CHANNEL = 1  # Change to your channel
ADC_ADDRESS = 0x49  # Change to your ADC address

if mux.select_channel(TARGET_CHANNEL):
    adc = ATtiny817_ADC(bus, ADC_ADDRESS)

    # Continuous reading
    try:
        print(f"\n=== Reading ADC at 0x{ADC_ADDRESS:02x} on channel {TARGET_CHANNEL} ===")
        while True:
            # Read all valid pins (0,1,2,3,6,7,18,19,20)
            for pin in [0, 1, 2, 3, 6, 7, 18, 19, 20]:
                val = adc.read_adc(pin)
                if val is not None:
                    voltage = (val / 1023) * 3.3  # Convert to voltage
                    print(f"Pin {pin}: {voltage:.2f}V (raw: {val})")
                else:
                    print(f"Pin {pin}: Read failed")
            print("-----")
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...")
finally:
bus.write_byte(TCA9548A_ADDR, 0x00)  # Reset mux
bus.close()