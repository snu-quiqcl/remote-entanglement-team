# -*- coding: utf-8 -*-
"""
Created on Wed Jul 14 00:30:47 2021

@author: QCP32
"""
import time
import threading
import numpy as np


class CCD_controller_Base:
    
    _image_buffer = None
    _buffer_size = 50
    _buffer_list = []
    
    _avail_acquisition_modes = ['single_scan', 'continuous_scan']
    
    _acquisition_mode = 'continuous_scan'
    _img_cnt = 0
    _running_flag = False
    _is_opened = False

class DummyCCD(CCD_controller_Base):
    
    def __init__(self):               
        self.acquisition_mode = self._acquisition_mode
        self._running_thread = threading.Thread(target = self._get_ccd_image)
        self._acq_event = threading.Event()
        print("Dummy CCD v0.1")
        
        self._gain = 20
        self._temperature = 30
        self._sensor_size = (1392, 1040)

        self._exposure_time = 0.1
        self._trigger_count = 0 # continuous scan
        
        self.cooler = CoolerHandler(self)
            
    def openDevice(self):
        if not self._is_opened:
            self._is_opened = True
            self.cooler.start()
            time.sleep(2)
            print("CCD has been opened.")
            
        else:
            raise RuntimeError ("The device is already opened!")
    
    def closeDevice(self):
        if self._is_opened:
            if self._running_flag:
                self.stopAcquisition()
            self._is_opened = False
            print("CCD has been closed.")
        else:
            raise RuntimeError ("Tried to close the device before it is opened.")
        
    def startAcquisition(self):
        if not self._is_opened:
            raise RuntimeError ("The device should be opened beforehand.")
        else:
            self._img_cnt = 0
            self._running_flag = True
            if not self._running_thread.is_alive():
                self._running_thread = threading.Thread(target = self._get_ccd_image)
                self._running_thread.start()
            print("Started Acqusition")
    
    def stopAcquisition(self):
        if not self._running_flag:
            raise RuntimeError ("Tried to stop acqusition before it is started.")
        else:
            self._running_flag = False
            if self._running_thread.is_alive():
                self._running_thread.join()
            print("Stopped Acqusition")
    
    @property
    def sensor_size(self):
        return self._sensor_size
    
    @property
    def gain(self):
        return self._gain
        
    @gain.setter
    def gain(self, value):
        self._gain = int(max(0, min(value, 1000)))
        
    @property
    def exposure_time(self):
        return self._exposure_time
    
    @exposure_time.setter
    def exposure_time(self, exp_time):
        self._exposure_time = (max(0.001, min(exp_time, 10)))
        
    @property
    def acquisition_mode(self):
        return self._acquisition_mode
    
    @acquisition_mode.setter
    def acquisition_mode(self, mode):
        assert isinstance(mode, str), "Acquisition mode should be a string."
        if not mode in self._avail_acquisition_modes:
            raise ValueError ("Acqusition mode should be either 'single_scan' or 'continuous_scan'.")
        self._acquisition_mode = mode
        
    @property
    def trigger_count(self):
        return self._trigger_count
    
    @trigger_count.setter
    def trigger_count(self, count):
        assert isinstance(count, int), "Trigger count should be an int."
        self._trigger_count = count
        self._buffer_size = count
        
    @property
    def temperature(self):
        return self._temperature
    
    @temperature.setter
    def temperature(self, temp):
        self._temperature = temp
        
    @property
    def target_temperature(self):
        return self._target
    
    @target_temperature.setter
    def target_temperature(self, value):
        self._target = max(-80, min(30, value))
        
    def coolerOn(self, target=-60):
        self.target_temperature = target
        self.cooler.coolerOn()
        
    def coolerOff(self):
        self.cooler.coolerOff()
    
    #%% CCD Image
    @property
    def ccd_image(self):
        return self._image_buffer
    
    @ccd_image.setter
    def ccd_image(self, image):
        self._image_buffer = image
    
    #%% Thread
    def _get_ccd_image(self):
        while self._running_flag:
            time.sleep(self.exposure_time + 0.1)
            self._img_cnt += 1
            data_arr = np.random.randint(380 + self.temperature,
                                         380 + self.temperature + 45*self.gain,
                                         self.sensor_size, dtype=np.uint16)
            
            self.ccd_image = np.copy(data_arr)
            if not (len(self._buffer_list) < self._buffer_size):
                while (len(self._buffer_list) >= self._buffer_size):
                    self._buffer_list.pop(0)
            self._buffer_list.append(data_arr)
            
            if self._acquisition_mode == 'single_scan':
                if self._img_cnt+1 == self.trigger_count:
                    self.stopAcquisition()
            self._acq_event.set()
            time.sleep(5)

class CoolerHandler(object):
    
    def __init__(self, parent):
        self.controller = parent
        self._cooler_flag = False
        
        
    def coolerOn(self):
        self._cooler_flag = True
    
    def coolerOff(self):
        self._cooler_flag = False
        
    def start(self):
        self.t1 = threading.Thread(target=self._changeTemperature)
        self.t1.start()
        
    def _changeTemperature(self):
        while self.controller._is_opened:
            time.sleep(1)
            curr_temp = self.controller.temperature
            if self._cooler_flag:
                target = self.controller.target_temperature
            else:
                target = 30
                
            if abs(target - curr_temp) < 0.01:
                self.controller.temperature = target
            else:
                self.controller.temperature = curr_temp + 0.5*(np.log(abs(target - curr_temp) + 1)) * (-1)**((target - curr_temp) < 0)
                
        

if __name__ == "__main__":
    CCD = DummyCCD()
