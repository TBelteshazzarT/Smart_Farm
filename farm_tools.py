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
DEFAULT_ADC_ADDR = 0x04
REG_SET_ADDR = 0xC0
ADC_CHANNELS = 4  # Each ADC has 4 moisture sensor channels
WATERING_DURATION = 30  # Default watering duration in seconds
MONITOR_INTERVAL = 300  # 5 minutes between cycles
MAX_PUMP_TIME = 300  # 5 minutes maximum pump runtime

class I2CDeviceManager:
    def __init__(self, config_file="i2c_devices.json"):
        self.devices = {}
        self.bus = Bus()
        self.config_file = config_file
        self.load_devices()

    def load_devices(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                devices = json.load(f)
                self.devices = {int(addr, 16): info for addr, info in devices.items()}

    def save_devices(self):
        with open(self.config_file, 'w') as f:
            devices = {hex(addr): info for addr, info in self.devices.items()}
            json.dump(devices, f, indent=4)

    def scan_bus(self):
        found_devices = []
        for address in range(0x03, 0x77):
            try:
                self.bus.write_quick(address)
                found_devices.append(address)
            except:
                pass
        return found_devices

    def change_stm32_address(self, current_addr, new_addr):
        """Use your ADC's specific address change protocol"""
        try:
            # Create a temporary ADC instance
            adc = Pi_hat_adc(addr=current_addr)
            success = adc.set_i2c_address(new_addr)

            if success:
                # Verify the change
                try:
                    test_adc = Pi_hat_adc(addr=new_addr)
                    test_adc.get_nchan_ratio_0_1_data(0)  # Simple read to verify
                    return True
                except:
                    print(f"Verification failed - device not responding at {hex(new_addr)}")
                    return False
            return False
        except Exception as e:
            print(f"Address change failed: {e}")
            return False

    def register_device(self, device_type, location, group):
        """
        New registration flow with STM32 address change support
        """
        print("\n=== ADC Registration ===")
        print("1. Connect ONE ADC to the system now")
        input("Press Enter when ready...")

        # Scan for devices
        found = self.scan_bus()
        if DEFAULT_ADC_ADDR not in found:
            print(f"No device found at default address {hex(DEFAULT_ADC_ADDR)}")
            print("Please check connections or ensure device is in default mode")
            return None

        # Find available address
        new_addr = self._find_available_address(found)
        if new_addr is None:
            print("Error: No available I2C addresses")
            return None

        # Attempt address change
        print(f"Attempting to change address from {hex(DEFAULT_ADC_ADDR)} to {hex(new_addr)}")
        if not self.change_stm32_address(DEFAULT_ADC_ADDR, new_addr):
            print("Address change failed - ensure STM32 firmware supports this feature")
            return None

        # Register the device
        return self._register_device_at_address(device_type, location, group, new_addr)

    def _find_available_address(self, used_addresses):
        for addr in range(DEFAULT_ADC_ADDR + 1, 0x77):
            if addr not in used_addresses:
                return addr
        return None

    def _register_device_at_address(self, device_type, location, group, address):
        self.devices[address] = {
            'type': device_type,
            'location': location,
            'group': group,
            'channels': [None] * ADC_CHANNELS,
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
        GPIO.setwarnings(False)

        # These will be set during setup
        self.water_pump_pin = None
        self.water_sensors = {}  # {'top': {'power': pin, 'read': pin}, 'bottom': {...}}
        self.valve_pins = {}  # {group_name: pin}
        self.group_thresholds = {}  # {group_name: threshold}

        # System state
        self.fill_in_progress = False
        self.last_watering_time = 0
        self.setup_complete = False

        # Initialize subsystems
        self.device_manager = I2CDeviceManager()
        self.group_manager = DeviceGroupManager(self.device_manager)
        self.adc = None  # Will be initialized per-device

    def get_adc_for_device(self, address):
        """Helper method to get ADC instance for a specific address"""
        return Pi_hat_adc(addr=address)

    def setup_pins(self):
        """Initial hardware setup"""
        print("\n=== Hardware Setup ===")

        # Water pump pin
        self.water_pump_pin = int(input("Enter GPIO pin for water pump: "))
        GPIO.setup(self.water_pump_pin, GPIO.OUT)
        GPIO.output(self.water_pump_pin, GPIO.LOW)

        # Water sensors
        print("\nWater Sensors Setup:")
        for sensor in ['top', 'bottom']:
            power_pin = int(input(f"Enter power pin for {sensor} sensor: "))
            read_pin = int(input(f"Enter read pin for {sensor} sensor: "))
            GPIO.setup(power_pin, GPIO.OUT)
            GPIO.setup(read_pin, GPIO.IN)
            GPIO.output(power_pin, GPIO.LOW)  # Start with sensors off
            self.water_sensors[sensor] = {'power': power_pin, 'read': read_pin}

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
        print("\nHardware setup complete!")

    def read_water_sensor(self, sensor):
        """Read a water sensor (turn on, read, turn off)"""
        if sensor not in self.water_sensors:
            return False

        # Turn on sensor
        GPIO.output(self.water_sensors[sensor]['power'], GPIO.HIGH)
        time.sleep(0.1)  # Allow sensor to stabilize

        # Read value
        value = GPIO.input(self.water_sensors[sensor]['read'])

        # Turn off sensor
        GPIO.output(self.water_sensors[sensor]['power'], GPIO.LOW)

        return value

    def check_water_level(self):
        """Check water level sensors"""
        return {
            'top_wet': self.read_water_sensor('top'),
            'bottom_wet': self.read_water_sensor('bottom')
        }

    def pump_cycle(self, watering_occurred):
        """Handle water tank filling if needed"""
        if not watering_occurred:
            return False

        print("\n[Pump Cycle] Checking water level...")
        start_time = time.time()

        # Only check bottom sensor if watering occurred
        bottom_wet = self.read_water_sensor('bottom')

        if not bottom_wet:
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
        print("\n[Monitor Cycle] Checking all sensors...")
        groups_to_water = {group: False for group in self.valve_pins.keys()}

        for group_name in self.valve_pins:
            moisture_readings = []
            for addr, device in self.device_manager.devices.items():
                if device.get('group') == group_name:
                    adc = self.get_adc_for_device(addr)
                    for channel in range(ADC_CHANNELS):
                        try:
                            moisture = adc.get_nchan_ratio_0_1_data(channel)
                            moisture_readings.append(moisture / 10)  # Convert 0.1% to %
                        except Exception as e:
                            print(f"Error reading channel {channel} on device {hex(addr)}: {e}")
                            moisture_readings.append(100)  # Default to "wet" if error

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

                # 1. Pump cycle (check water level if we watered last cycle)
                watering_occurred_last_cycle = (time.time() - self.last_watering_time) < MONITOR_INTERVAL
                self.pump_cycle(watering_occurred_last_cycle)

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
            for sensor in self.water_sensors.values():
                GPIO.output(sensor['power'], GPIO.LOW)


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
        """Updated ADC registration with STM32 address change support"""
        if not self.farm.setup_complete:
            print("Please complete setup first!")
            return

        print("\nAdding new ADC device")
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
            return

        # Set channel names
        for channel in range(ADC_CHANNELS):
            name = input(f"Enter name for channel {channel}: ")
            self.farm.device_manager.devices[assigned_addr]['channels'][channel] = name
        self.farm.device_manager.save_devices()
        print("ADC registration complete!")

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
                for channel in range(ADC_CHANNELS):
                    moisture = self.farm.adc.get_nchan_ratio_0_1_data(channel)
                    print("{:<10} {:<15} {:<10} {:<10.1f}%".format(
                        device['group'],
                        device['location'],
                        device['channels'][channel] or str(channel),
                        moisture / 10))