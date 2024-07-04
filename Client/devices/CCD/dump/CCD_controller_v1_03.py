# -*- coding: utf-8 -*-
"""
Created on Wed Jul 14 00:30:47 2021

@author: CPO
"""
import os
import threading
import numpy as np
from datetime import datetime
from PIL import Image
from tifffile import tifffile
from QuIQCL_ThorCam_v0_01 import QuIQCL_ThorCam

class CCD_controller_Base:
    
    _image_buffer = None
    _buffer_size = 50
    _buffer_list = []
    
    _avail_acquisition_modes = ['single_scan', 'continuous_scan']
    
    _acquisition_mode = 'continuous_scan'
    _img_cnt = 0

class CCD_controller(CCD_controller_Base):
    
    def __init__(self):
        self._thor_cam = QuIQCL_ThorCam()
        
        # Get all the initial parameters from the device
        self._read_settings()
               
        self.acquisition_mode = self._acquisition_mode
        
        self._running_thread = threading.Thread(target = self._get_ccd_image, daemon=True)
        
        # pipes
        self._acq_event = threading.Event()
        
        print("Device standby.")
        
    def _read_settings(self):
        attr_list = self._thor_cam.__dir__()
        for  attr in attr_list:
            if "get_" in attr:
                func = getattr(self._thor_cam, attr)
                func()
    
    def open_device(self):
        self._thor_cam.cam_serial = self._thor_cam.get_cam_list()[0]
        self._thor_cam.open_cam()
        
        self.result_q.put(["D", "CCD", "OPEN", 1])
        
        print("Device opened!")
    
    def close_device(self):
        self._thor_cam.stop_camera()
        self._thor_cam.close_cam()
        if self._running_thread.is_alive():
            self._running_thread.join()
            
            self.result_q.put(["D", "CCD", ""])
    
    def run_device(self):
        self._img_cnt = 0
        self._thor_cam.play_camera()
        if not self._running_thread.is_alive():
            self._running_thread = threading.Thread(target = self._get_ccd_image)
            self._running_thread.start()
    
    def stop_device(self):
        self._thor_cam.stop_camera()
        if self._running_thread.is_alive():
            self._running_thread.join()
    
    @property
    def sensor_size(self):
        return self._thor_cam.sensor_size
    
    @property
    def gain(self):
        return self._thor_cam.gain
        
    @gain.setter
    def gain(self, value):
        self._thor_cam.set_gain(value)
        
    @property
    def exposure_time(self):
        return self._thor_cam.exposure_ms
    
    @exposure_time.setter
    def exposure_time(self, exp_time):
        self._thor_cam.set_exposure_ms(exp_time)
        
    @property
    def acquisition_mode(self):
        return self._acquisition_mode
    
    @acquisition_mode.setter
    def acquisition_mode(self, mode):
        assert isinstance(mode, str), "Acquisition mode should be a string."
        if not mode in self._avail_acquisition_modes:
            raise ValueError ("Acqusition mode should be either 'single_scan' or 'continuous_scan'.")
        self._acquisition_mode = mode
        
        if mode == "single_scan":
            self._thor_cam.set_trigger_count(self.trigger_count)
        else:
            self._thor_cam.set_trigger_count(0)
        
    @property
    def trigger_count(self):
        return self._thor_cam.trigger_count
    
    @trigger_count.setter
    def trigger_count(self, count):
        assert isinstance(count, int), "Trigger count should be an int."
        self._thor_cam.set_trigger_count(count)
        self._buffer_size = count
        
    
    #%% CCD Image
    @property
    def ccd_image(self):
        return self._image_buffer
    
    @ccd_image.setter
    def ccd_image(self, image):
        self._image_buffer = image
    
    #%% Thread
    def _get_ccd_image(self):
        while self._thor_cam.is_running():
            raw_data = self._thor_cam.read_frame()
            if raw_data == None:
                continue
            self._img_cnt += 1
            data_int = raw_data[0].astype(np.int16)
            data_arr = data_int.reshape(raw_data[2], order='F')
            
            self.ccd_image = np.copy(data_arr)
            # print('list_len:{} / buffer size: {}'.format(len(self._buffer_list), self._buffer_size))
            if not (len(self._buffer_list) < self._buffer_size):
                # print('big')
                while (len(self._buffer_list) >= self._buffer_size):
                    self._buffer_list.pop(0)
                    # print('popped')
            self._buffer_list.append(data_arr)
            # print('list_len:{}'.format(len(self._buffer_list)))
            
            if self._acquisition_mode == 'single_scan':
                if self._img_cnt+1 == self.trigger_count:
                    self._thor_cam.stop_camera()
            self.proc_q.put(["D", "CCD", self.ccd_image])
            self._acq_event.set()
            

if __name__ == "__main__":
    CCD = CCD_controller()