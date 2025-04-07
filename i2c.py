#!/usr/bin/env/ python

import smbus2 as smbus
from smbus2 import i2c_msg
class Bus:
   instance = None
   MRAA_I2C = 0

   def __init__(self, bus=1):
      if not self.instance:
         self.instance = smbus.SMBus(bus)
      self.bus = bus
      self.msg = i2c_msg

   def __getattr__(self, name):
      return getattr(self.instance, name)