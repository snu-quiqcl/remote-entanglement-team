# -*- coding: utf-8 -*-
"""
Created on Tue Oct 17 18:51:52 2023

@author: QCP75
The GUI v3 supports pyqtGraph
"""

import os
from PyQt5 import uic, QtWidgets
from PyQt5.QtCore import QObject, Qt
from PyQt5.QtWidgets import QLabel, QLineEdit, QCheckBox, QInputDialog


filename = os.path.abspath(__file__)
dirname = os.path.dirname(filename)
uifile = dirname + '/motor_status_ui_v3.ui'

Ui_Form, _ = uic.loadUiType(uifile)


class MotorController_GUI(QtWidgets.QMainWindow, Ui_Form):
    
    _gui_initialized = False
    
    def __init__(self, controller=None):
        QtWidgets.QMainWindow.__init__(self)
        
        self.setupUi(self)
        self.checkBox.setVisible(False)
        
        # Add a button to connect remote motors manually.
        # self.btnConnectRemote = QtWidgets.QPushButton("Connect Remote")
        # self.btnConnectRemote.clicked.connect(self.pressedConnectRemoteMotors)
        
        # # Existing motor columns use 0~4:
        # # checkbox, nickname, serial, position, status
        # # Put the new button in column 5 of the header row.
        # self.gridLayout.addWidget(self.btnConnectRemote, 0, 5)
               
        self.parent = controller
        
        self.motor_idx = 1
        self.motor_dict = {}
            
        self.setWindowTitle("Motor Controller v3.0")
        self.parent._sig_motors_positions.connect(self.updatePosition)
        
        if not self.parent == None:
            self._initMotors(self.parent._motors)
            
        self._gui_initialized = True
            
    def showEvent(self, event):
        if self._gui_initialized:
            self.updateMotorStatus()
        
    def updateMotorStatus(self):
        for motor_handle in self.motor_dict.values():
            motor_handle.updateStatus()
        
    def _initMotors(self, motor_dict):
        for nick, motor in motor_dict.items():
            self.addMotor(nick, motor.serial, motor)
        
    def addMotor(self, nickname="", serial_number="", motor=None):
        if nickname in self.motor_dict.keys():
            raise ValueError("The nickname '%s' is already taken." % nickname)
            return
        
        self.motor_dict[nickname] = IndividualMotorGUI(self, nickname, serial_number, motor)
        self.motor_dict[nickname].Qposition.returnPressed.connect(self.requestedMotorMoving)
    
        # Connect button for each remote motor
        self.motor_dict[nickname].Qconnect.clicked.connect(self.pressedRemoteButton)
    
        self.gridLayout.addWidget(self.motor_dict[nickname].QcheckBox, self.motor_idx, 0)
        self.gridLayout.addWidget(self.motor_dict[nickname].Qnickname, self.motor_idx, 1)
        self.gridLayout.addWidget(self.motor_dict[nickname].Qserial,   self.motor_idx, 2)
        self.gridLayout.addWidget(self.motor_dict[nickname].Qposition, self.motor_idx, 3)
        self.gridLayout.addWidget(self.motor_dict[nickname].Qstatus,   self.motor_idx, 4)
        self.gridLayout.addWidget(self.motor_dict[nickname].Qconnect,  self.motor_idx, 5)
    
        self.motor_idx += 1
    
        self.setFixedHeight(int(50 + 25*self.motor_idx))
        
    def requestedMotorMoving(self):
        for motor_nick, motor_handle in self.motor_dict.items():
            if motor_handle.Qposition == self.sender():
                try:
                    target = float(motor_handle.Qposition.text())
    
                    # User input is now committed.
                    motor_handle._editing_position = False
    
                    data_dict = {motor_nick: target}
                    self.parent.moveToPosition(data_dict)
                    return
    
                except Exception as e:
                    print("[GUI ERROR] requestedMotorMoving:", e)
                    motor_handle._editing_position = False
                    motor_handle.changedStatus(motor_nick, "error")
        
    def pressedOpenMotors(self):
        motor_list = []
        for motor_nick, motor_handle in self.motor_dict.items():
            if motor_handle.isChecked:
                motor_list.append(motor_nick)
                motor_handle.QcheckBox.setChecked(False)
        self.parent.openDevice(motor_list)
        
    def pressedHomeMotors(self):
        motor_list = []
        for motor_nick, motor_handle in self.motor_dict.items():
            if motor_handle.isChecked:
                motor_list.append(motor_nick)
                motor_handle.QcheckBox.setChecked(False)
        self.parent.homePosition(motor_list)
              
    def pressedCloseMotors(self):
        motor_list = []
        for motor_nick, motor_handle in self.motor_dict.items():
            if motor_handle.isChecked:
                motor_list.append(motor_nick)
                motor_handle.QcheckBox.setChecked(False)
        self.parent.closeDevice(motor_list)
        
    def pressedAddMotor(self):
        nickname, nickname_returned = QInputDialog.getText(self, "Motor adder (1/3)", "Enter the motor's nickname:")
        if nickname_returned:
        
            motor_type, type_returned = QInputDialog.getInt(self, "Motor adder (2/3)", "Enter the motor's type (0: KDC101, 1: Dummy, 2: remote):", value=0, min=0, max=2)
    
            if type_returned:
                if motor_type in [0, 1]:
                    serial_number, serial_returned = QInputDialog.getText(self, "Motor adder (3/3)", "Enter the serial number:")
                    if serial_returned:
                        self.parent.addMotor(serial_number, "Dummy" if motor_type else "KDC101", nickname)
                        self.addMotor(nickname, serial_number, self.parent._motors[nickname])
                        
                        self.toStatusBar("A motor (%s) has beeen added." % nickname)
                        return
                    
                else: # remote motor
                    owner_nick, owner_returned = QInputDialog.getText(self, "Motor adder (3/3)", "Enter the owner's nickname:")
                    if owner_returned:
                        self.parent.addMotor(owner_nick, "remote", nickname, True)
                        self.addMotor("%s:%s" % (owner_nick, nickname), "remote", self.parent._motors["%s:%s" % (owner_nick, nickname)])
                        
                        self.toStatusBar("A remote motor (%s:%s) has beeen added." % (owner_nick, nickname))
                        return
                        
        self.toStatusBar("Adding a motor has been aborted.")
                    
    def pressedRemoteButton(self):
        sender = self.sender()
    
        for motor_nick, motor_handle in self.motor_dict.items():
            if motor_handle.Qconnect != sender:
                continue
    
            motor = motor_handle.motor
    
            is_remote = False
            if hasattr(motor, "serial") and motor.serial == "remote":
                is_remote = True
            if ":" in motor_nick:
                is_remote = True
    
            if not is_remote:
                self.toStatusBar("This motor is not a remote motor: %s" % motor_nick)
                return
    
            # If connected, use the same button as Disconnect.
            if motor_handle.Qconnect.text() == "Disconnect" or motor.status == "standby":
                self.parent.closeDevice([motor_nick])
                motor_handle.Qconnect.setText("Reconnect")
                motor_handle.Qconnect.setEnabled(True)
                self.toStatusBar("Remote motor disconnection requested: %s" % motor_nick)
                return
    
            # Otherwise, connect or reconnect.
            self.parent.connectRemoteMotors(motor_nick) 
            self.toStatusBar("Remote motor connection requested: %s" % motor_nick)
            return
    
    def pressedConnectOneRemoteMotor(self):
        sender = self.sender()
    
        for motor_nick, motor_handle in self.motor_dict.items():
            if motor_handle.Qconnect == sender:
                motor = motor_handle.motor
    
                is_remote = False
    
                if hasattr(motor, "serial") and motor.serial == "remote":
                    is_remote = True
    
                if ":" in motor_nick:
                    is_remote = True
    
                if not is_remote:
                    self.toStatusBar("This motor is not a remote motor: %s" % motor_nick)
                    return
    
                self.parent.connectRemoteMotors(motor_nick)
                self.toStatusBar("Remote motor connection requested: %s" % motor_nick)
                return    
    
    def changeItem(self, row_idx, col_idx, string):
        if row_idx > len(self.table_dict)-1 or col_idx > 3:
            raise ValueError ("Unexpected row id")
        
        self.tableWidget.item(row_idx, col_idx).setText(string)

        
    def getItem(self, row_idx, col_idx):
        text = self.tableWidget.item(row_idx, col_idx).text()
        return text
    
    def updatePosition(self, position_dict):
        for motor_nick, motor_position in position_dict.items():
            if motor_nick not in self.motor_dict:
                print("[GUI WARNING] unknown motor position update:", motor_nick)
                print("[GUI WARNING] known motors:", list(self.motor_dict.keys()))
                continue
    
            self.motor_dict[motor_nick].changedPosition(motor_position)
            
    def toStatusBar(self, msg, duration=8000):
        self.statusbar.showMessage(msg, duration)
    
