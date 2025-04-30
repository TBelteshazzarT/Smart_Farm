import time
import smbus

# I2C addresses
TCA9548A_ADDR = 0x70
ATTINY817_ADDR = 0x36  # Default Seesaw address

# Initialize I2C bus (1 for newer Pi, 0 for very old Pi)
bus = smbus.SMBus(1)

class TCA9548A:
    def __init__(self, bus, address=TCA9548A_ADDR):
        self.bus = bus
        self.address = address

    def select_channel(self, channel):
        """Select one of 0-7 channels"""
        if 0 <= channel <= 7:
            self.bus.write_byte(self.address, 1 << channel)
        else:
            raise ValueError("Channel must be 0-7")

class SeesawADC:
    def __init__(self, bus, address=ATTINY817_ADDR):
        self.bus = bus
        self.address = address

    def read_adc(self, pin):
        """Read ADC value from specified pin (0-7)"""
        if pin < 0 or pin > 7:
            raise ValueError("Pin must be 0-7")

        # Seesaw command format for ADC reading
        # 0x09 = ADC module base address
        # 0x07 = ADC channel offset
        self.bus.write_i2c_block_data(self.address, 0x09, [0x07 + pin])

        # Small delay for conversion
        time.sleep(0.01)

        # Read 2 bytes of data
        result = self.bus.read_i2c_block_data(self.address, 0x09, 2)

        # Combine bytes into 16-bit value
        return (result[0] << 8) | result[1]

# Initialize components
mux = TCA9548A(bus)
adc = SeesawADC(bus)

def read_all_channels():
    """Read all ADC channels on all mux channels"""
    results = {}

    for mux_channel in range(8):
        try:
            # Select mux channel
            mux.select_channel(mux_channel)

            # Test if device exists by attempting a read
            adc.read_adc(0)

            # Read all ADC pins if device exists
            channel_results = {}
            for pin in range(8):
                try:
                    value = adc.read_adc(pin)
                    voltage = (value / 65535) * 3.3  # Convert to voltage (assuming 3.3V reference)
                    channel_results[f"Pin {pin}"] = f"{voltage:.2f}V"
                except IOError:
                    channel_results[f"Pin {pin}"] = "Error"

            results[f"Mux {mux_channel}"] = channel_results

        except IOError:
            results[f"Mux {mux_channel}"] = "No device"

    return results

# Main reading loop
try:
    while True:
        print("\nReading all ADCs...")
        readings = read_all_channels()

        for mux_ch, pins in readings.items():
            print(f"\n{mux_ch}:")
            if isinstance(pins, dict):
                for pin, value in pins.items():
                    print(f"  {pin}: {value}")
            else:
                print(f"  {pins}")

        time.sleep(1)

except KeyboardInterrupt:
    print("\nExiting...")