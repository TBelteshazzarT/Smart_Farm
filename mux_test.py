import time
import smbus

# Hardware Configuration
TCA9548A_ADDR = 0x70  # Mux address
ATTINY817_ADDR = 0x49  # ADC address (confirmed)
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


# Initialize
bus = smbus.SMBus(BUS_NUMBER)
mux = MuxManager(bus)
adc = ATtiny817_ADC(bus, ATTINY817_ADDR)

# Debug: Check mux and bus first
print("=== Debug Steps ===")
try:
    print("1. Scanning for mux...", end=" ")
    bus.write_quick(TCA9548A_ADDR)
    print("✓ Found at 0x70")
except:
    print("× Mux missing! Check wiring.")
    exit()

# Debug: Check ADC on specified mux channel
TARGET_CHANNEL = 1  # Change to your mux channel
print(f"2. Checking mux channel {TARGET_CHANNEL}...", end=" ")
if mux.select_channel(TARGET_CHANNEL):
    print("✓ Activated")
    print("3. Scanning for ADC...", end=" ")
    if adc.ping():
        print("✓ Responding!")
    else:
        print("× No response. Check:")
        print("   - ADC address (0x49)")
        print("   - Power (3.3V/GND)")
        print("   - SDA/SCL continuity")
        exit()
else:
    print("× Mux channel failed!")
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