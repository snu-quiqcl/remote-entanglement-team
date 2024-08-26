# -*- coding: utf-8 -*-
"""
Created on Sat Jul  3 23:06:53 2021

@author: JHJeong32
This script is designed for a spectific usage due to lack of time.
If you are looking for general python scripts for oscilloscopes, please contact JJH.
mail: jhjeong32@snu.ac.kr
Tel.: 010-9600-3392
"""
SVR_IP   = "172.22.22.92"
SVR_PORT = 53001

from PyQt5 import uic, QtWidgets, QtGui
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtGui     import QColor
from PyQt5.QtCore    import pyqtSignal, QThread

import pyqtgraph as pg
import configparser, socket, os, pickle
import numpy as np
from queue import Queue

from Oscillo_scope_theme import Oscilloscpoe_theme_base

filename = os.path.abspath(__file__)
dirname = os.path.dirname(filename)
uifile = dirname + '/Libs/Oscilloscope_gui_MSO7054.ui'
Ui_Form, _ = uic.loadUiType(uifile)

pg.setConfigOptions(antialias=True) # This makes the plot smoother.


class MSO7054_GUI(QtWidgets.QWidget, Ui_Form, Oscilloscpoe_theme_base):

    def closeEvent(self, e):
        self.hide()
        self.pressedRunButton(0)
        self.pressedConnect()
        # self.deleteLater()
        
    def __init__(self, parent=None, theme="black"):
        QtWidgets.QWidget.__init__(self)
        self.setupUi(self)
        self.BTN_DB.setIcon(QtGui.QIcon(dirname + '/Libs/gui_save.ico'))
        self.parent = parent
        self._theme = theme
        self.CH_list = [True]  # always 1 for this version of the app
        self.x_data = {idx: [] for idx in range(len(self.CH_list))}
        self.y_data = {idx: [] for idx in range(len(self.CH_list))}
        self.vpp_data = {idx: [] for idx in range(len(self.CH_list))}
        
        self.isInitialized = False
        self.device_idx = 0
        self.ch_idx = 0
                        
        self.canvas, self.ax_dict, self.plot_dict = self._createCanvas(self.LBL_PLOT)        
        
        self.plot_fetcher = Fetcher(self, SVR_IP, SVR_PORT)
        self.plot_fetcher.waveform_signal.connect(self.updatePlot)
                
        self.cp = configparser.ConfigParser()
        
        self.Vscale    = [5]
        self.Hscale    = 5
        self.Vposition = [5]
        
        self.vmin, self.vmax =  self.VAL_VMIN.value(), self.VAL_VMAX.value()
        
        self._is_connected = False
        self.STAT_CON.setStyleSheet("background-color: rgb(0, 0, 0);color: red;font-weight: bold")
        self.CBOX_channel.setEnabled(False)
        self.BTN_run.setEnabled(False)
        # self.CBOX_channel.setStyleSheet("color: black")
        # self.BTN_run.setStyleSheet("color: black")
        self.BTN_auto.setEnabled(False)
        
        self.setWindowTitle("Oscilloscope v0.04")
        
    def _createCanvas(self, frame):
        if self._theme == "black":
            pg.setConfigOption("background", QColor(70, 70, 70))
            pg.setConfigOption('foreground', QColor(210, 210, 210))
            styles = {"color": "#D2D2D2","font-size": "15px", "font-family": "Arial"}
            self.line_colors = [QColor(141, 211, 199), QColor(254, 255, 179)]
            
        else:
            pg.setConfigOption('background', 'w')
            pg.setConfigOption('foreground', 'k')
            styles = {"color": "k", "font-size": "15px", "font-family": "Arial"}
            self.line_colors = [QColor(31, 119, 180), QColor(255, 127, 14)]
            
        self.line_width = 1
        
        canvas = pg.GraphicsLayoutWidget()
        
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(canvas)

        frame.setLayout(layout)

        ax = canvas.addPlot(row=0, col=0)
        ax.setDefaultPadding(0)
        plot0 = ax.plot(self.x_data[0],
                        self.y_data[0],
                        pen=pg.mkPen(self.line_colors[0], width=self.line_width))                
        ax.setMouseEnabled(x=False,y=False)
        ax.setLabel("bottom", "Time", **styles)
        ax.setLabel("left", "Voltage", **styles)
        
        ax1 = canvas.addPlot(row=1, col=0)
        ax1.setDefaultPadding(0)
        plot1 = ax1.plot(self.x_data[0],
                        self.vpp_data[0],
                        pen=pg.mkPen(self.line_colors[0], width=self.line_width))                
        ax1.setMouseEnabled(x=False,y=False)
        ax1.setLabel("bottom", "Time", **styles)
        ax1.setLabel("left", "Vpp", **styles)

        plot_dict = {0: plot0, 1:plot1}
        ax_dict = {0: ax, 1:ax1}
        
        
        ax.showGrid(x=True)
        ax1.showGrid(x=True)
        
        return canvas, ax_dict, plot_dict
        
    
    def updatePlot(self, wave_data):
        if (not self.isHidden() and not self.isMinimized()):
            for ch, on in enumerate(self.CH_list):
                if on:
                    y_data = wave_data["data"][ch][::2]
                    
                    # If auto, is_auto == 'auto' 
                    # Else, is_auto will be some data point
                    is_auto = str(wave_data["data"][ch])
                    
                # if not y_data[0] == "auto":
                if not is_auto == "auto":
                    # Plot waveform
                    # Load x data (time)
                    x_data = wave_data["time"][ch][::2]
                    
                    off_scale = np.linspace(-0.1, 0.1, 201)[self.Vposition[ch]]
                    x_scale = np.linspace(0.1, 0.5, 11)[self.Hscale]
                    # y_scale = np.linspace(0.1, 1.99, 11)[self.Vscale[ch]]
                                        
                    self.plot_dict[ch].setData(x_data, y_data + off_scale*np.mean(y_data))
                    self.ax_dict[ch].setXRange( np.mean(x_data) - x_scale*np.max(x_data), np.mean(x_data) + x_scale*np.max(x_data))
                    # self.ax_dict[ch].setYRange( np.mean(y_data) - y_scale*np.ptp(y_data), np.mean(y_data) + y_scale*np.ptp(y_data))
                    self.ax_dict[ch].setYRange(self.vmin, self.vmax)
                    
                    self.LBL_CH_VAVG.setText(  self.VPlotScaler( np.mean(wave_data["data"][0])  ) )
                    
                    self.CH_P2P = np.ptp(wave_data["data"][0])
                    self.LBL_CH_VPP.setText(  self.VPlotScaler(  np.ptp(wave_data["data"][0])  ) )
        
                    self.LBL_CH_FREQ.setText( self.FPlotScaler( wave_data["freq"][0] ) )
                    
                    # Plot vpp data
                    vpp_data = np.abs(np.max(y_data) - np.min(y_data))
                    self.vpp_data[ch].append(vpp_data)
                    if len(self.vpp_data[ch]) > 50:
                        self.vpp_data[ch].pop(0)
                    self.plot_dict[ch+1].setData(list(range(len(self.vpp_data[ch]))), self.vpp_data[ch])
                    self.ax_dict[ch+1].setYRange(0, 1.1*np.max(self.vpp_data[ch]))
                    
                else:
                    self.LBL_CH_VAVG.setText("Settings...")
                    self.LBL_CH_VPP.setText("Settings...")
                    self.LBL_CH_FREQ.setText("Settings...")
                    
            QtWidgets.QApplication.processEvents()

    def changedChannel(self, channel):
        if channel == "CH1":
            ch_id = 0
        elif channel == "CH2":
            ch_id = 1
        elif channel == "CH3":
            ch_id = 2
        elif channel == "CH4":
            ch_id = 3
        self.CBOX_channel.setEnabled(False)
        self.BTN_run.setEnabled(False)
        # self.CBOX_channel.setStyleSheet("color: black")
        # self.BTN_run.setStyleSheet("color: black")     
        self.ch_idx = ch_id      
        self.plot_fetcher.queue.put("CH:%d\n" % self.ch_idx)  
        self.plot_fetcher.start()
    
    def _ch_changed(self):
        self.CBOX_channel.setEnabled(True)
        self.BTN_run.setEnabled(True)
        # self.CBOX_channel.setStyleSheet("color: white")
        # self.BTN_run.setStyleSheet("color: white")
                
    def changedVplotMinMax(self):
        self.vmin, self.vmax =  self.VAL_VMIN.value(), self.VAL_VMAX.value()
        
    def ScaleChange(self, ScaleInt):
        objName = self.sender().objectName()
        if not objName.find('CH1') == -1:
            ch_index = 0
        elif not objName.find('CH2') == -1:
            ch_index = 1
        else:
            ch_index = -1 # Horizontal slider
            
        if not objName.find("VP") == -1:
            self.Vposition[ch_index] = ScaleInt
        elif not objName.find("VS") == -1:
            self.Vscale[ch_index] = ScaleInt
        else:
            self.Hscale = ScaleInt

    def VPlotScaler(self, data):
        data = abs(data)
        if data == 0.0:
            return ('----')     
        elif 1 <= data:
            val, unit = data, 'V'
        elif 1e-4 <= data < 1:
            val, unit = data*1e3, 'mV'
        elif 1e-7 <= data < 1e-4:
            val, unit = data*1e6, 'μV'
        
        return ("%.2f %s" % (val, unit))
    
    def FPlotScaler(self, data): 
        if data <= 1e12:
            if data < 1e3:
                val, unit = data, 'Hz'
            elif 1e3 <= data < 1e6:
                val, unit = data/1e3, 'kHz'
            elif 1e6 <= data < 1e9:
                val, unit = data/1e6, 'MHz'
            elif 1e9 <= data:
                val, unit = data/1e9, 'GHz'
                
            return ("%.2f %s" % (val, unit))
        else :
            return ('----')
    
    def pressedConnect(self):
        if self._is_connected:
            self.STAT_CON.setStyleSheet("background-color: rgb(0, 0, 0);color: red;font-weight: bold")
            self.STAT_CON.setText("Discon")
            self.BTN_CON.setText("Connect")
            self.CBOX_channel.setEnabled(False)
            self.BTN_run.setEnabled(False)
            # self.CBOX_channel.setStyleSheet("color: black")
            # self.BTN_run.setStyleSheet("color: black")
            self.plot_fetcher.disconnect()
            self._is_connected = False
        else:
            try:
                self.plot_fetcher.connect()
                self.STAT_CON.setStyleSheet("background-color: rgb(255, 255, 255);color: green;font-weight: bold")
                self.STAT_CON.setText("Con")
                self.BTN_CON.setText("Disconnect")
                self.CBOX_channel.setEnabled(True)
                self.BTN_run.setEnabled(True)
                # self.CBOX_channel.setStyleSheet("color: white")
                # self.BTN_run.setStyleSheet("color: white")
                self._is_connected = True
            except:
                print("Failed to connect to the server")            
        
    def pressedAutoSet(self):
        # pass
        if self.plot_fetcher.isRunning():
            self.plot_fetcher.queue.put("AUTO:%d" % self.device_idx)
            
    def pressedRunButton(self, flag):
        if flag:
            msg = "DATA:%d" % self.device_idx
            self.plot_fetcher.queue.put(msg)
            self.plot_fetcher.start()
            # self.plot_fetcher.scope.sendall(bytes(msg + "\n", "latin-1"))
            self.CBOX_channel.setEnabled(False)
            self.BTN_CON.setEnabled(False)
            
        else:
            self.plot_fetcher.queue.queue.clear()
            self.plot_fetcher.stop()
            self.CBOX_channel.setEnabled(True)
            self.BTN_CON.setEnabled(True)
            self.BTN_run.setChecked(False)
            # self.plot_fetcher.wait(500)
            
    
    def pressedSaveButton(self):
        pass
            
