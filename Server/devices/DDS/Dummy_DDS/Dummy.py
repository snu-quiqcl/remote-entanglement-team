# -*- coding: utf-8 -*-
"""
Created on Tue Oct 26 10:13:54 2021

@author: QCP32
"""

class DummyDDS():
    
    def __init__(self, ser_num="", com_port=""):
        super().__init__()
        self._connected = False
                
    def openDevice(self):
        if self._connected:
            raise RuntimeError ("The device is already opened!")
        else:
            self._connected = True

    def closeDevice(self):
        self._connected = False
     
    def setCurrent(self, board, ch1, ch2, current):
        print("Set the current %d." % current)
  
    def setFrequency(self, board, ch1, ch2, freq_in_MHz):
        print("Set the frequency %.4f." % freq_in_MHz)
        
    def powerDown(self, board, ch1, ch2):
        print("Power downed.")
        
    def powerUp(self, board, ch1, ch2):
        print("Power up.")
        
if __name__ == "__main__":
    my_dds = DummyDDS(ser_num="")