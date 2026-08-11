# -*- coding: utf-8 -*-
"""
Created on Mon Sep 27 17:01:22 2021

@author: jhjeong
E-mail: jhjeong32@snu.ac.kr
Tel. 010-9600-3392
"""
from QtClient_basic_v0_01 import ClientSocket

from PyQt5 import QtWidgets
from PyQt5.QtCore import pyqtSignal, QObject
from configparser import ConfigParser

import os, sys
from queue import Queue

filename = os.path.abspath(__file__)
dirname = os.path.dirname(filename)

class ClientMain(QObject):
    
    cp = None
    user_name = "unanimous"
    IP = "127.0.0.1"
    device_dict = {}
    
    status = "standby"
    _fire_signal = pyqtSignal()
    _gui_signal = pyqtSignal(list)
    gui = None
    
    
    ccd_cnt = 0

    def __init__(self, gui=True, config_path=None):
        super().__init__()
        self._shutting_down = False
        # These used to be class attributes, which leaked devices between
        # instances in diagnostics and made a second client in one process
        # unsafe.  A running client owns its device registry and GUI.
        self.device_dict = {}
        self.gui = None
        self._readConfig(config_path)
        self.socket = ClientSocket(self, self.user_name)
        self.socket._message_signal.connect(self.receivedMessage)
        self._msg_queue = Queue()

        self._setupDevices()
        if gui:
            sys.path.append(dirname + '/gui')
            from client_main_gui import MainWindow
            self.gui = MainWindow(self.device_dict, self.cp, self, self.cp.get("gui", "theme"))
        
        self._fire_signal.connect(self.manageMessageQue)
        
    def _readConfig(self, config_path=None):
        """Load the client configuration without silently inventing one.

        Resolution order is an explicit constructor/command-line path,
        ``QTCLIENT_CONFIG``, then ``config/<COMPUTERNAME>.ini``.  The legacy
        fallback attempted to copy a non-existent ``default.ini`` and failed
        with an unrelated error on test computers.
        """
        configured = config_path or os.getenv("QTCLIENT_CONFIG", "").strip()
        if configured:
            config_file = os.path.abspath(configured)
        else:
            PC_name = os.getenv('COMPUTERNAME', 'defaultValue')
            config_file = os.path.join(dirname, 'config', '%s.ini' % PC_name)
        if not os.path.isfile(config_file):
            raise FileNotFoundError(
                "Client configuration not found: %s. Pass EA.ini/EC.ini as "
                "the first argument or set QTCLIENT_CONFIG." % config_file
            )

        self.cp = ConfigParser()
        loaded = self.cp.read(config_file)
        if not loaded:
            raise RuntimeError("Could not read client configuration: %s" % config_file)
        
        self.IP = self.cp.get("win_server", "ip")
        self.PORT = int(self.cp.get("win_server", "port"))
        self.user_name = self.cp.get("client", "nickname")
        self.cp.set("client", "conf_file", config_file)

    def _setupDevices(self):
        sys.path.append(dirname + "/devices")
        device_list = self.cp['device']
        for device in device_list:
            # get the device nickname and its folder name from the section "device"
            sys.path.append(dirname + "/devices/%s/" % (device.upper()))
            sys.path.append(dirname + "/devices/%s/%s/" % (device.upper(), self.cp.get('device', device)))
            
            exec( "from %s import %s" % (self.cp.get(device, 'file'), self.cp.get(device, 'class')) )
            exec( "self.device_dict['%s'] = %s(socket=self)" % (device, self.cp.get(device, 'class')))

    def toMessageList(self, msg):
        self._msg_queue.put(msg)
        if self.status == "standby":
            self._fire_signal.emit()
        
    def manageMessageQue(self):
        self.status = "sending"
        while self._msg_queue.qsize():
            msg = self._msg_queue.get()
            self.socket.sendMessage(msg)
        self.status = "standby"
        
    def receivedMessage(self, msg_list):
        device = msg_list.pop(1)
        if not device == "SRV":
            # After the final cut-over MOTOR traffic has its own authenticated
            # transport.  Never accept a MOTOR command through the legacy DDS
            # socket in standalone mode, even if an old server still relays it.
            motor_server_mode = self.cp.get(
                "motor_server", "mode", fallback="legacy"
            ).strip().lower()
            if (
                motor_server_mode == "standalone"
                and device.rsplit(":", 1)[-1].upper() == "MOTORS"
            ):
                print("[MOTOR] Ignored legacy DDS MOTOR message:", msg_list)
                return

            if ":" in device.lower():
                device = device.split(":")[1]
                
            if device.lower() in self.device_dict.keys():
                self.device_dict[device.lower()].toWorkList(msg_list)
            else:                    
                print("No such device is in our device dict! (%s)." % device)
        
        else:
            if not self.gui == None:
                self._gui_signal.emit(msg_list)

    def shutdown(self):
        """Shut down device controllers before closing the DDS socket.

        The previous GUI close path called every ``closeDevice`` without the
        arguments required by MotorController and disconnected the socket
        first.  A dedicated, idempotent shutdown hook lets each controller
        perform the cleanup appropriate for its transport.
        """
        if self._shutting_down:
            return
        self._shutting_down = True

        for device, controller in list(self.device_dict.items()):
            try:
                if hasattr(controller, "shutdown"):
                    controller.shutdown()
                elif hasattr(controller, "closeDevice"):
                    controller.closeDevice()
            except Exception as err:
                print("An error while closing '%s', (%s)" % (device, err))

        try:
            if self.socket.isOpen():
                self.socket.breakConnection(True)
        except Exception as err:
            print("An error while closing the DDS server socket: %s" % err)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    selected_config = sys.argv[1] if len(sys.argv) > 1 else None
    client = ClientMain(config_path=selected_config)
    if not client.gui == None:
        client.gui.show()
    try:
        sys.exit(app.exec())
    finally:
        client.shutdown()
    # print(client.socket.makeConnection(client.IP, client.PORT))
# client.socket.sendMessage(["C", "DAC", "ON", []])
# client.socket.sendMessage(["C", "DAC", "SETV", [0, 0.3, 1, -4, 2, -0.7, 12, 8]])
# client.socket.sendMessage(["C", "EA_SG38X", "CON", []])
