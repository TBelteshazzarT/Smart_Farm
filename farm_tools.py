#!/usr/bin/env python

import time
import json
import os
import smbus2
import RPi.GPIO as GPIO
from smbus2 import i2c_msg
from adc_8chan_12bit import Pi_hat_adc
from i2c import Bus

# Constants
ADC_DEFAULT_IIC_ADDR = 0x04
REG_SET_ADDR = 0xC0
Moisture_Channels = [0,2,4,6]  # Each ADC has 4 moisture sensor channels
WATERING_DURATION = 30  # Default watering duration in seconds
MONITOR_INTERVAL = 300  # 5 minutes between cycles
MAX_PUMP_TIME = 300  # 5 minutes maximum pump runtime
CONFIG_FILE = "farm_config.json"  # Configuration file for pin settings

# Water sensor ADC channels
TOP_WATER_SENSOR_ADC_CHANNEL = 5  # Channel
BOTTOM_WATER_SENSOR_ADC_CHANNEL = 7  # Channel
WATER_SENSOR_THRESHOLD = 1000  # Threshold for wet/dry detection (adjust as needed)


class I2CDeviceManager:
    def __init__(self, config_file="i2c_devices.json"):
        self.devices = {}  # {address: {'type': str, 'location': str, 'group': str}}
        self.bus = Bus()
        self.config_file = config_file
        self.load_devices()

    def load_devices(self):
        """Load registered devices from JSON file"""
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                devices = json.load(f)
                self.devices = {int(addr, 16): info for addr, info in devices.items()}

    def save_devices(self):
        """Save registered devices to JSON file"""
        with open(self.config_file, 'w') as f:
            devices = {hex(addr): info for addr, info in self.devices.items()}
            json.dump(devices, f, indent=4)

    def scan_bus(self):
        """Scan I2C bus and detect all connected devices"""
        found_devices = []
        for address in range(0x03, 0x77):
            try:
                self.bus.write_quick(address)
                found_devices.append(address)
            except:
                pass
        return found_devices

    def verify_device_address(self, expected_addr):
        """Check if device is active at given address"""
        try:
            temp_bus = smbus2.SMBus(self.bus.bus)
            temp_bus.write_quick(expected_addr)
            return True
        except:
            return False

    def register_device(self, device_type, location, group, default_addr=0x04):
        """Enhanced device registration with proper EEPROM handling"""
        found = self.scan_bus()
        return self._register_device_at_address(device_type, location, group, default_addr)

    def _find_available_address(self, used_addresses, default_addr):
        """Find next available address"""
        for addr in range(default_addr + 1, 0x77):
            if addr not in used_addresses:
                return addr
        return None

    def _register_device_at_address(self, device_type, location, group, address):
        """Helper to register a device at specific address"""
        self.devices[address] = {
            'type': device_type,
            'location': location,
            'group': group,
            'channels': Moisture_Channels,
            'last_seen': time.time()
        }
        self.save_devices()
        print(f"Device successfully registered at {hex(address)}")
        return address


class DeviceGroupManager:
    def __init__(self, device_manager):
        self.device_manager = device_manager
        self.groups = {}  # {group_name: {'devices': [address1, address2], 'valve_pin': int}}

    def create_group(self, group_name, valve_pin):
        self.groups[group_name] = {'devices': [], 'valve_pin': valve_pin}
        GPIO.setup(valve_pin, GPIO.OUT)
        GPIO.output(valve_pin, GPIO.LOW)

    def add_to_group(self, group_name, address):
        if group_name in self.groups and address in self.device_manager.devices:
            self.groups[group_name]['devices'].append(address)
            self.device_manager.devices[address]['group'] = group_name
            self.device_manager.save_devices()

    def get_group_valve_pin(self, group_name):
        return self.groups.get(group_name, {}).get('valve_pin')


