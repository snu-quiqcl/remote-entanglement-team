# -*- coding: utf-8 -*-
"""
Created on Thu Oct  5 10:50:27 2023

@author: QCP75
"""
import os, sys
import numpy as np

serial_devices = ["SynthNV", "SynthHD"]
socket_devices = ["SG384", "APSYN420"]

filename = os.path.abspath(__file__)
dirname = os.path.dirname(filename)

# PyQt libraries
from PyQt5 import uic, QtWidgets

connection_ui_file = dirname + "/ui/device_connection_custom.ui"
connection_ui, _ = uic.loadUiType(connection_ui_file)

internal_dev_ui_file = dirname + "/ui/device_connection_internal.ui"
internal_dev_ui, _ = uic.loadUiType(internal_dev_ui_file)


class CustomDevice(QtWidgets.QWidget, connection_ui):
    
    
    def __init__(self, parent=None):
        QtWidgets.QWidget.__init__(self)
        self.parent = parent
        self.con_type = "Serial"
        
        self.serial_devices = serial_devices
        self.socket_devices = socket_devices
        self.device_list = []
        self.device_type = ""
        
        self.setupUi(self)
        self.CBOX_connection_type.addItems(["Serial", "Socket"])
        sys.path.append(dirname)
        

    def changedConnection(self, connection_type):
        self.con_type = connection_type
        
        if connection_type == "Serial":
            self.NON_con1.setText("COM")
            self.NON_con2.setText("Baud\nRate")
        else:
            self.NON_con1.setText("IP")
            self.NON_con2.setText("Port")
            
        self.fillDeviceComboBox()
        
    def fillDeviceComboBox(self):
        self.CBOX_device.clear()
        if self.con_type == "Serial":
            self.CBOX_device.addItems(self.serial_devices)
            self.device_list = self.serial_devices
            
        else:
            self.CBOX_device.addItems(self.socket_devices)
            self.device_list = self.socket_devices
            
            
    def pressedConnect(self, flag):
        if flag:
            try:
                self.device_type = self.CBOX_device.currentText()
                exec("from RFdevice import %s as dev" % self.device_type)
                exec("self.device = dev()")
                if self.con_type == "Serial":
                    self.device.port = self.TXT_con1.text()
                else:
                    self.device.tcp_ip = self.TXT_con1.text()
                    self.device.tcp_port = int(self.TXT_con2.text())
                self.device.connect()
                self.toStatusBar("Connected to the device (%s)." % self.device_type)
                self._setOutputChannel()
            except Exception as err:
                self.toStatusBar("An error while connecting the device (%s)." % err)
                self.BTN_connection.setChecked(False)
                flag = not flag
        else:
            self.device.disconnect()
            self.toStatusBar("Disconnected from the device (%s)" % self.device_type)
        self._enableGUI(flag)

            
    @property
    def isConnected(self):
        if not self.device == None:
            return self.device.is_connected()
        
    @property
    def channel_index(self):
        return self.CBOX_channel.currentIndex()
    
    def setPower(self, power):
        self.device.setPower(power, self.CBOX_channel.currentIndex())
        
    def enableOutput(self):
        self.device.enableOutput(self.CBOX_channel.currentIndex())
        
    def disableOutput(self):
        self.device.disableOutput(self.CBOX_channel.currentIndex())
        
    def setFrequency(self, frequency):
        self.device.setFrequency(frequency, self.CBOX_channel.currentIndex())
        
    def readFrequency(self):
        return self.device.getFrequency(self.CBOX_channel.currentIndex())
        
    def toStatusBar(self, txt):
        if not self.parent == None:
            self.parent.toStatusBar(txt)
        else:
            print(txt)

    def _enableGUI(self, flag):
        self.CBOX_connection_type.setEnabled(not flag)
        self.CBOX_device.setEnabled(not flag)
        
    def _setOutputChannel(self):
        self.CBOX_channel.clear()
        if "SG3" in self.device_type:
            self.CBOX_channel.addItems(["BNC", "N-type"])
        else:
            self.CBOX_channel.addItems( [str(x) for x in range(self.device._num_channels)] )

