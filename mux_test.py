import time
import smbus
from collections import defaultdict

# Configuration
TCA9548A_ADDR = 0x70
BUS_NUMBER = 1
SCAN_DELAY = 0.1  # Increased delay for reliability


class RobustI2CScanner:
    def __init__(self, bus):
        self.bus = bus

    def scan_channel(self, mux_channel=None, retries=3):
        """Scan with error handling and retries"""
        found = []

        for attempt in range(retries):
            try:
                if mux_channel is not None:
                    self.bus.write_byte(TCA9548A_ADDR, 1 << mux_channel)
                    time.sleep(SCAN_DELAY)

                # Quick check if bus is responsive
                self.bus.write_quick(TCA9548A_ADDR)

                # Scan addresses
                for addr in range(0x03, 0x78):
                    try:
                        self.bus.write_quick(addr)
                        found.append(addr)
                        time.sleep(0.005)
                    except:
                        pass

                break  # Success - exit retry loop

            except Exception as e:
                print(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt == retries - 1:
                    raise
                time.sleep(0.5)

        # Reset mux if used
        if mux_channel is not None:
            try:
                self.bus.write_byte(TCA9548A_ADDR, 0x00)
            except:
                pass

        return found


# Initialize with error handling
try:
    bus = smbus.SMBus(BUS_NUMBER)
    scanner = RobustI2CScanner(bus)

    print("=== Starting Safe Scan ===")

    # 1. Verify mux is reachable
    try:
        bus.write_quick(TCA9548A_ADDR)
        print("✓ Mux detected at 0x70")
    except:
        print("× Mux not responding at 0x70")
        print("Check:")
        print("- Mux power (3.3V)")
        print("- I2C connections (SDA/SCL)")
        print("- Pull-up resistors (4.7kΩ)")
        exit()

    # 2. Scan each channel
    device_map = defaultdict(dict)

    for channel in range(8):
        try:
            print(f"Scanning channel {channel}...", end=' ')
            found = scanner.scan_channel(channel)

            if found:
                print(f"Found: {[hex(x) for x in found]}")
                for addr in found:
                    # Quick device verification
                    try:
                        bus.write_quick(addr)
                        device_map[channel][addr] = True
                        print(f"  ✓ Device responds at 0x{addr:02x}")
                    except:
                        print(f"  × No response at 0x{addr:02x}")
            else:
                print("No devices")

        except Exception as e:
            print(f"Scan failed: {str(e)}")
            continue

    if not device_map:
        print("No working devices found!")
        exit()

    # 3. Continuous reading only if devices found
    print("\n=== Starting Monitoring ===")
    try:
        while True:
            for channel, devices in device_map.items():
                try:
                    bus.write_byte(TCA9548A_ADDR, 1 << channel)
                    time.sleep(SCAN_DELAY)

                    for addr in devices:
                        # Implement your actual ADC reading here
                        print(f"Reading channel {channel}, device 0x{addr:02x}")
                        # Example: val = read_adc(bus, addr, pin)
                        # voltage = (val / 65535) * 3.3

                except Exception as e:
                    print(f"Channel {channel} error: {str(e)}")

            time.sleep(1)

    except KeyboardInterrupt:
        print("\nStopped by user")

finally:
    # Cleanup
    try:
        bus.write_byte(TCA9548A_ADDR, 0x00)
    except:
        pass
    bus.close()