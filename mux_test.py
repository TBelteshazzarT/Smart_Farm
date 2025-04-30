import time
import smbus

# Configuration
TCA9548A_ADDR = 0x70
ATTINY817_ADDR = 0x36  # Default Seesaw address
BUS_NUMBER = 1  # Try 0 if not working


class TCA9548A:
    def __init__(self, bus, address=TCA9548A_ADDR):
        self.bus = bus
        self.address = address

    def select_channel(self, channel):
        """Select one of 0-7 channels with debug output"""
        print(f"Attempting to select channel {channel}...")
        if 0 <= channel <= 7:
            try:
                self.bus.write_byte(self.address, 1 << channel)
                time.sleep(0.01)  # Brief pause
                print(f"Channel {channel} selected successfully")
            except Exception as e:
                print(f"Channel selection failed: {str(e)}")
        else:
            raise ValueError("Channel must be 0-7")


class SeesawADC:
    def __init__(self, bus, address=ATTINY817_ADDR):
        self.bus = bus
        self.address = address

    def ping(self):
        """Check if device responds"""
        try:
            self.bus.write_quick(self.address)
            return True
        except:
            return False

    def read_adc(self, pin):
        """Read ADC with better error handling"""
        if pin < 0 or pin > 7:
            raise ValueError("Pin must be 0-7")

        try:
            # Seesaw command format
            self.bus.write_i2c_block_data(self.address, 0x09, [0x07 + pin])
            time.sleep(0.01)
            result = self.bus.read_i2c_block_data(self.address, 0x09, 2)
            return (result[0] << 8) | result[1]
        except Exception as e:
            print(f"Read error: {str(e)}")
            return None


# Initialize with debug
print("Initializing I2C...")
bus = smbus.SMBus(BUS_NUMBER)
mux = TCA9548A(bus)
adc = SeesawADC(bus)

# Test detection
print("\nTesting detection on Mux 0:")
mux.select_channel(0)
if adc.ping():
    print("ADC detected! Reading pins...")
    for pin in range(8):
        value = adc.read_adc(pin)
        if value is not None:
            voltage = (value / 65535) * 3.3
            print(f"Pin {pin}: {voltage:.2f}V")
        else:
            print(f"Pin {pin}: Read failed")
else:
    print("No ADC detected! Check:")
    print("1. Physical connections")
    print("2. I2C addresses")
    print("3. Power supply")