class InternalRF_Device(QtWidgets.QWidget, internal_dev_ui):
    
    def __init__(self, parent=None):
        QtWidgets.QWidget.__init__(self)
        self.parent = parent
        self.device_dict = self.parent.device_dict
        self.RF_interface = self.device_dict["rf"]
        self.RF_dict = self.RF_interface.RF_dict
        self.device_type = ""
        self.RF_interface._gui_update_signal.connect(self.updateSettings)
        
        self.setupUi(self)
        
        if self.RF_interface.isOpened:
            self.BTN_RF_con.setChecked(True)
            self.fillDeviceComboBox()
        
    def pressedRFConnect(self, flag):
        if flag:
            if not self.RF_interface.sck.socket.isConnected:
                self.toStatusBar("The main client is not connected yet.")
                self.BTN_RF_con.setChecked(False)
            else:
                self.RF_interface.connectRF()
        else:
            self.RF_interface.disconnectRF()
            self.restGUIProperties()
            
    def restGUIProperties(self):
        self.CBOX_device.clear()
        self.CBOX_channel.clear()
        self.SPB_vpp.setValue(0)
        self.BTN_connection.setChecked(False)
    
    def changedDevice(self, device:str):
        if device in self.RF_dict.keys():
            self.device_type = device
            self.device = self.RF_dict[device]
            self._setOutputChannel()
            self._updateDeviceSettings()
        else:
            self.toStatusBar("No such device in the device type!(%s)" % device)
    
    def changedOutputChannel(self, channel:int):
        self._updateDeviceSettings()
        
    def fillDeviceComboBox(self):
        self.CBOX_device.clear()
        self.CBOX_device.addItems( list(self.RF_dict.keys()) )
            
    def pressedUpdateDevices(self):
        self.fillDeviceComboBox()
            
    def pressedConnect(self, flag):
        if flag:
            if not self.BTN_RF_con.isChecked():
                self.BTN_connection.setChecked(False)
                self.toStatusBar("You should connect to the RF interface first.")
            try:
                self.RF_interface.openDevice(self.device_type)
                self.toStatusBar("Connected to the device (%s)." % self.device_type)
                self.fillDeviceComboBox()
            except Exception as err:
                self.toStatusBar("An error while connecting the device (%s)." % err)
                self.BTN_connection.setChecked(False)
                flag = not flag
        else:
            self.RF_interface.closeDevice(self.device_type)
            self.toStatusBar("Disconnected from the device (%s)" % self.device_type)
            self.CBOX_channel.clear()
            self.SPB_vpp.setValue(0)

            
    @property
    def isConnected(self):
        if not self.device == None:
            return self.device.is_connected()
        
    @property
    def channel_index(self):
        return self.CBOX_channel.currentIndex()
    
    def setPower(self, power):
        self.RF_interface.setPower(self.device_type, power, self.CBOX_channel.currentIndex())
        
    def enableOutput(self):
        self.Rf_interface.setOutput(self.device_type, self.channel_index, True)
        
    def disableOutput(self):
        self.Rf_interface.setOutput(self.device_type, self.channel_index, False)
        
    def setFrequency(self, frequency):
        self.device.setFrequency(frequency, self.CBOX_channel.currentIndex())
        
    def readFrequency(self):
        return self.device.getFrequency(self.CBOX_channel.currentIndex())
        
    def toStatusBar(self, txt):
        if not self.parent == None:
            self.parent.toStatusBar(txt)
        else:
            print(txt)

    def _enableGUI(self, flag):
        self.BTN_RF_con.setEnabled(not flag)
        self.CBOX_device.setEnabled(not flag)
        self.CBOX_channel.setEnabled(not flag)
        
    def _setOutputChannel(self):
        self.CBOX_channel.clear()
        self.CBOX_channel.addItems( ["CH%d" % (x+1) for x in range(len(self.device.settings))] )
        
    def _updateDeviceSettings(self):
        self._updateAmplitude()
        self.BTN_connection.setChecked(self.device.isConnected)
        
    def updateSettings(self, device_key:str, command:str, data:list):
        if device_key == "RF":
            if command == "CON":
                self.BTN_RF_con.setChecked(True)
                self.fillDeviceComboBox()
            elif command == "DCN":
                self.BTN_RF_con.setChecked(False)
                
        elif device_key == self.CBOX_device.currentText():
            if command in ["c", "con"]:
                flag = data[0]
                self.BTN_connection.setChecked(flag)
            elif command in ["STAT", "g"]:
                self._updateAmplitude()
                
    def _updateAmplitude(self):
        ch_idx = self.channel_index
        amplitude_dbm = self.device.settings[ch_idx]["power"]
        amplitude_vpp = self.dBm_to_vpp(amplitude_dbm)
        self.SPB_vpp.setValue(amplitude_vpp)
        
    def returnedAmplitude(self):
        vpp = self.SPB_vpp.value()
        dBm = self.vpp_to_dBm(vpp)
        ch_idx = self.channel_index
        self.RF_interface.setPower(self.device_type, ch_idx, dBm)
        

    def dBm_to_vpp(self, dBm):
        volt = 2*np.sqrt((100)/1000)*10**(dBm/20)
        return volt
    
    def vpp_to_dBm(self, vpp):
        dBm = 20*np.log10(vpp/np.sqrt(8)/(0.001 * 50)**0.5)
        return dBm

if __name__ == "__main__":
    cd = CustomDevice()
    cd.show()