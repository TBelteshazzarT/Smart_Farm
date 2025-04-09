import time
from i2c import Bus

ADC_DEFAULT_IIC_ADDR = 0x04
ADC_CHAN_NUM = 8

REG_RAW_DATA_START = 0x10
REG_VOL_START = 0x20
REG_RTO_START = 0x30
REG_SET_ADDR = 0xC0
COMMAND_CHANGE_ADDR = 0x55


class Pi_hat_adc():
    def __init__(self, bus_num=1, addr=ADC_DEFAULT_IIC_ADDR):
        self.bus = Bus(bus_num)
        self.addr = addr

    def set_i2c_address(self, new_addr):
        """Change the I2C address of the ADC (new firmware requires command byte 0x55)"""
        if new_addr < 0x08 or new_addr > 0x77:
            return False

        try:
            # New firmware expects [0x55, new_addr] at register 0xC0
            self.bus.write_i2c_block_data(self.addr, REG_SET_ADDR, [COMMAND_CHANGE_ADDR, new_addr])
            time.sleep(0.1)  # Allow time for flash write and reset
            self.addr = new_addr  # Update local address
            return True
        except:
            return False

    def get_all_adc_raw_data(self):
        """Get all 8 channels raw data (12-bit) - same as before"""
        array = []
        for i in range(ADC_CHAN_NUM):
            data = self.bus.read_i2c_block_data(self.addr, REG_RAW_DATA_START + i, 2)
            val = data[1] << 8 | data[0]  # Little-endian conversion
            array.append(val)
        return array

    def get_nchan_adc_raw_data(self, n):
        """Get single channel raw data"""
        if n < 0 or n >= ADC_CHAN_NUM:
            return 0
        data = self.bus.read_i2c_block_data(self.addr, REG_RAW_DATA_START + n, 2)
        return data[1] << 8 | data[0]

    def get_all_vol_milli_data(self):
        """Get all channels voltage (mV)"""
        array = []
        for i in range(ADC_CHAN_NUM):
            data = self.bus.read_i2c_block_data(self.addr, REG_VOL_START + i, 2)
            val = data[1] << 8 | data[0]
            array.append(val)
        return array

    def get_nchan_vol_milli_data(self, n):
        """Get single channel voltage"""
        if n < 0 or n >= ADC_CHAN_NUM:
            return 0
        data = self.bus.read_i2c_block_data(self.addr, REG_VOL_START + n, 2)
        return data[1] << 8 | data[0]

    def get_all_ratio_0_1_data(self):
        """Get all channels ratio (0.1%)"""
        array = []
        for i in range(ADC_CHAN_NUM):
            data = self.bus.read_i2c_block_data(self.addr, REG_RTO_START + i, 2)
            val = data[1] << 8 | data[0]
            array.append(val)
        return array

    def get_nchan_ratio_0_1_data(self, n):
        """Get single channel ratio"""
        if n < 0 or n >= ADC_CHAN_NUM:
            return 0
        data = self.bus.read_i2c_block_data(self.addr, REG_RTO_START + n, 2)
        return data[1] << 8 | data[0]


# Example usage
if __name__ == '__main__':
    adc = Pi_hat_adc()

    # Change address example (persistent)
    if adc.set_i2c_address(0x08):
        print("Address changed to 0x08")

    # Read all channels
    print("Raw ADC Values:", adc.get_all_adc_raw_data())
    print("Voltages (mV):", adc.get_all_vol_milli_data())
    print("Ratios (0.1%):", adc.get_all_ratio_0_1_data())