class IndividualMotorGUI(QObject):
    
    isChecked = False
    status = "closed"
    
    def __init__(self, parent=None, nick="", serial_number="", motor=None):
        super().__init__()
        self.parent = parent
        self.nickname = nick
        self.serial = serial_number
        
        self.QcheckBox = QCheckBox(self.parent)
        self.Qnickname = self._createQLabel(nick)
        self.Qserial   = self._createQLabel(serial_number)
        self.Qposition = QLineEdit("0.000")
        self._editing_position = False

        self.Qposition.textEdited.connect(self._onPositionTextEdited)
        self.Qposition.editingFinished.connect(self._onPositionEditingFinished)
        self.Qstatus   = self._createQLabel("Closed")
    
        # Individual remote connection button
        self.Qconnect = QtWidgets.QPushButton("Connect")
    
        if serial_number == "remote" or ":" in nick:
            self.Qconnect.setVisible(True)
        else:
            self.Qconnect.setVisible(False)
        
        self.motor = motor
        
        self.Qposition.setEnabled(False)
        self.Qstatus.setText("Closed")
        self.Qstatus.setStyleSheet("background-color:rgb(20, 20, 20); color:rgb(200, 200, 200);")
        self.QcheckBox.toggled.connect(self.toggledCheckBox)
        
        self.motor._sig_motor_initialized.connect(self.initiatedMotor)
        self.motor._sig_motor_error.connect(self.erroredMotor)
        self.motor._sig_motor_move_done.connect(self.movedMotor)
        self.motor._sig_motor_homed.connect(self.homedMotor)
        
        self.motor._sig_motors_changed_status.connect(self.changedStatus)
        
    def _onPositionTextEdited(self, text):
        # This signal is emitted only when the user edits the text.
        self._editing_position = True
    
    def _onPositionEditingFinished(self):
        # Do not immediately overwrite here.
        # requestedMotorMoving() will read the value after Return is pressed.
        pass
    def toggledCheckBox(self, flag):
        self.isChecked = flag
        
    def initiatedMotor(self, nick):
        print("[GUI SETTEXT] initiatedMotor", self.nickname, nick)
        self.setPositionTextFromMotor(self.motor.position)
    
    def erroredMotor(self, nick):
        self.changedStatus(self.nickname, "error")
    
    def movedMotor(self, nick, position):
        print("[GUI SETTEXT] movedMotor", self.nickname, nick, position)
        self._editing_position = False
        self.setPositionTextFromMotor(self.motor.position, force=True)
    
    def homedMotor(self, nick):
        self._editing_position = False
        self.Qposition.setText("0.000")
        
    def changedPosition(self, position):
        print("[GUI SETTEXT] changedPosition", self.nickname, position,
          "focus=", self.Qposition.hasFocus(),
          "editing=", getattr(self, "_editing_position", None))
        self.setPositionTextFromMotor(position)
    
        self.Qposition.setText("%.3f" % position)
    def setPositionTextFromMotor(self, position, force=False):
        if self._editing_position and not force:
            return
    
        self.Qposition.setText("%.3f" % position)
    def changedStatus(self, nick, status):
        if status == "standby":
            self.Qposition.setEnabled(True)
            self.Qstatus.setStyleSheet("background-color:rgb(10, 150, 10); color:rgb(200, 200, 200);")
    
        elif status == "initiating":
            self.Qposition.setEnabled(False)
            self.Qstatus.setStyleSheet("background-color:rgb(130, 130, 130); color:rgb(200, 200, 200);")
    
        elif status == "moving":
            self.Qposition.setEnabled(False)
            self.Qstatus.setStyleSheet("background-color:rgb(10, 10, 150); color:rgb(200, 200, 200);")
    
        elif status == "homing":
            self.Qposition.setEnabled(False)
            self.Qstatus.setStyleSheet("background-color:rgb(150, 10, 10); color:rgb(200, 200, 200);")
    
        elif status == "closed":
            self.Qposition.setEnabled(False)
            self.Qstatus.setStyleSheet("background-color:rgb(20, 20, 20); color:rgb(200, 200, 200);")
    
        elif status == "error":
            self.Qposition.setEnabled(False)
            self.Qstatus.setStyleSheet("background-color:rgb(150, 10, 10); color:rgb(200, 200, 200);")
    
        self.Qstatus.setText(status)
    
        is_remote = self.serial == "remote" or ":" in self.nickname
    
        if is_remote:
            if status == "standby":
                self.Qconnect.setText("Disconnect")
                self.Qconnect.setEnabled(True)
        
            elif status == "connecting":
                self.Qconnect.setText("Connecting...")
                self.Qconnect.setEnabled(False)
        
            elif status == "initiating":
                self.Qconnect.setText("Disconnect")
                self.Qconnect.setEnabled(False)
        
            elif status == "closed":
                self.Qconnect.setText("Connect")
                self.Qconnect.setEnabled(True)
        
            elif status == "error":
                self.Qconnect.setText("Reconnect")
                self.Qconnect.setEnabled(True)
        
            elif status in ["moving", "homing"]:
                self.Qconnect.setText("Disconnect")
                self.Qconnect.setEnabled(False)
            
    def updateStatus(self):
        print("[GUI SETTEXT] updateStatus", self.nickname,
         self.motor.position, self.motor.status,
         "editing=", getattr(self, "_editing_position", None))
        position = self.motor.position
        status = self.motor.status
    
        self.setPositionTextFromMotor(position)
        self.changedStatus(self.nickname, status)
        
    def _createQLabel(self, label_text):
        qlabel = QLabel(label_text)
        qlabel.setAlignment(Qt.AlignCenter)
        return qlabel

        

        
if __name__ == "__main__":
    gui = MotorController_GUI()
    gui.show()