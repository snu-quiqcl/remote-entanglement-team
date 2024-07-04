# -*- coding: utf-8 -*-
"""
Created on Thu Sep 16 20:29:03 2021

@author: QCP32
"""
from PyQt5.QtCore import QThread
from queue import Queue

class DummyDacController(QThread):
    """
    A dummy/test class to give a guide to make a script.
    The controller class uses QThread class as a base, handling commands and the device is done by QThread.
    This avoids being delayed by the main thread's task.
    
    The logger decorate automatically record the exceptions when a bug happens.
    """
    _num_channel = 0
    _voltage_list = []
    _client_list = []
    _status = "standby"
    
    def __init__(self, parent=None, config=None, logger=None, device="DummyDAC"):
        super().__init__()
        self.parent = parent
        self.cp = config
        self.logger = logger
        print("Dummy v0.02")
        self.queue = Queue()
        self._readConfig(device)
        
    def _readConfig(self, device):
        pass
    
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
        self.dac.openDevice()
        self.readSettings()
    
    @logger_decorator
    def closeDevice(self):
        self.dac.closeDevice()

    @logger_decorator
    def readSettings(self):
        self._num_channel = self.dac._num_channel
        self._voltage_list = self.dac._voltage_list

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
                if command == "SETV":
                    data = work[2]
                    self.updateVoltages(data)
                    # Let all clients know that the voltages are updated.
                    self.readVoltages([], self._client_list)
                    
                elif command == "ON":
                    """
                    When a client is connected, opens the devcie and send voltage data to the client.
                    """
                    print("opening the device")
                    if not self.dac._is_opened:
                        self.openDevice()
                        
                    client.toMessageList(["D", "DAC", "HELO", []])
                    self.readVoltages([], client)
                    
                elif command == "OFF":
                    """
                    When a client is disconnected, terminate the client and close the device if no client left.
                    """
                    if client in self._client_list:
                        self._client_list.remove(client)
                    # When there's no clients connected to the server. close the device.
                    if not len(self._client_list):
                        self.closeDevice()
                        self.toLog("info", "No client is being connected. closing the device.")
                
            elif work_type == "Q":
                if command == "SETV":
                    data = work[2]
                    self.readVoltages(data, client)
                        
            else:
                self.toLog("critical", "Unknown work type (\"%s\") has been detected." % work_type)
            self._status = "standby"
            
    @logger_decorator
    def updateVoltages(self, voltage_data):
        """
        voltage data example:
            "[0, 0.07, 1, 1.2, 5, -0.3, 7, -3]"
        """
        channel_list = voltage_data[::2]
        voltage_list = voltage_data[1::2]
        
        for idx, channel in enumerate(channel_list):
            voltage = voltage_list[idx]
            
            self.dac.setVoltage(channel, voltage)
            
    @logger_decorator
    def readVoltages(self, voltage_data, client):
        """
        voltage data example:
            "[0, 0.07, 1, 1.2, 5, -0.3, 7, -3]"
        """
        
        # When the list is empty, scans all channels
        if not len(voltage_data):
            channel_list = range(self._num_channel)
        else:
            channel_list = voltage_data[::2]

            
        data = []
        
        for channel in channel_list:
            voltage = self._voltage_list[channel]
            data.append(channel)
            data.append(voltage)
            
        message = ["D", "DAC", "SETV", data]
        self.informClients(message, client)
                     
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

        
class DummyClient():
    
    def __init__(self):
        pass
    
    def toMessageList(self, msg):
        print(msg)
    