class Fetcher(QThread):
    
    waveform_signal = pyqtSignal(dict)
    
    def __init__(self, parent=None, svr_ip="", svr_port=0):
        super().__init__()
        self.parent = parent
        self.ip = svr_ip
        self.port = svr_port
        self.queue = Queue()
        self.scope = None
        self.data_buffer = []
        self.msg_buffer = []
    
    def stop(self):
        self.data_buffer = []
        self.msg_buffer = []
        self.quit()
    
    def connect(self):
        self.scope = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.scope.settimeout(100)
        self.scope.connect((self.ip, self.port))
        self.scope.sendall(bytes("REQ:%d\n" % self.parent.device_idx, 'latin-1'))
    
    def disconnect(self):
        self.scope.sendall(bytes("STOP\n", 'latin-1'))
        self.scope.close()
        self.scope = None
        self.data_buffer = []
        self.msg_buffer = []
        
    def run(self):
        try:
            while self.queue.qsize():
                # Receiving the waveform data
                if self.parent.BTN_run.isChecked():
                    msg = self.queue.get()                    
                    self.scope.sendall(bytes(msg + "\n", "latin-1"))
                    while True:
                        packet = self.scope.recv(4096)
                        # If no data is received, break
                        if not packet: 
                            break
                        # If the packet is a waveform data
                        if not b'\r\n' in packet:
                            self.data_buffer.append(packet)                    
                        else:
                            temp = b"".join(self.data_buffer)
                            temp += packet[:packet.find(b'\r\n')]
                            self.data_dict = pickle.loads(temp)
                            self.waveform_signal.emit(self.data_dict)
                            self.data_buffer = [packet[packet.find(b'\r\n')+2:]]
                            
                            if self.parent.BTN_run.isChecked():
                                msg = "DATA:%d\n" % self.parent.device_idx
                                self.queue.put(msg)
                                self.msleep(50)
                            break
                # Send and Receive message data
                else:
                    msg = self.queue.get()
                    self.scope.sendall(bytes(msg + "\n", "latin-1"))
                    while True:
                        packet = self.scope.recv(1024)
                        # If no data is received, break
                        if not packet: 
                            break
                        # If the packet is a massage dict
                        if not b'\r\n' in packet:
                            self.msg_buffer.append(packet)                    
                        else:
                            temp = b"".join(self.msg_buffer)
                            temp += packet[:packet.find(b'\r\n')]
                            msg_recv = pickle.loads(temp)
                            
                            if "CH" in msg_recv.keys():
                                if msg_recv["CH"].lower() == "done":
                                    self.parent._ch_changed() 
                            break
                        
            # Stop the thread
            self.stop()
            
        except socket.error as exc:
            print("Couldn't connect to the oscilloscope server. (%s)" % exc)
            self.parent.BTN_run.setChecked(False)
                
#%%
if __name__ == "__main__":
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    OSC = MSO7054_GUI(theme="black")
    OSC.changeTheme("black")
    OSC.show()
    app.exec_()
