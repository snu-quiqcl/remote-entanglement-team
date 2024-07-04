# -*- coding: utf-8 -*-
"""
Created on Oct 22 21:10:12 2021
version = v0.01

@author: jhjeong32
E-mail: jhjeong32@snu.ac.kr
Tel. 010-9600-3392
"""
import ctypes
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
    

class PCI6216V(DAC_Abstract):
    """
    This DAC is commonly used in the lab for 16 channel DAC.
    You need to install drivers to make this board function properly.
        - Q:\Softwares\ADLINK DAQ\AllInOne_13A1\setup.exe
        
    Note that this board doesn't support read values from channels.
    """
    _dll_file = 'PCI-Dask64.dll'
    _is_opened = False
    _num_channel = 16
    _voltage_range = [-10, 10]
    _voltage_list = [0]*16
    
    def __init__(self, dll_path = ""):
        if not dll_path == "":
            self._dll_file = dll_path + '/'+ self._dll_file
        self._dll = ctypes.WinDLL(self._dll_file)
        self._initDll()
        
    def openDevice(self):
        """
        ::Register_Card::
           - Initializes the hardware and software states of a NuDAQ PCI-bus data acquisition card,
           - then returns a numeric card ID that corre- sponds to the initialized card.
           - Register_Card must be called before any other PCIS-DASK library functions can be called for a particular card.
           - The function initializes the card and variables internal to the PCIS-DASK library.
        """
        if self._is_opened:
            raise RuntimeError ("The device is alrady open!")
        else:
            self._card = self.Register_Card(1, 0)
            if self._card < 0:
                raise RuntimeError ("No DAC board has been found or already occupied.")
                return
            self._is_opened = True
        
    @requires_device_open
    def closeDevice(self):
        self._is_opened = False
        self.Release_Card(self._card)
        
    @requires_device_open
    def resetDevice(self):
        for ch in range(self._num_channel):
            self.setVoltage(ch, 0)
    
    @requires_device_open
    def setVoltage(self, channel, voltage):
        if channel >= self._num_channel:
            raise ValueError ("The number of channel that can be contrlled is (%d)" % self._num_channel)
        
        if (voltage < min(self._voltage_range) or voltage > max(self._voltage_range)):
            raise ValueError ("The voltage value cannot be out of the range (%d ~ %d)" % (self._voltage_range[0], self._voltage_range[1]))

        self.AO_VWriteChannel(self._card, channel, voltage)
        self._voltage_list[channel] = voltage


    @requires_device_open
    def readVoltage(self, channel):
        """
        This board doesn't support read values using dll.
        """
        if channel >= self._num_channel:
            raise ValueError ("The number of channel that can be contrlled is (%d)" % self._num_channel)
        
        return self._voltage_list[channel]
    
    def _initDll(self):
        self.Register_Card=self._dll.Register_Card
        self.Register_Card.argtypes = [ctypes.c_uint16, ctypes.c_uint16]
        self.Register_Card.restype = ctypes.c_int16
        
        self.AO_WriteChannel=self._dll.AO_WriteChannel
        self.AO_WriteChannel.argtypes = [ctypes.c_uint16, ctypes.c_uint16, ctypes.c_uint16]
        self.AO_WriteChannel.restype = ctypes.c_int16
        
        self.Release_Card=self._dll.Release_Card
        self.Release_Card.argtypes = [ctypes.c_uint16]
        self.Release_Card.restype = ctypes.c_int16
        
        self.AO_VWriteChannel=self._dll.AO_VWriteChannel
        self.AO_VWriteChannel.argtypes = [ctypes.c_uint16, ctypes.c_uint16, ctypes.c_double]
        self.AO_VWriteChannel.restype = ctypes.c_int16
        
if __name__ == "__main__":
    dac = DAC6208()