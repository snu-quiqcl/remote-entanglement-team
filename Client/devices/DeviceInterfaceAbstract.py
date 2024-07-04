# -*- coding: utf-8 -*-
"""
Created on Wed Sep 13 10:27:20 2023

@author: Junho Jeong
@Tel: 010-9600-3392
@email1: jhjeong32@snu.ac.kr
@mail2: bugbear128@gmail.com
"""
from PyQt5.QtCore import QThread
from queue import Queue
from datetime import datetime

class DeviceInterfaceAbstractBase:
    
    def openDevice(self):
        raise NotImplementedError
    
    def closeDevice(self):
        raise NotImplementedError
    
    def toWorkList(self, cmd):
        raise NotImplementedError
    
    def toSocket(self, msg):
        raise NotImplementedError
            
    def toGUI(self, msg):
        raise NotImplementedError


class DeviceInterfaceAbstract(DeviceInterfaceAbstractBase, QThread):

    def __init__(self, socket=None, gui=None, nick="default"):
        super().__init__()
        self._current_work = "standby"
        self.sck = socket
        self.que = Queue()
        self.gui= gui
        self.nick = nick
    
    def __call__(self):
        return self._current_work
    
    def run(self):
        """
        This run method is used by overriding the method within the QThread class.
        """
    
    def openDevice(self):
        if self._is_opened:
            raise RuntimeError ("The device is alrady open!")
        else:
            self.toSocket(["C", self.nick, "ON", []])
            
    def closeDevice(self):
        self.toSocket(["C", self.nick, "OFF", []])
        self._is_opened = False
        self.sig_update_callback.emit()
        
    def toWorkList(self, cmd):
        self.que.put(cmd)
        if not self.isRunning():
            self.start()
            
    def toSocket(self, msg=""):
        if not self.sck == None:
            self.sck.toMessageList(msg)
        else:
            print(msg)
            
    def toGUI(self, msg=""):
        if not self.gui == None:
            self.gui.toStatus(msg)
        else:
            print(msg)
            
            
class TestInterface(DeviceInterfaceAbstract):
    
    def run(self):
        while self.que.qsize():
            work = self.que.get()
            self._current_work = [work[2], datetime.now().strftime("%y-%m-%d %H:%H:%H")]
            print(work)
            
            
        self._current_work = "standby"
            
            
if __name__ == "__main__":
    test = TestInterface()
    test()
        