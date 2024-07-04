# -*- coding: utf-8 -*-
"""
Created on Wed Oct 13 14:00:26 2021

@author: QC109_4
"""

import serial
import time
from serial.tools.list_ports import comports

def requires_device_open(func):
    
    def wrapper(self, *args):
        if self._is_opened:
            return func(self, *args)        
        else:
            raise RuntimeError('{} is called before the device is opened.'.format(func.__name__))
      
    return wrapper

class GDM8341():
    
    adc = None
    _device_candidate = {}
    _is_opened = False
    
    def __init__(self):
        self._init = True 
#        self.scanDevice()
#        assert len(self._device_candidate), "No GDM8341 has been found"
#        
#    def scanDevice(self):
#        for dev in comports():
#            if "GDM834" in dev.description:
#                serial_number = dev.serial_number               
#                com_port      = dev.device
#                description   = dev.description
#                self._device_candidate[serial_number] = {"desc": description, "com": com_port}    
                
    def openDevice(self, com_port=None):     
        self._is_opened = True
        print("The device successfully opened!")
        
    @requires_device_open
    def closeDevice(self):
        self._is_opened = False
        print("The device successfully closed!")
    
    @requires_device_open
    def goRemote(self):
        self._is_remote = True
    
    @requires_device_open
    def goLocal(self):
        self._is_remote = False
        
    @requires_device_open
    def readVoltage(self, vol_type = "DC"):
#        self.writeCommand('CONF:CURR:%s\n' % vol_type)          
#        dc_voltage = float(self.queryValue('MEAS:VOLT:%s?\n' % vol_type))
        return 1
                                                                    
    @requires_device_open
    def readCurrent(self, cur_type = "DC"):
#        self.writeCommand('CONF:CURR:%s\n' % cur_type)
#        dc_current = float(self.queryValue('MEAS:CURR:%s?\n' % cur_type))
        return 2
    
    @requires_device_open
    def readResistance(self):
#        self.writeCommand('CONF:RES\n')
#        resistance = float(self.queryValue('MEAS:RES?\n'))
        return 3
    
    @requires_device_open
    def readFrequency(self):
#        self.writeCommand('CONF:FREQ\n')
#        frequency = float(self.queryValue('MEAS:FREQ?\n'))
        return 4
    
    @requires_device_open
    def writeCommand(self, command):
        if command[-1] != '\n':       
            command += '\n'           
        self.adc.write(command.encode()) 
        
    @requires_device_open
    def queryValue(self, command):
        self.writeCommand(command)
        line = ""
        while not len(line):    
            time.sleep(0.1)
            line = self.adc.readline().decode()[:-2] 
        return line
    
    
if __name__ == "__main__":
    gdm = GDM8341()
        
        
        
    
