# -*- coding: utf-8 -*-
"""
Created on Thu Sep 16 20:29:03 2021

@author: QCP32
"""
import sys
from PyQt5.QtCore import QThread
from queue import Queue
import numpy as np

from multiprocessing import Process
from multiprocessing import Queue as mpQueue

"""
err_codes

0: couldn't open the device.
1: couldn't close the device.
2: Requested to change the setting while running.
3: Requested not availale option.
"""

class CCD_Controller(QThread):
    """
    A dummy/test class to give a guide to make a script.
    The controller class uses QThread class as a base, handling commands and the device is done by QThread.
    This avoids being delayed by the main thread's task.
    
    The logger decorate automatically record the exceptions when a bug happens.
    """
    _num_channel = 0
    _voltage_list = []
    _client_list = []
    _viewer_dict = {} # No compression for 16 bits.
    _status = "standby"
    
    def __init__(self, logger=None, device="Dummy_CCD"):
        super().__init__()
        self.logger = logger
        self.queue = Queue()
        self.device_type = device
        self._readConfig(device)
        self.acq_handler = AcquisitionHandler(self)
        
    def _readConfig(self, device):
        if device == "Dummy_CCD":
            sys.path.append("C:/Users/QCP32/Documents/GitHub/QtDevice_Server/Server/devices/CCD/Dummy/")
            from Dummy_CCD import DummyCCD as CCD
            
        self.ccd = CCD()
        
    
    def logger_decorator(func):
        """
        It writes logs when an exception happens.
        """
        def wrapper(self, *args):
            try:
                func(self, *args)
            except Exception as err:
                if not self.logger == None:
                    self.logger.error("An error ['%s'] occured while handling ['%s']." % (err, func.__name__))
                else:
                    print("An error ['%s'] occured while handling ['%s']." % (err, func.__name__))
        return wrapper
    
    @logger_decorator
    def openDevice(self):
        self.ccd.openDevice()
    
    @logger_decorator
    def closeDevice(self):
        self.ccd.closeDevice()

    @logger_decorator    
    def toWorkList(self, cmd):
        client = cmd[-1]
        if not client in self._client_list:
            self._client_list.append(client)
            
        self.queue.put(cmd)
        if not self.isRunning():
            self.start()
            print("Thread started")

    @logger_decorator          
    def run(self):
        while True:
            work = self.queue.get()
            self._status  = "running"
            # decompose the job
            work_type, command = work[:2]
            client = work[-1]    
    
            if work_type == "C":
                if command == "ON":
                    """
                    When a client is connected, opens the devcie and send voltage data to the client.
                    """
                    print("opening the device")
                    if not self.ccd._is_opened:
                        # Let the cliend know that the device is being initiated.
                        client.toMessageList(["D", "CCD", "INIT", []])
                        self.openDevice()
                        self.acq_handler.start()
                        
                    # Send current settings to the client
                    client.toMessageList(["D", "CCD", "HELO", ["G", self.ccd.gain,              # gain
                                                               "T", self.ccd.exposure_time,     # exposure time
                                                               "M", self.ccd.acquisition_mode]])# mode
                    
                elif command == "OFF":
                    """
                    When a client is disconnected, terminate the client and close the device if no client left.
                    """
                    if client in self._client_list:
                        self._client_list.remove(client)
                    if client in self._viewer_dict.keys():
                        self.toWorkList(["C", "ACQ", [0, 8], client])
                    # When there's no clients connected to the server. close the device.
                    if not len(self._client_list):
                        self.closeDevice()
                        self.toLog("info", "No client is being connected. closing the device.")
                        
                elif command == "ACQ":
                    """
                    It starts acqusition of the CCD when the data is 1. stops whtn it is 0.
                    """
                    run_flag, data_size = work[2]
                    
                    # Stop acqusition
                    if run_flag == 0:
                        if client in self._viewer_dict.keys(): # to avoid unexpected bugs
                            self._viewer_dict.pop(client)
                        if not len(self._viewer_dict):
                            self.stopAcquisition()
                        
                    # Start acquisition
                    else:
                        print(type(data_size))
                        if not (int(data_size) == 8 or int(data_size) == 16):
                            msg = ["D", "CCD", "ERR", ["ACQ", 3]]
                            self.informClients(msg, client)
                        else:
                            self._viewer_dict[client] = data_size
                            if not self.ccd._running_flag:
                                self.ccd.startAcquisition()
                    
                elif command == "SETG":
                    """
                    This sets gain of the CCD
                    """
                    gain = work[2]
                    self.ccd.gain = gain
                    
                    msg = ["D", "CCD", "SETG", [self.ccd.gain]]
                    self.informClients(msg, self._client_list)
                    
                elif command == "SETT":
                    """
                    This sets the exposure time of the CCD
                    """
                    exposure_time = work[2]
                    self.ccd.exposure_time = exposure_time
                    
                    msg = ["D", "CCD", "SETT", [self.ccd.exposure_time]]
                    self.informClients(msg, self._client_list)
                    
                elif command == "SETM":
                    """
                    It sets the acuqisiton mode.
                    Be aware that the CCD should not be running to handle the acqusition mode.
                    """
                    if self.ccd._running_flag:
                        msg = ["D", "CCD", "ERR", ["SETM", 2]]
                        self.informClients(msg, client)
                    else:
                        acquisition_mode = work[2]
                        if not acquisition_mode in self.ccd._avail_acquisition_modes:
                            msg = ["D", "CCD", "ERR", ["SETM", 3]]
                            self.informClients(msg, client)
                        else:
                            self.ccd.acquisition_mode = acquisition_mode
                            
                elif command == "SETC":
                    """
                    It controls the temperature of the EMCCD.
                    """
                    if self.device_type == "ThorCam":
                        msg = ["D", "CCD", "ERR", ["SETC", 3]] # controlling temperature is not available for ThorCam
                        self.informClients(msg, client)
                    else:
                        temp = work[2]
                        self.ccd.setCoolerTarget(temp)
                        msg = ["D", "CCD", "SETC", [self.ccd.target_temperature, self.ccd.temperature]]
                        self.informClients(msg, self._client_list)
                        
                elif command == "COOL":
                    """
                    It turns on and of the cooling
                    """
                    if self.device_type == "ThorCam":
                        msg = ["D", "CCD", "ERR", ["COOL", 3]] # controlling temperature is not available for ThorCam
                        self.informClients(msg, client)
                    else:
                        cooling_flag = work[2]
                        if cooling_flag:
                            self.ccd.coolerOn()
                        else:
                            self.ccd.coolerOff()
                            
                        msg = ["D", "CCD", "COOL", [cooling_flag]]
                        self.informClients(msg, self._client_list)
                
            elif work_type == "Q":
                if command == "RUN":
                    msg = ["D", "CCD", "RUN", [self.ccd._running_flag]]
                    self.informClients(msg, client)
                
                elif command == "SETG":
                    msg = ["D", "CCD", "SETG", [self.ccd.gain]]
                    self.informClients(msg, client)
                    
                elif command == "SETT":
                    msg = ["D", "CCD", "SETT", [self.ccd.exposure_time]]
                    self.informClients(msg, client)

                elif command == "SETM":
                    msg = ["D", "CCD", "SETM", [self.ccd.acquisition_mode]]
                    self.informClients(msg, client)
                    
                elif command == "SETC":
                    msg = ["D", "CCD", "SETC", [self.ccd.target_temperature, self.ccd.temperature]]
                    self.informClients(msg, client)
                    
                        
            else:
                self.toLog("critical", "Unknown work type (\"%s\") has been detected." % work_type)
            self._status = "standby"
            

    @logger_decorator
    def informClients(self, msg, client):
        if type(client) != list:
            client = [client]
        
        self.informing_msg = msg
        for clt in client:
            clt.toMessageList(msg)
            
        print("informing Done!")
         
    def toLog(self, log_type, log_content):
        if not self.logger == None:
            if log_type == "debug":
                self.logger.debug(log_content)
            elif log_type == "info":
                self.logger.info(log_content)
            elif log_type == "warning":
                self.logger.warning(log_content)
            elif log_type == "error":
                self.logger.error(log_content)
            else:
                self.logger.critical(log_content)
        else:
            print(log_type, log_content)


class AcquisitionHandler(Process):
    
    def __init__(self, proc_q=None, cons_q=None):
        super(AcquisitionHandler, self).__init__()
        self.proc_q = proc_q
        self.cons_q = cons_q
        
        self.roi_dict = {"x": [0, 512], "y": [0, 512]}
        self.flip_dict = {"v": False, "h": False}
        self.pooling_step = 2
        
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
            work = self.proc_q.get()
            
            sort, cmd, data = work
            
            if sort == "C":
                if cmd == "ROI":
                    roi_axis, roi_range = data
                    self.setROI(roi_axis, roi_range)
                    
                elif cmd == "FLIP":
                    flip_axis, flip_flag = data
                    self.setFlip(flip_axis, flip_flag)
                
            elif sort == "D":
                if cmd == "CCD":
                    processed_image = self.processData(data)
                    self.cons_q.put(processed_image)
                    
            
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
        
class DummyClient():
    
    def __init__(self):
        pass
    
    def toMessageList(self, msg):
        print(msg)
    
    
if __name__ == "__main__":
    proc_q = mpQueue()
    cons_q = mpQueue()
    AH = AcquisitionHandler(proc_q, cons_q)
    AH.start()