class SmartFarmSystem:
    def __init__(self):
        # Initialize GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(True)

        # These will be set during setup
        self.water_pump_pin = None
        self.valve_pins = {}  # {group_name: pin}
        self.group_thresholds = {}  # {group_name: threshold}

        # System state
        self.fill_in_progress = False
        self.last_watering_time = 0
        self.setup_complete = False

        # Initialize subsystems
        self.device_manager = I2CDeviceManager()
        self.group_manager = DeviceGroupManager(self.device_manager)
        self.adc = Pi_hat_adc()

        # Try to load configuration if file exists
        self.load_config()

    def calibrate_moisture_reading(self, value):
        """Converts the raw value from the moisture sensor into a percent such that 100% is fully wet"""
        return ((250-(value-370))/250)*100

    def load_config(self):
        """Load pin configuration from file if it exists"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)

                    # Load water pump pin
                    self.water_pump_pin = config.get('water_pump_pin')
                    if self.water_pump_pin is not None:
                        GPIO.setup(self.water_pump_pin, GPIO.OUT)
                        GPIO.output(self.water_pump_pin, GPIO.LOW)



                    # Load groups
                    self.valve_pins = config.get('valve_pins', {})
                    self.group_thresholds = config.get('group_thresholds', {})

                    # Initialize group manager with loaded groups
                    for group_name, pin in self.valve_pins.items():
                        self.group_manager.create_group(group_name, pin)
                        threshold = self.group_thresholds.get(group_name, 50.0)
                        self.group_manager.add_to_group(group_name, None)  # Devices will be added separately

                    self.setup_complete = True
                    print("Configuration loaded successfully from file")

            except Exception as e:
                print(f"Error loading configuration: {e}")
                self.setup_complete = False

    def save_config(self):
        """Save current pin configuration to file"""
        config = {
            'water_pump_pin': self.water_pump_pin,
            'valve_pins': self.valve_pins,
            'group_thresholds': self.group_thresholds
        }

        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=4)
            print("Configuration saved successfully")
        except Exception as e:
            print(f"Error saving configuration: {e}")

    def setup_pins(self):
        """Initial hardware setup"""
        print("\n=== Hardware Setup ===")

        # Water pump pin
        self.water_pump_pin = int(input("Enter GPIO pin for water pump: "))
        GPIO.setup(self.water_pump_pin, GPIO.OUT)
        GPIO.output(self.water_pump_pin, GPIO.LOW)

        # Groups and valves
        print("\nGroup Setup:")
        while True:
            group_name = input("Enter group name (or 'done' to finish): ")
            if group_name.lower() == 'done':
                break
            valve_pin = int(input(f"Enter valve pin for group '{group_name}': "))
            threshold = float(input(f"Enter moisture threshold (0-100%) for '{group_name}': "))

            GPIO.setup(valve_pin, GPIO.OUT)
            GPIO.output(valve_pin, GPIO.LOW)
            self.valve_pins[group_name] = valve_pin
            self.group_thresholds[group_name] = threshold
            self.group_manager.create_group(group_name, valve_pin)

        self.setup_complete = True
        self.save_config()  # Save configuration after setup
        print("\nHardware setup complete and saved to configuration!")

    def read_water_sensor(self, sensor):
        """Read a water sensor (turn on, read via ADC, turn off)"""
        # Determine ADC channel
        channel = TOP_WATER_SENSOR_ADC_CHANNEL if sensor == 'top' else BOTTOM_WATER_SENSOR_ADC_CHANNEL

        # Read value from ADC
        try:
            # Get raw ADC value (0-4095 for 12-bit ADC)
            raw_value = self.adc.get_nchan_adc_raw_data(channel)
            # Convert to boolean (wet/dry)
            value = raw_value > WATER_SENSOR_THRESHOLD
        except Exception as e:
            print(f"Error reading ADC channel {channel}: {e}")
            value = False
        return value

    def check_water_level(self):
        """Check water level sensors"""
        return {
            'top_wet': self.read_water_sensor('top'),
            'bottom_wet': self.read_water_sensor('bottom')
        }

    def pump_cycle(self, bottom_sensor):
        """Handle water tank filling if needed"""
        print(bottom_sensor)
        if bottom_sensor:
            return False

        print("\n[Pump Cycle] Checking water level...")
        start_time = time.time()


        if not bottom_sensor:
            print("Water level low - starting pump")
            GPIO.output(self.water_pump_pin, GPIO.HIGH)
            self.fill_in_progress = True

            # Monitor top sensor until full or timeout
            while time.time() - start_time < MAX_PUMP_TIME:
                top_wet = self.read_water_sensor('top')
                if top_wet:
                    GPIO.output(self.water_pump_pin, GPIO.LOW)
                    self.fill_in_progress = False
                    print("Tank filled")
                    return True
                time.sleep(1)

            # Timeout reached
            GPIO.output(self.water_pump_pin, GPIO.LOW)
            print("Pump timeout reached - stopping pump")
            return False
        return False

    def monitor_cycle(self):
        """Check all sensors and determine which groups need watering"""
        print("\n[Monitor Cycle] Checking all sensors...")
        groups_to_water = {group: False for group in self.valve_pins.keys()}

        for group_name in self.valve_pins:
            # Get all moisture readings for this group
            moisture_readings = []
            for addr, device in self.device_manager.devices.items():
                if device.get('group') == group_name:
                    for channel in Moisture_Channels:
                        moisture = self.adc.get_nchan_ratio_0_1_data(channel)
                        moisture_readings.append(self.calibrate_moisture_reading(moisture))  # Calibration

            if moisture_readings:
                avg_moisture = sum(moisture_readings) / len(moisture_readings)
                threshold = self.group_thresholds[group_name]
                groups_to_water[group_name] = avg_moisture < threshold
                print(
                    f"Group '{group_name}': Avg moisture {avg_moisture:.1f}% (Threshold: {threshold}%) - {'WATER' if groups_to_water[group_name] else 'OK'}")

        return groups_to_water

    def watering_cycle(self, groups_to_water):
        """Water groups that need it"""
        watering_occurred = False

        for group_name, should_water in groups_to_water.items():
            if should_water:
                print(f"\n[Watering Cycle] Watering group '{group_name}' for {WATERING_DURATION} seconds")
                GPIO.output(self.valve_pins[group_name], GPIO.HIGH)
                GPIO.output(self.water_pump_pin, GPIO.HIGH)

                start_time = time.time()
                while time.time() - start_time < WATERING_DURATION:
                    # Check if tank is empty during watering
                    if not self.read_water_sensor('bottom'):
                        print("Water tank empty during watering! Stopping...")
                        break
                    time.sleep(1)

                GPIO.output(self.valve_pins[group_name], GPIO.LOW)
                GPIO.output(self.water_pump_pin, GPIO.LOW)
                watering_occurred = True
                self.last_watering_time = time.time()

        return watering_occurred

    def main_loop(self):
        """Main control loop with 3 cycles"""
        if not self.setup_complete:
            print("Please complete setup first!")
            return

        try:
            while True:
                print("\n=== Starting New Cycle ===")

                # 1. Pump cycle
                self.pump_cycle(self.read_water_sensor('bottom'))

                # 2. Monitoring cycle
                groups_to_water = self.monitor_cycle()

                # 3. Watering cycle
                watering_occurred = self.watering_cycle(groups_to_water)

                print(f"\nCycle complete. Waiting {MONITOR_INTERVAL // 60} minutes...")
                time.sleep(MONITOR_INTERVAL)

        except KeyboardInterrupt:
            print("\nStopping system...")
            # Turn off all outputs
            GPIO.output(self.water_pump_pin, GPIO.LOW)
            for pin in self.valve_pins.values():
                GPIO.output(pin, GPIO.LOW)


class SmartFarmUI:
    def __init__(self, farm_system):
        self.farm = farm_system

    def show_main_menu(self):
        print("\nSmart Farm Control System")
        print("1. Initial Setup")
        print("2. Add ADC Device")
        print("3. View System Status")
        print("4. Start Main Loop")
        print("5. Exit")

    def run(self):
        while True:
            self.show_main_menu()
            choice = input("Enter your choice: ")

            if choice == '1':
                self.farm.setup_pins()
            elif choice == '2':
                self.add_adc_device()
            elif choice == '3':
                self.view_system_status()
            elif choice == '4':
                if not self.farm.setup_complete:
                    print("Please complete setup first!")
                else:
                    self.farm.main_loop()
            elif choice == '5':
                self.farm.device_manager.save_devices()
                GPIO.cleanup()
                print("Goodbye!")
                break
            else:
                print("Invalid choice")

    def add_adc_device(self):
        """Add a new ADC device with group assignment"""
        if not self.farm.setup_complete:
            print("Please complete setup first!")
            return

        print("\nAdding new ADC device")

        found = self.farm.device_manager.scan_bus()
        registered = set(self.farm.device_manager.devices.keys())
        new_devices = [addr for addr in found if addr not in registered]

        if not new_devices:
            print("No new ADC devices found. Please connect one and try again.")
            return

        print(f"Found new device at address {hex(new_devices[0])}")

        location = input("Enter location/description for this ADC: ")

        print("\nAvailable groups:")
        groups = list(self.farm.valve_pins.keys())
        for i, group in enumerate(groups, 1):
            print(f"{i}. {group}")

        try:
            group_choice = int(input("Select group for this ADC: ")) - 1
            group_name = groups[group_choice]
        except (ValueError, IndexError):
            print("Invalid group selection")
            return

        assigned_addr = self.farm.device_manager.register_device(
            "ADC", location, group_name)

        if assigned_addr is None:
            print("Device registration failed")
            return

        # Only proceed with channel naming if registration was successful (disabled)
        '''for channel in Moisture_Channels:
            name = input(f"Enter name for channel {channel} (e.g., 'North Bed'): ")
            self.farm.device_manager.devices[assigned_addr]['channels'][channel] = name'''
        self.farm.device_manager.save_devices()
        print("Device saved successfully")

    def view_system_status(self):
        """Display current system status"""
        if not self.farm.setup_complete:
            print("System not yet setup")
            return

        print("\n=== System Status ===")

        # Water tank status
        water_status = self.farm.check_water_level()
        print("\nWater Tank:")
        print(f"Top sensor: {'Wet' if water_status['top_wet'] else 'Dry'}")
        print(f"Bottom sensor: {'Wet' if water_status['bottom_wet'] else 'Dry'}")
        print(f"Pump status: {'ON' if self.farm.fill_in_progress else 'OFF'}")

        # Groups and valves
        print("\nIrrigation Groups:")
        for group, pin in self.farm.valve_pins.items():
            print(f"{group}: Valve pin {pin}, Threshold: {self.farm.group_thresholds[group]}%")

        # Moisture data
        print("\nMoisture Sensor Data:")
        print("{:<10} {:<15} {:<10} {:<10}".format(
            "Group", "Location", "Channel", "Moisture"))
        print("-" * 45)

        for addr, device in self.farm.device_manager.devices.items():
            if device['type'] == 'ADC':
                for channel in Moisture_Channels:
                    moisture = self.farm.adc.get_nchan_ratio_0_1_data(channel)
                    print("{:<10} {:<15} {:<10} {:<10.1f}%".format(
                        device['group'],
                        device['location'],
                        str(channel),
                        self.farm.calibrate_moisture_reading(moisture))) # calibrated


if __name__ == "__main__":
    farm = SmartFarmSystem()
    ui = SmartFarmUI(farm)
    ui.run()