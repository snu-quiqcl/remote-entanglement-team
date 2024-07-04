# -*- coding: utf-8 -*-
"""
Created on Wed Sep 22 21:10:12 2021

@author: QCP32
"""
from DAC_base import DAC_Abstract

def requires_device_open(func):
    """Decorator that checks if the device is open.

    Raises:
        RuntimeError - the func is called before the device is open.
    """

    def wrapper(self, *args):
        if self._is_opened:
            return func(self, *args)
        else:
            raise RuntimeError('{} is called before the device is opened.'
                               .format(func.__name__))
    return wrapper
    

class DummyDAC(DAC_Abstract):
    
    _is_opened = False
    _num_channel = 16
    _voltage_range = [-15, 15]
    _voltage_list = [0]*16
    
    def __init__(self, serial_id = ""):
        self._serial_id = serial_id
        
    def openDevice(self):
        if self._is_opened:
            raise RuntimeError ("The device is alrady open!")
        else:
            self._is_opened = True
        
    @requires_device_open
    def closeDevice(self):
        self._is_opened = False
        
    @requires_device_open
    def resetDevice(self):
        self._voltage_list = [0]*16
    
    @requires_device_open
    def setVoltage(self, channel, voltage):
        if channel >= self._num_channel:
            raise ValueError ("The number of channel that can be contrlled is (%d)" % self._num_channel)
        
        if (voltage < min(self._voltage_range) or voltage > max(self._voltage_range)):
            raise ValueError ("The voltage value cannot be out of the range (%d ~ %d)" % (self._voltage_range[0], self._voltage_range[1]))
            
        self._voltage_list[channel] = voltage

    @requires_device_open
    def readVoltage(self, channel):
        if channel >= self._num_channel:
            raise ValueError ("The number of channel that can be contrlled is (%d)" % self._num_channel)
        
        return self._voltage_list[channel]