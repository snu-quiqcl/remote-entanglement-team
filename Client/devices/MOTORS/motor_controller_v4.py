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
    
            # If this function is called while handling data received from remote,
            # do not send another socket message.
            if getattr(self, "_handling_remote_data", False):
                return func(self, *args)
    
            if self.remote_flag:
                if func.__name__ == "_initializedMotor":
                    nick = args[0]
                    full_nick = self._fullMotorNick(nick)
                    msg = ["D", "%s:MOTORS" % self.user_name, "INITED", [full_nick]]
                    self.toSocket(msg)
    
                elif func.__name__ == "_homedMotor":
                    nick = args[0]
                    full_nick = self._fullMotorNick(nick)
                    msg = ["D", "%s:MOTORS" % self.user_name, "HOMED", [full_nick]]
                    self.toSocket(msg)
    
                elif func.__name__ == "_detectedError":
                    error_message = args[0] if len(args) else "Unknown error"
    
                    if getattr(self, "_handling_remote_error", False):
                        return func(self, *args)
    
                    sender = self.sender()
    
                    if sender is None or not hasattr(sender, "nickname"):
                        return func(self, *args)
    
                    nick = sender.nickname
                    full_nick = self._fullMotorNick(nick)
                    msg = ["E", "%s:MOTORS" % self.user_name, full_nick, [error_message]]
                    self.toSocket(msg)
    
                elif func.__name__ == "_completedMotorMoving":
                    nick, position = args
                    full_nick = self._fullMotorNick(nick)
                    msg = ["D", "%s:MOTORS" % self.user_name, "MOVED", [full_nick, position]]
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
        self._handling_remote_error = False
        self._handling_remote_data = False
        # Remote motor connection state
        self._remote_motor_owners = {}          # {"sz": ["x", "y"], ...}
        self._remote_connection_state = "DISCONNECTED"
        self._remote_connecting_owners = set()
        self._remote_connected_owners = set()
        self._remote_connecting_motors = set()
        
        self.remote_connect_timer = QTimer()
        self.remote_connect_timer.setSingleShot(True)
        self.remote_connect_timer.timeout.connect(self._onRemoteConnectTimeout)
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
        from Motor_Controller_GUI_v4 import MotorController_GUI
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
    
                if owner not in self._remote_motor_owners:
                    self._remote_motor_owners[owner] = []
    
                if nickname not in self._remote_motor_owners[owner]:
                    self._remote_motor_owners[owner].append(nickname)
    
                full_nick = "%s:%s" % (owner, nickname)
    
                # Create the remote motor instance now,
                # but do not connect to the server here.
                motor_dict[full_nick] = self._addRemoteMotor(
                    owner,
                    "remote",
                    nickname
                )
    
                print("[MOTOR] remote motor instance created but not connected:",
                      full_nick)
    
        return motor_dict
    def _fullMotorNick(self, nick):
        if isinstance(nick, str) and ":" in nick:
            return nick
        return "%s:%s" % (self.user_name, nick)
    def _resolveMotorNick(self, nick):
        """
        Return the key used in self._motors.
    
        Examples:
            "pz"    -> "pz" if local motor exists
            "EC:pz" -> "EC:pz" if remote motor exists
            "EC:pz" -> "pz" if this client is the owner side
        """
        if nick in self._motors:
            return nick
    
        if isinstance(nick, str) and ":" in nick:
            local_nick = nick.split(":")[-1]
    
            if local_nick in self._motors:
                return local_nick
    
        return None
    def addMotor(self, serno_or_owner, dev_type, nickname, remote_flag=0):
        if remote_flag:
            self._motors["%s:%s" % (serno_or_owner, nickname)] = self._addRemoteMotor(serno_or_owner, dev_type, nickname)
        else:
            self._motors[nickname] = self._addMotor(serno_or_owner, dev_type, nickname)

    def connectRemoteMotors(self, motor_list=None, owner=None):
        """
        Connect remote motors explicitly.
        """
    
        if self.sck is None:
            #print("[MOTOR] cannot connect remote motors: socket is None")
            return
    
        # If previous connection trial was stuck, reset it and retry.
        if self._remote_connection_state == "CONNECTING":
            #print("[MOTOR] previous remote connection was stuck in CONNECTING. Reset and retry.")
            self._remote_connecting_owners.clear()
            self._remote_connected_owners.clear()
            self._remote_connection_state = "DISCONNECTED"
    
        # Optional: allow reconnect even after CONNECTED
        # If you want to block duplicate connection after success, keep this.
        # If you want reconnect button always available, remove this block.
        if self._remote_connection_state == "CONNECTED":
            #print("[MOTOR] remote motors are already connected. Reconnect request will be sent again.")
            self._remote_connection_state = "DISCONNECTED"
    
        target_motors = []
    
        # Case 1: explicit motor nickname was given
        if motor_list is not None:
            if type(motor_list) == str:
                motor_list = [motor_list]
    
            for full_nick in motor_list:
                if full_nick not in self._motors:
                    #print("[MOTOR] unknown remote motor:", full_nick)
                    continue
    
                motor = self._motors[full_nick]
    
                if not hasattr(motor, "serial") or motor.serial != "remote":
                    #print("[MOTOR] not a remote motor:", full_nick)
                    continue
    
                target_motors.append((motor.owner, motor.nickname))
    
        # Case 2: owner was given
        elif owner is not None:
            if owner not in self._remote_motor_owners:
                #print("[MOTOR] unknown remote owner:", owner)
                return
    
            for nick in self._remote_motor_owners[owner]:
                full_nick = "%s:%s" % (owner, nick)
    
                if full_nick not in self._motors:
                    print("[MOTOR] remote motor instance does not exist:", full_nick)
                    continue
    
                target_motors.append((owner, nick))
    
        # Case 3: connect all registered remote motors
        else:
            for owner_name, nick_list in self._remote_motor_owners.items():
                for nick in nick_list:
                    full_nick = "%s:%s" % (owner_name, nick)
    
                    if full_nick not in self._motors:
                        print("[MOTOR] remote motor instance does not exist:", full_nick)
                        continue
    
                    target_motors.append((owner_name, nick))
    
        if not target_motors:
            #print("[MOTOR] no remote motors to connect")
            return
    
        self._remote_connection_state = "CONNECTING"
        self._remote_connecting_motors.clear()
        
        for owner_name, nick in target_motors:
            self._remote_connecting_owners.add(owner_name)
        
            motor_key = "%s:%s" % (owner_name, nick)
            self._remote_connecting_motors.add(motor_key)
        
            # Show "connecting" state in GUI immediately.
            if motor_key in self._motors:
                self._motors[motor_key].status = "connecting"
        
            msg = [
                "C",
                "%s:MOTORS" % owner_name,
                "CON",
                [nick]
            ]
        
            self.toSocket(msg)
        
        # Timeout if no STATUS response arrives.
        self.remote_connect_timer.start(3000)
    def _onRemoteConnectTimeout(self):
        if self._remote_connection_state != "CONNECTING":
            return
    
        print("[MOTOR] remote connection timeout")
    
        # Mark pending remote motors as error so GUI button becomes Reconnect.
        for motor_key in list(self._remote_connecting_motors):
            if motor_key in self._motors:
                self._motors[motor_key].status = "error"
    
        self._remote_connecting_motors.clear()
        self._remote_connecting_owners.clear()
        self._remote_connection_state = "DISCONNECTED"
    
        if self.gui:
            self.gui.toStatusBar("Remote motor connection timeout. Please reconnect.")
        else:
            print("Remote motor connection timeout. Please reconnect.")        
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
            if motor_nick not in self._motors:
                self._detectedError("Unknown motor: %s" % motor_nick)
                continue
    
            if ":" in motor_nick and self._remote_connection_state != "CONNECTED":
                self._detectedError(
                    "Remote motor is not connected yet: %s" % motor_nick
                )
                continue
    
            self._motors[motor_nick].toWorkList("H")
            self._motors_under_homing.append(motor_nick)
    
    def moveToPosition(self, motor_dict):
        for motor_nick, target_position in motor_dict.items():
            if motor_nick not in self._motors:
                self._detectedError("Unknown motor: %s" % motor_nick)
                continue
    
            motor = self._motors[motor_nick]
    
            if ":" in motor_nick and self._remote_connection_state != "CONNECTED":
                self._detectedError(
                    "Remote motor is not connected yet: %s" % motor_nick
                )
                continue
    
            if hasattr(motor, "_is_opened") and not motor._is_opened:
                self._detectedError(
                    "Motor is not opened yet: %s" % motor_nick
                )
                continue
    
            motor.setTargetPosition(target_position)
            self._motors_under_request.append(motor_nick)
            motor.toWorkList("M")
    
        if len(self._motors_under_request) and not self.pos_checker.isActive():
            self.pos_checker.start(qtimer_interval)

    @remote_control_wrapper
    def _completedMotorMoving(self, nick, position):
        motor_key = self._resolveMotorNick(nick)
    
        candidates = [nick]
        if motor_key is not None:
            candidates.append(motor_key)
            candidates.append(self._fullMotorNick(motor_key))
    
        for key in candidates:
            if key in self._motors_under_request:
                self._motors_under_request.remove(key)
                break
    
    def openDevice(self, motor_list):
        if type(motor_list) == str:
            motor_list = [motor_list]
    
        valid_motor_list = []
    
        for m_nick in motor_list:
            motor_key = self._resolveMotorNick(m_nick)
    
            if motor_key is None:
                self._detectedError("Unknown motor: %s" % m_nick)
                continue
    
            if ":" in motor_key and self._remote_connection_state != "CONNECTED":
                self._detectedError(
                    "Remote motor is not connected yet: %s" % motor_key
                )
                continue
    
            valid_motor_list.append(motor_key)
    
        self._sig_motors_initialized.emit(len(valid_motor_list), "")
    
        for motor_key in valid_motor_list:
            if motor_key not in self._motors_under_loading:
                self._motors_under_loading.append(motor_key)
            self._motors[motor_key].toWorkList("O")
            
    def closeDevice(self, motor_list):
        if type(motor_list) == str:
            motor_list = [motor_list]
    
        for m_nick in motor_list:
            motor_key = self._resolveMotorNick(m_nick)
    
            if motor_key is None:
                self._detectedError("Unknown motor: %s" % m_nick)
                continue
    
            self._motors[motor_key].toWorkList("D")

    @remote_control_wrapper
    def _homedMotor(self, nick):
        self._motors_under_homing.remove(nick)
            
    def homeDevice(self, motor_list):
        for m_idx, m_nick in enumerate(motor_list):
            self._motors[m_nick].toWorkList("H")
            self._motors_under_homing.append(m_nick)
          
    def checkPositionsUnderMoving(self):
        if len(self._motors_under_request):
            print("[POS CHECK] _motors_under_request:", self._motors_under_request)
    
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
            position_list.append(self._fullMotorNick(nick))
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
            work = self.queue.get()
            self._status  = "running"
            # decompose the job
            work_type, command = work[:2]
            data = work[2]
            if work_type == "C":
                if command == "CON":
                    self.remote_flag = True
                    status_list = []
                
                    for nick in data:
                        motor_key = self._resolveMotorNick(nick)
                
                        if motor_key is None:
                            print("[MOTOR WARNING] CON for unknown motor:", nick)
                            print("[MOTOR WARNING] known motors:", list(self._motors.keys()))
                            continue
                
                        full_nick = self._fullMotorNick(motor_key)
                
                        status_list.append(full_nick)
                        status_list.append(self._motors[motor_key].status)
                        status_list.append(self._motors[motor_key].position)
                
                    if status_list:
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
                    new_data = [self._fullMotorNick(nick) for nick in data]
                    msg = ["D", "%s:MOTORS" % self.user_name, "INIT", new_data]
                    self.toSocket(msg)
                    
                elif command == "CLOSE":
                    self.closeDevice(data)
                    new_data = [self._fullMotorNick(nick) for nick in data]
                    msg = ["D", "%s:MOTORS" % self.user_name, "CLOSE", new_data]
                    self.toSocket(msg)
                    
                elif command == "HOME":
                    self.homeDevice(data)
                    new_data = [self._fullMotorNick(nick) for nick in data]
                    msg = ["D", "%s:MOTORS" % self.user_name, "HOME", new_data]
                    self.toSocket(msg)
                                
                elif command == "MOVE":
                    data_dict = dict(zip(data[::2], data[1::2]))
                    self.moveToPosition(data_dict)
                    new_data = [self._fullMotorNick(nick) for nick in data[::2]]
                
                    msg = ["D", "%s:MOTORS" % self.user_name, "MOVE", new_data]
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
                self._handling_remote_data = True
            
                try:
                    if command == "STATUS":
                        position_dict = {}
            
                        for nick, status, position in zip(data[::3], data[1::3], data[2::3]):
                            motor_key = self._resolveMotorNick(nick)
            
                            if motor_key is None:
                                print("[MOTOR WARNING] received STATUS for unknown motor:", nick)
                                print("[MOTOR WARNING] known motors:", list(self._motors.keys()))
                                continue
            
                            self._motors[motor_key].position = position
                            self._motors[motor_key].status = status
            
                            position_dict[motor_key] = position
            
                            if ":" in nick:
                                owner = nick.split(":")[0]
                                self._remote_connected_owners.add(owner)
                                self._remote_connecting_owners.discard(owner)
            
                            self._remote_connecting_motors.discard(motor_key)
            
                        if len(self._remote_connecting_motors) == 0:
                            if self.remote_connect_timer.isActive():
                                self.remote_connect_timer.stop()
            
                        if len(self._remote_connecting_owners) == 0 and len(self._remote_connected_owners) > 0:
                            self._remote_connection_state = "CONNECTED"
            
                        self._sig_motors_positions.emit(position_dict)
            
                    elif command == "REMOTE":
                        self.remote_flag = data[0]
            
                    elif command == "INIT":
                        for nick in data:
                            motor_key = self._resolveMotorNick(nick)
                            if motor_key is None:
                                print("[MOTOR WARNING] INIT for unknown motor:", nick)
                                continue
                            self._motors[motor_key].status = "initiating"
            
                    elif command == "INITED":
                        for nick in data:
                            motor_key = self._resolveMotorNick(nick)
                            if motor_key is None:
                                print("[MOTOR WARNING] INITED for unknown motor:", nick)
                                continue
            
                            self._motors[motor_key].status = "standby"
                            self._motors[motor_key]._is_opened = True
                            self._motors[motor_key]._sig_motor_initialized.emit(motor_key)
            
                    elif command == "MOVE":
                        for nick in data:
                            motor_key = self._resolveMotorNick(nick)
                            if motor_key is None:
                                print("[MOTOR WARNING] MOVE for unknown motor:", nick)
                                continue
                            self._motors[motor_key].status = "moving"
            
                    elif command == "MOVED":
                        for nick, position in zip(data[::2], data[1::2]):
                            motor_key = self._resolveMotorNick(nick)
                            if motor_key is None:
                                print("[MOTOR WARNING] MOVED for unknown motor:", nick)
                                continue
            
                            self._motors[motor_key].position = position
                            self._motors[motor_key].status = "standby"
                            self._motors[motor_key]._sig_motor_move_done.emit(motor_key, position)
            
                    elif command == "HOME":
                        for nick in data:
                            motor_key = self._resolveMotorNick(nick)
                            if motor_key is None:
                                print("[MOTOR WARNING] HOME for unknown motor:", nick)
                                continue
                            self._motors[motor_key].status = "homing"
            
                    elif command == "HOMED":
                        for nick in data:
                            motor_key = self._resolveMotorNick(nick)
                            if motor_key is None:
                                print("[MOTOR WARNING] HOMED for unknown motor:", nick)
                                continue
            
                            self._motors[motor_key].status = "standby"
                            self._motors[motor_key]._sig_motor_homed.emit(motor_key)
                            self._motors[motor_key].position = 0
            
                    elif command == "CLOSE":
                        for nick in data:
                            motor_key = self._resolveMotorNick(nick)
                            if motor_key is None:
                                print("[MOTOR WARNING] CLOSE for unknown motor:", nick)
                                continue
            
                            self._motors[motor_key].status = "closed"
                            self._motors[motor_key]._is_opened = False
            
                    elif command == "POS":
                        for nick, position in zip(data[::2], data[1::2]):
                            motor_key = self._resolveMotorNick(nick)
                            if motor_key is None:
                                print("[MOTOR WARNING] POS for unknown motor:", nick)
                                continue
            
                            self._motors[motor_key].position = position
            
                    else:
                        raise RuntimeError("An unknown data command while handling returned data. (%s)" % command)
            
                finally:
                    self._handling_remote_data = False                
            elif work_type == "E":  # An Error has been detected
                nick = command
                error_message = data[0] if len(data) else "Unknown error"
            
                print("[MOTOR ERROR]", nick, error_message)
            
                self._remote_connection_state = "ERROR"
            
                motor_key = self._resolveMotorNick(nick)
            
                if motor_key is not None:
                    # IMPORTANT:
                    # Do not emit _sig_motor_error here.
                    # It can call _detectedError(), and remote_control_wrapper may send E again.
                    self._motors[motor_key].status = "error"
            
                    if self.gui:
                        self.gui.toStatusBar("Remote motor error: %s / %s" % (motor_key, error_message))
                    else:
                        print("Remote motor error:", motor_key, error_message)
            
                else:
                    # Also do not call self._detectedError() here.
                    # Just display/log it locally.
                    if self.gui:
                        self.gui.toStatusBar("Remote motor error: %s / %s" % (nick, error_message))
                    else:
                        print("Remote motor error:", nick, error_message)
            
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