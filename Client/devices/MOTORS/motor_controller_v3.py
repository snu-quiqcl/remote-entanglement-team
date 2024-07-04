"""
Created on Sun Nov 21 2021
@author: Junho Jeong
"""
from PyQt5.QtCore import QObject, pyqtSignal, QTimer, QThread#, pyqtSlot
from motor_handler import MotorHandler
from remote_motor_handler import RemoteMotorHandler
from queue import Queue
version = "3.1"
qtimer_interval = 100 # ms

class MotorController(QObject):
    """
    The controller class uses QThread class as a base, handling commands and the device is done by QThread.
    This avoids being delayed by the main thread's task.
    
    The logger decorate automatically record the exceptions when a bug happens.
    """
    
    _sig_motors_initialized = pyqtSignal(int, str)
    _sig_motors_positions = pyqtSignal(dict)
    _sig_remote_control = pyqtSignal()
    
    
    def remote_control_wrapper(func):
        def wrapper(self, *args):
            if self.remote_flag:
                if func.__name__ == "_initializedMotor":
                    nick = args[0]
                    msg = ["D", "%s:MOTORS" % self.user_name, "INITED", ["%s:%s" % (self.user_name, nick)]]     
                    self.toSocket(msg)
                    
                elif func.__name__ == "_homedMotor":
                    nick = args[0]
                    msg = ["D", "%s:MOTORS" % self.user_name, "HOMED", ["%s:%s" % (self.user_name, nick)]]
                    self.toSocket(msg)
                    
                elif func.__name__ == "_detectedError":
                    nick = self.sender().nickname
                    error_message = args[0]
                    msg = ["E", "%s:MOTORS" % self.user_name, "%s:%s" % (self.user_name, nick), [error_message]]
                    self.toSocket(msg)
                    
                elif func.__name__ == "_completedMotorMoving":
                    nick, position = args
                    msg = ["D", "%s:MOTORS" % self.user_name, "MOVED", ["%s:%s" % (self.user_name, nick), position]]
                    self.toSocket(msg)
                    
                else:
                    self._detectedError("Un unknown function has been detected.(%s)" % func.__name__)
                    
            return func(self, *args)
                
        return wrapper

    
    def __init__(self, socket=None, gui=None):  # cp is ConfigParser class
        super().__init__()
        self.sck = socket # parent
        self.cp = self.sck.cp
        self.gui = gui
        
        self._status = "standby"
        self._motors = {}
        self._is_opened = False
        self._gui_opened = False
        self._motors_under_request = []
        self._motors_under_homing  = []
        self._motors_under_loading = []
        # Setting motor initiator
        self.device = self.cp.get("device", "motors")
        self._motors = self._getMotorDictToLoad()
        
        self.pos_checker = QTimer() # This emits position signals of currently moving motors in 0.5s interval.
        self.pos_checker.setSingleShot(True)
        self.pos_checker.timeout.connect(self.checkPositionsUnderMoving)
        
        print("Motor Controller v%s" % version)
        
        # For remote control
        self._client_list = []
        self.queue = Queue()
        self.remote_flag = False
        self.message_thread = QThread()
        self._sig_remote_control.connect(self.run)
        
    def openGui(self):
        from Motor_Controller_GUI_v3 import MotorController_GUI
        self.gui = MotorController_GUI(controller=self)
        self._gui_opened = True

    def _receiveMotors(self, motor_dict):
        for nickname, motor in self._motors.items():
            self._positions[nickname] = motor.position
            
    def _getMotorDictToLoad(self):
        motor_dict = {}
        mtype = self.cp.get("motors", "motor_type")
        self.user_name = self.cp.get("client", "nickname")
        
        for option in self.cp.options("motors"):
            if "_serno" in option:
                nickname = option[:option.find("_serno")]
                serno = self.cp.get("motors", option)
                                
                motor_dict[nickname] = self._addMotor(serno, mtype, nickname)
                
            elif "_owner" in option:
                nickname = option[:option.find("_owner")]
                owner = self.cp.get("motors", option)
                
                motor_dict["%s:%s" % (owner, nickname)] = self._addRemoteMotor(owner, "remote", nickname)
                
                
        return motor_dict
    
    def addMotor(self, serno_or_owner, dev_type, nickname, remote_flag=0):
        if remote_flag:
            self._motors["%s:%s" % (serno_or_owner, nickname)] = self._addRemoteMotor(serno_or_owner, dev_type, nickname)
        else:
            self._motors[nickname] = self._addMotor(serno_or_owner, dev_type, nickname)
    
    def _addMotor(self, serno, dev_type, nickname):        
        motor = MotorHandler(self, serno, dev_type=dev_type, nick=nickname)
        
        motor._sig_motor_initialized.connect(self._initializedMotor)
        motor._sig_motor_move_done.connect(self._completedMotorMoving)
        motor._sig_motor_error.connect(self._detectedError)
        motor._sig_motor_homed.connect(self._homedMotor)
        
        return motor
    
    def _addRemoteMotor(self, owner, dev_type, nickname):
        motor = RemoteMotorHandler(self, owner, dev_type, nickname, self.sck)
        motor._sig_motor_initialized.connect(self._initializedMotor)
        motor._sig_motor_move_done.connect(self._completedMotorMoving)
        motor._sig_motor_error.connect(self._detectedError)
        motor._sig_motor_homed.connect(self._homedMotor)
        
        return motor
        
    def _removeMotor(self, nickname):
        if nickname in self._motors.keys():
            self._motors[nickname].closeDevice()
            self._motors.pop(nickname)
    
    @remote_control_wrapper
    def _initializedMotor(self, nick):
        if nick in self._motors_under_loading:
            self._motors_under_loading.remove(nick)
        self._sig_motors_initialized.emit(len(self._motors_under_loading), nick)  # Let applications know how many motors are left.
    
    def getPosition(self, nickname):
        return self._motors[nickname].getPosition()
    
    def homePosition(self, motor_list):
        for motor_nick in motor_list:
            self._motors[motor_nick].toWorkList("H")
            self._motors_under_homing.append(motor_nick)
    
    def moveToPosition(self, motor_dict):
        # try:
        for motor_nick, target_position in motor_dict.items():
            self._motors[motor_nick].setTargetPosition(target_position)
            self._motors_under_request.append(motor_nick)
            self._motors[motor_nick].toWorkList("M")
        if not self.pos_checker.isActive():
            self.pos_checker.start(qtimer_interval) # Let the clients know the positions while moving.
        # except Exception as ee:
        #     print(ee)

    @remote_control_wrapper
    def _completedMotorMoving(self, nick, position):
        if nick in self._motors_under_request:
            self._motors_under_request.remove(nick)
    
    def openDevice(self, motor_list):
        if type(motor_list) == str:
            motor_list = [motor_list]
        self._sig_motors_initialized.emit(len(motor_list), "")  # Let applications know how many motors to be open. # Redundant?
        for m_idx, m_nick in enumerate(motor_list):
            self._motors_under_loading.append(m_nick)
            self._motors[m_nick].toWorkList("O")
            
    def closeDevice(self, motor_list):
        for m_idx, m_nick in enumerate(motor_list):
            self._motors[m_nick].toWorkList("D")

    @remote_control_wrapper
    def _homedMotor(self, nick):
        self._motors_under_homing.remove(nick)
            
    def homeDevice(self, motor_list):
        for m_idx, m_nick in enumerate(motor_list):
            self._motors[m_nick].toWorkList("H")
            self._motors_under_homing.append(m_nick)
          
    def checkPositionsUnderMoving(self):
        if len(self._motors_under_request):
            position_dict = {}
            for m_nick in self._motors_under_request:
                position_dict[m_nick] = self._motors[m_nick].getPosition()
            self._sig_motors_positions.emit(position_dict)
            if self.remote_flag:
                self._announcePositionsUnderMoving(position_dict)
            self.pos_checker.start(qtimer_interval)
            
    def _announcePositionsUnderMoving(self, position_dict):
        position_list = []
        for nick, position in position_dict.items():
            position_list.append("%s:%s" % (self.user_name, nick))
            position_list.append(position)
        msg = ["D", "%s:MOTORS" % self.user_name, "POS", position_list]
        self.toSocket(msg)
        
    @remote_control_wrapper
    def _detectedError(self, msg):
        if self.gui:
            self.gui.toStatusBar(msg)
        else:
            print(msg)
        
    def toWorkList(self, cmd):
        self.queue.put(cmd)
        if not self._status == "running":
            self.run()
            
    def run(self):
        while self.queue.qsize():
            print("queue size", self.queue.qsize())
            work = self.queue.get()
            self._status  = "running"
            # decompose the job
            work_type, command = work[:2]
            data = work[2]
            if work_type == "C":
                if command == "CON":
                    """
                    Successfully received a response from the server
                    """
                    self.remote_flag = True
                    status_list = []
                    for nick in data:
                        status_list.append("%s:%s" % (self.user_name, nick))
                        status_list.append(self._motors[nick].status)
                        status_list.append(self._motors[nick].position)
                        
                    msg = ["D", "%s:MOTORS" % self.user_name, "STATUS", status_list]
                    self.toSocket(msg)
                    
                elif command == "DCN":
                    """
                    Close the remote control mode
                    """
                    self.remote_flag = False
                    msg = ["D", "%s:MOTORS" % self.user_name, "REMOTE", [False]]
                    self.toSocket(msg)
                    
                elif command == "OPEN":
                    self.openDevice(data)
                    new_data = ["%s:%s" % (self.user_name, nick) for nick in data]
                    msg = ["D", "%s:MOTORS" % self.user_name, "INIT", new_data]
                    self.toSocket(msg)
                    
                elif command == "CLOSE":
                    self.closeDevice(data)
                    new_data = ["%s:%s" % (self.user_name, nick) for nick in data]
                    msg = ["D", "%s:MOTORS" % self.user_name, "CLOSE", new_data]
                    self.toSocket(msg)
                    
                elif command == "HOME":
                    self.homeDevice(data)
                    new_data = ["%s:%s" % (self.user_name, nick) for nick in data]
                    msg = ["D", "%s:MOTORS" % self.user_name, "HOME", new_data]
                    self.toSocket(msg)
                                
                elif command == "MOVE":
                    data_dict = dict(zip(data[::2], data[1::2]))
                    self.moveToPosition(data_dict)
                    new_data = ["%s:%s" % (self.user_name, nick) for nick in data[::2]]
                    
                    msg = ["D", "%s:MOTORS" % self.user_name, "MOVE", new_data] # nicknames only
                    self.toSocket(msg)
                    
                else:
                    raise RuntimeError("An unknown data command while handling command data. (%s)" % command)
                    
            elif work_type == "Q":
                if command == "STATUS":
                    status_list = []
                    for nick in data:
                        status_list.append("%s:%s" % (self.user_name, nick))
                        status_list.append(self._motors[nick].status)
                        
                    msg = ["D", "MOTORS", "STATUS", status_list]
                    self.toSocket(msg)
                
                elif command == "POS":
                    position_list = []
                    for nick in data:
                        position_list.append("%s:%s" % (self.user_name, nick))
                        position_list.append(self._motors[nick].getPosition())
                    
                    msg = ["D", "MOTORS", "POS", position_list]
                    self.toSocket(msg)
                else:
                    raise RuntimeError("An unknown data command while handling query. (%s)" % command)
                    
            # Data D is used when data has been acquired from the owner.        
            elif work_type == "D":
                if command == "STATUS":
                    position_dict = {}
                    for nick, status, position in zip(data[::3], data[1::3], data[2::3]):
                        self._motors[nick].position = position
                        self._motors[nick].status = status
                        
                        position_dict[nick] = position
                    self._sig_motors_positions.emit(position_dict)
                        
                elif command == "REMOTE":
                    self.remote_flag = data[0] # True of False
                    
                elif command == "INIT":
                    for nick in data:
                        self._motors[nick].status = "initiating"
                        
                elif command == "CLOSE":
                    for nick in data:
                        self._motors[nick].status = "closed"
                        self._motors[nick]._is_opened = False
                        
                elif command == "HOME":
                    for nick in data:
                        self._motors[nick].status = "homing"
                        
                elif command == "MOVE":
                    for nick in data:
                        self._motors[nick].status = "moving"
                        
                elif command == "INITED":
                    for nick in data:
                        self._motors[nick].status = "standby"
                        self._motors[nick]._is_opened = True
                        self._motors[nick]._sig_motor_initialized.emit(nick)
                
                elif command == "HOMED":
                    for nick in data:
                        self._motors[nick].status = "standby"
                        self._motors[nick]._sig_motor_homed.emit(nick)
                        self._motors[nick].position = 0
                        
                elif command == "MOVED":
                    for nick, position in zip(data[::2], data[1::2]):
                        self._motors[nick].position = position
                        self._motors[nick].status = "standby"
                        self._motors[nick]._sig_motor_move_done.emit(nick, position)
                        
                elif command == "POS":
                    for nick, position in zip(data[::2], data[1::2]):
                        self._motors[nick].position = position
                        
                else:
                    raise RuntimeError("An unknown data command while handling returned data. (%s)" % command)
                
            elif work_type == "E": # An Error has been detected
                nick = command
                self._motors[nick]._sig_motor_error.emit(data[0]) # data is the error message
                    
            else:
                print("An error while handling a message. (work_type:%s)" % work_type)
                continue
            
        self._status = "standby"
        self.message_thread.quit()
        
        
    def toSocket(self, msg):
        if not self.sck == None:
            self.sck.toMessageList(msg)
        else:
            print(msg)
            
         
"""
client = srv.rh.client_list[0]
client.toMessageList(["C", "MOTORS", "CON", ["px", "py", "pz"]])
"""