# -*- coding: utf-8 -*-
"""
Created on Tue Jan 18 20:24:45 2022

@author: QCP32
"""
import numpy as np
from multiprocessing import Process
from multiprocessing import Queue as mpQueue

class AcquisitionHandler(Process):
    
    def __init__(self, command_q=None, result_q=None, data_q=None, ccd_type="DUMMY"):
        super(AcquisitionHandler, self).__init__()
        self.command_q = command_q # gets commands from it
        self.result_q = result_q # gives the result to it
        self.data_q = data_q # It handles image data only
                
        self.roi_dict = {"x": [0, 512], "y": [0, 512]}
        self.flip_dict = {"v": False, "h": False}
        self.pooling_step = 2
        
        self.cam = None
        
        self._device_running = False
        
        # self.openDevice(ccd_type)
        
        
    def openDevice(self, ccd_type="CCD"):
        if ccd_type == "CCD":
            from CCD_controller_v1_03 import CCD_controller
            
        elif ccd_type == "EMCCD":
            pass
            
        elif ccd_type == "DUMMY":
            from Dummy.Dummy_CCD import CCD_controller
            
        else:
            raise ValueError ("You should specify the ccd type which is one of 'CCD' or 'EMCCD.'")
            
        self.cam = CCD_controller(data_q = self.data_q)
        
        self._device_opened = True
        self.result_q.put(["D", "OPEN", []])
        
        
    def setROI(self, roi_axis:str, roi_range:list):
        if not isinstance(roi_axis, str):
            raise ValueError ("The roi_axis must be a string.")
        if not isinstance(roi_range, list):
            raise ValueError ("The roi_range must be a list.")
            
        if not roi_axis in ["x", "y"]:
            raise ValueError ("The roi_axis must be 'x' or 'y'.")
            
        self.roi_dict[roi_axis] = roi_range
        
    def setPoolingStep(self, step):
        if not step in [2, 4]:
            raise ValueError ("The pooling step must be bettwen 2 or 4.")
        else:
            self.pooling_step = step
            
    def setFlip(self, flip_axis:str, flip_flag:bool):
        if not isinstance(flip_axis, str):
            raise ValueError ("The flip axis must be a string.")
        elif not flip_axis in ["x, y, h, v"]:
            raise ValueError ("The flip axis must be one of 'h', 'v', 'x', and 'y'.")
        else:
            if flip_axis == "x":
                flip_axis = "h"
            if flip_axis == "y":
                flip_axis = "v"
            self.flip_dict[flip_axis] = flip_flag
        
    def processData(self, data):
        processed_image = data[self.roi_dict["y"][0]:self.roi_dict["y"][1], 
                               self.roi_dict["x"][0]:self.roi_dict["x"][1]]
        if self.flip_dict["h"]:
            processed_image = np.flip(processed_image, 1)
        if self.flip_dict["v"]:
            processed_image = np.flip(processed_image, 0)
        
        return processed_image
        
    def run(self):
        while True:
            work = self.command_q.get()
            
            sort, cmd, data = work
            
            if sort == "C":
                if cmd == "ROI":
                    roi_axis, roi_range = data
                    self.setROI(roi_axis, roi_range)
                    self.result_q.put(["D", "ROI", self._dictToList(self.roi_dict)])
                    
                elif cmd == "FLIP":
                    flip_axis, flip_flag = data
                    self.setFlip(flip_axis, flip_flag)
                    self.result_q.put(["D", "FLIP", self._dictToList(self.flit_dict)])
                    
                elif cmd == "GAIN":
                    self.cam.gain = data[0]
                    self.result_q.put(["D", "GAIN", [self.cam.gain]])
                    
                elif cmd == "EXPT": # exposure_time
                    self.cam.exposure_time = data[0]
                    self.result_q.put(["D", "EXPT", [self.cam.exposure_time]])
                    
                elif cmd == "ACQM": # acqusition_mode
                    self.cam.acqusition_mode = data[0]
                    self.result_q.put(["D", "ACQM", [self.cam.acqusition_mode]])
                    
                elif cmd == "NTRG": # number of trigger
                    self.cam.trigger_count = data[0]
                    self.result_q.put(["D", "NTRG", [self.cam.trigger_count]])

                elif cmd == "RUN":
                    self.cam.startAcquisition()
                    self._device_running = True
                    self.result_q.put(["D", "RUN", [self._device_running]])
                    
                elif cmd == "STOP":
                    self.cam.stopAcquisition()
                    self._device_running = False
                    self.result_q.put(["D", "RUN", [self._device_running]])
            
            elif sort == "Q":
                if cmd == "ROI":
                    self.result_q.put(["A", "ROI", self._dictToList(self.roi_dict)])
                    
                elif cmd == "FLIP":
                    self.result_q.put(["A", "FLIP", self._dictToList(self.flip_dict)])
                    
                elif cmd == "GAIN":
                    self.result_q.put(["A", "GAIN", [self.gain]])
                    
                elif cmd == "EXPT":
                    self.result_q.put(["A", "EXPT", [self.cam.exposure_time]])
                    
                elif cmd == "ACQM":
                    self.result_q.put(["A", "ACQM", [self.cam.acqusition_mode]])
                    
                elif cmd == "NTRG":
                    self.result_q.put(["A", "NTRG", [self.cam.trigger_count]])
                    
                elif cmd == "RUN":
                    self.result_q.put(["A", "RUN", [self._device_running]])
            
            elif sort == "D":
                if cmd == "CCD":
                    processed_image = self.processData(data)
                    self.cons_q.put(processed_image)
                    
    def _dictToList(self, dict):
        return_list = []
        for key, val in dict.items():
            return_list.append(key)
            return_list.append(val)
        return return_list
            
            
    def average_pooling(self, array):
        x, y = array.shape
        new_x, new_y = x//self.pooling_step, y//self.pooling_step
        array = np.mean(array.reshape(new_x, self.pooling_step, new_y, self.pooling_step), axis = (1, 3))
        return array.astype(np.uint16)
    
    def maximum_pooling(self, array):
        x, y = array.shape
        new_x, new_y = x//self.pooling_step, y//self.pooling_step
        array = np.max(array.reshape(new_x, self.pooling_step, new_y, self.pooling_step), axis = (1, 3))
        return array.astype(np.uint16)
        
    
if __name__ == "__main__":
    command_q, result_q, data_q = mpQueue(), mpQueue(), mpQueue()
    ah = AcquisitionHandler(command_q, result_q, data_q, "DUMMY")
    ah.start()