# -*- coding: utf-8 -*-
"""
Created on Mon Aug 22 10:27:50 2022

@author: Junho Jeong

"""
from PyQt5.QtCore import QThread, pyqtSignal
from queue import Queue
version = "3.1"


class RemoteMotorHandler(QThread):
    """
    This class is an API-like class that can easily handle the motor with Qt classes.    
    This handler class handles the motor with a thread and the controller controls all the motors but in signal based operations.
    """
    _sig_motor_initialized = pyqtSignal(str)
    _sig_motor_error = pyqtSignal(str)
    _sig_motor_move_done = pyqtSignal(str, float)
    _sig_motor_changed_position = pyqtSignal(str, float)
    _sig_motor_homed = pyqtSignal(str) 
    _sig_motors_changed_status = pyqtSignal(str, str)
    
    def __init__(self, controller=None, owner=None, dev_type="Dummy", nick="motor", socket=None):  # cp is ConfigParser class
        super().__init__()
        self._motor = None
        self._position = 0
        self._status = "closed"
        self._nickname = "motor"
        self._owner = None
        self._is_opened = False
        
        self.parent = controller
        self.dev_type = dev_type
        
        self.owner = owner
        self.nickname = nick
        self.target = 0
        self.queue = Queue()
        self.socket = socket
        
        self.serial = "remote"
                
        if self.socket.socket.isOpen():
            self.updateStatus()
        
    @property
    def owner(self):
        return self._owner
    
    @owner.setter
    def owner(self, owner):
        if not owner == None:
            self._owner = owner
        else:
            print("The serial of the motor cannot be None.")
            
    def info(self):
        return {"owner": self.owner,
                "position": self.position,
                "status": self._status,
                "type": self.dev_type}
           
    @property
    def nickname(self):
        return self._nickname
    
    @nickname.setter
    def nickname(self, nick):
        self._nickname = nick
        
    @property
    def position(self):
        return self._position
        
    @position.setter
    def position(self, pos):
        self._position = pos
        
    @property
    def status(self):
        return self._status
    
    @status.setter
    def status(self, status):
        self._status = status
        if not (status == "closed" or status == "initiating"):
            if not self._is_opened: self._is_opened = True
        self._sig_motors_changed_status.emit(self.nickname, status)
        
    def updateStatus(self):
        msg = ["C", "%s:MOTORS" % self.owner, "CON", [self.nickname]]
        self.toSocket(msg)
        
    def getPosition(self):
        return self.position
    
    def setTargetPosition(self, target):
        self._target = target
        
    def openDevice(self):
        """
        If the force flag is true even if the device is already opened, it will be restarted.
        """
        msg = ["C", "%s:MOTORS" % self.owner, "OPEN", [self.nickname]]
        self.toSocket(msg)
        
    def moveToPosition(self, target_position):
        self.setTargetPosition(target_position)
        msg = ["C", "%s:MOTORS" % self.owner, "MOVE", [self.nickname, target_position]]
        self.toSocket(msg)
        
    def forceHome(self):
        msg = ["C", "%s:MOTORS" % self.owner, "HOME", [self.nickname]]
        self.toSocket(msg)
           
    def closeDevice(self):
        msg = ["C", "%s:MOTORS" % self.owner, "CLOSE", [self.nickname]]
        self.toSocket(msg)
        
    def toSocket(self, msg):
        self.socket.toMessageList(msg)
            
    def toWorkList(self, cmd):
        self.queue.put(cmd)
        if not self.isRunning():
            self.start()
            
    def run(self):
        while self.queue.qsize():
            work = self.queue.get()
            
            if work == "O": # Open device
                self.openDevice()
                
            elif work == "M": # Move position
                self.moveToPosition(self._target)
                                
            elif work == "H": # Homing
                self.forceHome()
                
            elif work == "Q": # Get position
                self.getPosition()
                
            elif work == "D": # Disconnect
                self.closeDevice()
                return

            self.status = "standby"
