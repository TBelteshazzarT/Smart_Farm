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

    def read_adc(self, pin):
        """Read a 10-bit ADC value from the specified pin (0-20)"""
        try:
            # Seesaw command format (base=0x09, offset=pin)
            self.bus.write_i2c_block_data(self.address, 0x09, [pin])
            time.sleep(0.02)  # Conversion delay
            data = self.bus.read_i2c_block_data(self.address, 0x09, 2)
            raw_value = (data[0] << 8) | data[1]  # Combine bytes
            return raw_value & 0x3FF  # Keep only 10 bits
        except Exception as e:
            print(f"ADC read error (Pin {pin}): {e}")
            return None


# Initialize
bus = smbus.SMBus(BUS_NUMBER)
mux = MuxManager(bus)
adc = ATtiny817_ADC(bus, ATTINY817_ADDR)

# 1. Verify ADC is connected
try:
    mux.select_channel(1)  # Your ADC's mux channel
    bus.write_quick(ATTINY817_ADDR)
    print("✓ ADC detected!")
except:
    print("× ADC not responding! Check wiring & power.")
    exit()

# 2. Continuous reading of valid ADC pins
try:
    while True:
        if mux.select_channel(1):  # Your ADC's mux channel
            print("\n--- ADC Readings ---")
            for pin in ADC_PINS:
                raw = adc.read_adc(pin)
                if raw is not None:
                    voltage = (raw / 1023) * 3.3  # 10-bit scaling
                    print(f"Pin {pin}: {voltage:.2f}V (raw: {raw})")
                else:
                    print(f"Pin {pin}: Read failed")
        time.sleep(1)
except KeyboardInterrupt:
    print("\nStopping...")
finally:
    bus.write_byte(TCA9548A_ADDR, 0x00)  # Reset mux
    bus.close()