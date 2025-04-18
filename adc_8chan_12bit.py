import time
from i2c import Bus

ADC_DEFAULT_IIC_ADDR = 0X04

ADC_CHAN_NUM = 8

REG_RAW_DATA_START = 0X10
REG_VOL_START = 0X20
REG_RTO_START = 0X30

REG_SET_ADDR = 0XC0


class Pi_hat_adc():
    def __init__(self, bus_num=1, addr=ADC_DEFAULT_IIC_ADDR):
        self.bus = Bus(bus_num)
        self.addr = addr

    # get all raw adc data,THe max value is 4095,cause it is 12 Bit ADC
    def get_all_adc_raw_data(self):
        array = []
        for i in range(ADC_CHAN_NUM):
            data = self.bus.read_i2c_block_data(self.addr, REG_RAW_DATA_START + i, 2)
            val = data[1] << 8 | data[0]
            array.append(val)
        return array

    def get_nchan_adc_raw_data(self, n):
        data = self.bus.read_i2c_block_data(self.addr, REG_RAW_DATA_START + n, 2)
        val = data[1] << 8 | data[0]
        return val

    # get all data with unit mv.
    def get_all_vol_milli_data(self):
        array = []
        for i in range(ADC_CHAN_NUM):
            data = self.bus.read_i2c_block_data(self.addr, REG_VOL_START + i, 2)
            val = data[1] << 8 | data[0]
            array.append(val)
        return array

    def get_nchan_vol_milli_data(self, n):
        data = self.bus.read_i2c_block_data(self.addr, REG_VOL_START + n, 2)
        val = data[1] << 8 | data[0]
        return val

    # get all data ratio,unit is 0.1%
    def get_all_ratio_0_1_data(self):
        array = []
        for i in range(ADC_CHAN_NUM):
            data = self.bus.read_i2c_block_data(self.addr, REG_RTO_START + i, 2)
            val = data[1] << 8 | data[0]
            array.append(val)
        return array

    def get_nchan_ratio_0_1_data(self, n):
        data = self.bus.read_i2c_block_data(self.addr, REG_RTO_START + n, 2)
        val = data[1] << 8 | data[0]
        return val


ADC = Pi_hat_adc()


def main():
    raw_data = ADC.get_all_adc_raw_data()
    vol_data = ADC.get_all_vol_milli_data()
    ratio_data = ADC.get_all_ratio_0_1_data()
    print("raw data for each channel:(1-8chan)(12 bit-max=4096):")
    print(raw_data)
    print("voltage for each channel:(unit:mv,max=3300mv):")
    print(vol_data)
    print("ratio for each channel(unit 0.1%,max=100.0%):")
    print(ratio_data)

    print(" ")
    print("NOTICE!!!:")
    print("The default setting of ADC PIN is floating_input.")
    print(" ")


if __name__ == '__main__':
    main()
