# -*- coding: utf-8 -*-
"""
Created on Fri Oct  6 19:27:08 2023

@author: QCP75
"""

import os, time
import numpy as np
import pandas as pd
import datetime

import pyqtgraph as pg
pg.setConfigOptions(antialias=True)

filename = os.path.abspath(__file__)
dirname = os.path.dirname(filename)

# PyQt libraries
from PyQt5 import uic, QtWidgets, QtGui
from PyQt5.QtCore    import pyqtSignal, QMutex, QWaitCondition, QThread
from PyQt5.QtGui     import QColor
from PyQt5.QtWidgets import QVBoxLayout, QFileDialog

# Custom widgets
from .Connection_widget import CustomDevice, InternalRF_Device
# from .

ph_ui_file = dirname + "/ui/parametric_heating.ui"
ph_ui, _ = uic.loadUiType(ph_ui_file)

def vpp_to_dBm(vpp):
    dBm = 20*np.log10(vpp/np.sqrt(8)/(0.001 * 50)**0.5)
    return dBm

def checkError(func):
    """Decorator that checks the error of methods..
    """
    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except Exception as ee:
            self.toStatusBar("An error while running '%s'. (%s)" % (func.__name__, ee))
            return
    return wrapper


class ParametricHeatingGUI(QtWidgets.QWidget, ph_ui):
    
    
    def __init__(self, device_dict={}, parent=None, theme="white"):
        QtWidgets.QWidget.__init__(self)
        self.device_dict = device_dict
        self.parent = parent
        self._theme = theme
        
        self.sequencer = self.device_dict["sequencer"]
        self.sequencer.sig_occupied.connect(self._setInterlock)

        self.setupUi(self)
        self.canvas, self.ax, self.plot = self._create_canvas(self.GBOX_plot)
        
        self.initUi()
        self.plot_handler = PlotHandler(self)
        self.plot_handler.update_signal.connect(self.updatePlot)
        self.plot_handler.finished_signal.connect(self.finishedRun)
        
        self.disable_list = [self.BTN_start, self.con.BTN_connection]
        
        
    def showEvent(self, event):
        self.updatePlot()

    def initUi(self):
        self.custom_con = CustomDevice(self)
        self.internal_con = InternalRF_Device(self) # This should be changed later
        
        self.GBOX_device.layout().addWidget(self.custom_con)
        self.GBOX_device.layout().addWidget(self.internal_con)
        
        self.changeConnectionDevice()
        
        if not os.path.isdir(dirname + "/../data/parametric_heating"):
            os.mkdir(dirname + "/../data/parametric_heating")
                
    def updatePlot(self):      
        if (not self.isHidden() and not self.isMinimized()):
            if self.CBOX_Auto.isChecked():
                self.ax.setYRange(self.plot_handler.y_min, self.plot_handler.y_max)
                self.TXT_ymax.setText(self.plot_handler.y_max)
                self.TXT_ymin.setText(self.plot_handler.y_min)
                
            else:
                y_max = self.plot_handler.y_max
                y_min = self.plot_handler.y_min
                
                self.ax.setYRange(y_min, y_max)
                
            self.progressBar.setValue(self.plot_handler.percentage)
            QtWidgets.QApplication.processEvents()
            

    def changeConnectionDevice(self):
        if self.CBOX_custom.isChecked():
            self.internal_con.hide()
            self.custom_con.show()
            self.con = self.custom_con
        else:
            self.custom_con.hide()
            self.internal_con.show()
            self.con = self.internal_con
       
    @checkError
    def pressedStartButton(self, flag):
        self.BTN_save.setEnabled(not flag)
        self.BTN_save.setEnabled(not flag)
        
        if flag:
            if not self.sequencer.is_opened:
                self.toStatusBar("The FPGA is not opened!")
                self.BTN_start.setChecked(False)
            else:
                try:
                    f_init, f_end, f_step = float(self.TXT_init_freq.text())*1e6, \
                                            float(self.TXT_end_freq.text())*1e6,  \
                                            float(self.TXT_delta_freq.text())*1e3
                    exposure_time = int(self.TXT_exp_time.text())
                    average_number = int(self.TXT_avg_num.text())
                    power_in_dBm = vpp_to_dBm(float(self.TXT_Vpp.text()))
                    
                    self.plot_handler.switchingDevice(flag, power_in_dBm)
                    self.plot_handler.setFrequencyRange(f_init, f_end, f_step)
                    self.con.setFrequency(f_init)
                    self.plot_handler._resetProgress()
                    self.plot_handler._setSequencerFile(exposure_time, average_number)
                    self.changeXLimit()
                except Exception as ee:
                    self.toStatusBar("An error while setting the experiment (%s)." % ee)
                    self.BTN_start.setChecked(False)
                    self.BTN_save.setEnabled(True)
                    self.BTN_save.setEnabled(True)
                    return
                
                self.sequencer.occupant = "parametric_heating"
                self.sequencer.sig_occupied.emit(True)                    
                self.plot_handler.start()
                self.toStatusBar("Started heating.")
                
        else:
            self.plot_handler.wakeupThread()  # This make sure the thread stops
            self.sequencer.occupant = ""
            self.sequencer.sig_occupied.emit(False)
            
    @checkError
    def pressedSaveButton(self):
        file_name, _ = QFileDialog.getSaveFileName(self, 'Save file', os.path.abspath(dirname + "/../data/"))
        if file_name == "":
            self.toStatusBar("Aborted saving a data file.")
        else:
            self.plot_handler.setSaveFileName(file_name)
            self.plot_handler.scan_idx = self.plot_handler.total_length # This make sure the thread's logic jumps to the save logic
            self.plot_handler.start()
        
    @checkError
    def pressedLoadButton(self):
        file_name, _ = QFileDialog.getOpenFileName(self, 'Open file', os.path.abspath(dirname + "/../data/"))
        if file_name == "":
            self.toStatusBar("Aborted loading a save file.")
        else:
            pass
            # with open (file_name, "rb") as fr:
            #     pkl_data = pickle.load(fr)

    @checkError
    def cancelStartButton(self, no_input=True):
        self.BTN_start.setChecked(False)
        self.BTN_start.setText("Start")

    
    @checkError
    def changedYLimit(self, no_input=True):
        y_max = float(self.TXT_ymax.text())
        y_min = float(self.TXT_ymin.text())
        self.ax.set_ylim(y_min, y_max)
        self.canvas.draw()
        
    @checkError
    def changeXLimit(self, no_input=True):
        x_min = float(self.TXT_init_freq.text())
        x_max = float(self.TXT_end_freq.text())
        self.ax.set_xlim(x_min, x_max)
        
    @checkError
    def finishedRun(self):
        self.BTN_start.setChecked(False)
        self.progressBar.setValue(100)
                
        
    def toStatusBar(self, txt):
        if not self.parent == None:
            self.parent.toStatusBar(txt)
        else:
            print(txt)
            
    def _setInterlock(self, occupied_flag):
        if occupied_flag:
            if not self.sequencer.occupant == "parametric_heating":
                self._setEnableObjects(False)
            else:
                self.con.BTN_connection.setEnabled(False)
        else:
            self._setEnableObjects(True)
            
    def _setEnableObjects(self, flag):
        for enb_object in self.disable_list:
            enb_object.setEnabled(flag)
            
    def _create_canvas(self, frame):
        if self._theme == "black":
            pg.setConfigOption('background', QColor(40, 40, 40))
            styles = {"color": "#969696","font-size": "15px", "font-family": "Arial"}
            self.line_color = QColor(141, 211, 199)
            
        else:
            pg.setConfigOption('background', 'w')
            pg.setConfigOption('foreground', 'k')
            styles = {"color": "k", "font-size": "15px", "font-family": "Arial"}

            self.line_color = QColor(31, 119, 180)
        self.line_width = 3
        
        canvas = pg.GraphicsLayoutWidget()
        ax = canvas.addPlot()
        ax.setDefaultPadding(0)

        layout = QVBoxLayout()
        layout.layoutLeftMargin = 0
        layout.layoutRightMargin = 0
        layout.layoutTopMargin = 0
        layout.layoutBottomMargin = 0
        layout.addWidget(canvas)
        
        frame.setLayout(layout)
        
        plot = ax.plot([], [], pen=pg.mkPen(self.line_color, width=self.line_width))
        
        ax.setLabel("bottom", "Frequency (MHz)", **styles)
        ax.setLabel("left", "PMT counts", **styles)
        
        return canvas, ax, plot

#%%
class PlotHandler(QThread):
    
    update_signal = pyqtSignal()
    finished_signal = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__()
        self.parent  = parent
        self.ax      = parent.ax
        self.plot    = parent.plot
        self.con     = parent.con
        
        self.sequencer = self.parent.sequencer
        self.sequencer.sig_seq_complete.connect(self._completedProgress)
        
        # running
        self.cond = QWaitCondition()
        self.mutex = QMutex()
        self.status = "standby"
        
        self._resetProgress()
        
        self.save_file_dir = os.path.abspath(dirname + "/../data/parametric_heating")
        self.save_file_name = ""
        
        self.y_max = 1
        self.y_min = 0
        self.percentage = 100
        
    @checkError
    def _resetProgress(self):
        self.x_data = []
        self.y_data = []
        self.scan_idx = 0
        
    @checkError
    def _setSequencerFile(self, exposure_time_in_ms, average_number):
        # CHECK FOR SYNTAX
        self.sequencer.loadSequencerFile(seq_file= dirname + "/simple_exposure.py",
                                         replace_dict={11:{"param": "EXPOSURE_TIME_IN_MS", "value": exposure_time_in_ms},
                                                       12:{"param": "NUM_REPEAT", "value": average_number}})

    @checkError
    def _completedProgress(self, no_input=True):
        if self.parent.BTN_start.isChecked():
            raw_pmt_count = np.asarray(self.sequencer.data[0]) # kind of deep copying...
            if len(raw_pmt_count) > 1:
                pmt_count = np.mean(raw_pmt_count[:, 2])
            else:
                pmt_count = raw_pmt_count[0][2]
                
            self.scan_idx += 1
            
            self.x_data.append(self.current_frequency/1e6)
            self.y_data.append(pmt_count)
            
            self.y_max = np.ceil(np.max(self.y_data))
            self.y_min = np.floor(np.min(self.y_data))
            
            self.percentage = int( (self.scan_idx+1)*100/ self.total_length )
            
            self.update_signal.emit()
            
        self.wakeupThread()
        
    def wakeupThread(self):
        self.cond.wakeAll()
        
    @checkError
    def switchingDevice(self, flag, power):
        self.con.setPower(power)
        if flag:
            self.con.enableOutput()
        else:
            self.con.disableOutput()
        
    @checkError
    def setFrequencyRange(self, init, end, step):
        self.init, self.end, self.step = init, end, step
        self.total_length = int((self.end - self.init)/self.step) + 1 # The end frequency should be included
        
    @checkError
    def runSequencer(self):
        self.sequencer.runSequencerFile()
        
    @checkError
    def run(self):
        while self.parent.BTN_start.isChecked():
            self.mutex.lock()
            self.status = "running"
            if self.scan_idx <= self.total_length:
                self.current_frequency = self.init + self.step*self.scan_idx
                self.con.setFrequency(self.current_frequency)
                
                if self.parent.CBOX_precise.isChecked():
                    while not (self.current_frequency == self.con.readFrequency()):
                        time.sleep(0.3)
                
                self.status = "ready for sequencer"
                self.runSequencer()
                
                self.status = "wait for mutex"
                self.cond.wait(self.mutex)
                self.mutex.unlock()
                
            else: # This is not a good design, but I reused this as a save function.
                self.sequencer.occupant = ""
                self.sequencer.sig_occupied.emit(False)
                self.switchingDevice(False, -30)
                self.saveData()
                self.finished_signal.emit()
                self.parent.BTN_start.setChecked(False)
                self.status = "standby"
                self.mutex.unlock()
                
    @checkError
    def setSaveFileName(self, file_name=""):
        self.save_file_name = file_name


    @checkError
    def saveData(self):
        if self.save_file_name == "":
            save_file_name = dirname + "/../data/parametric_heating/%s_parametric_heating" % datetime.datetime.now().strftime("%y%m%d_%H%M%S")
        else:
            save_file_name = self.save_file_name
        
        detail_string = self._makeDetails()
        df = pd.DataFrame({"frequency[MHz]": self.x_data,
                           "Photon counts": self.y_data})
        
        
        try:
            with open (save_file_name + ".csv", "w") as fp:
                fp.write(detail_string)
            df.to_csv(save_file_name + ".csv", header=True, index=False, mode="a")
            
            window_qpixmap = self.parent.grab()
            window_qpixmap.save(save_file_name + ".png", "PNG")
            
            self.setSaveFileName() # reset the save file name.
            msg = "Saved the data file.(%s)" % save_file_name
        except Exception as ee:
            msg = "An error occured while saving the data.(%s)" % ee
        self.toStatusBar(msg)
        
        
    def _makeDetails(self):
        detail = """Experimental data of parametric heating.
%s
Initial Modulation frequency [MHz]: %s
End Modulation frequency [MHz]: %s
Modulation Vpp [V]: %s
369-nm Laser frequency [THz]: %s
Trap RF frequency [MHz]: %s
Exposure time [ms]: %s
Average number: %s
==============================================
""" % ( datetime.datetime.now().strftime("%y-%m-%d %H:%M:%S"),
                        self.parent.TXT_init_freq.text(),
                        self.parent.TXT_end_freq.text(),
                        self.parent.TXT_Vpp.text(),
                        self.parent.TXT_laser_freq.text(),
                        self.parent.TXT_RF_freq.text(),
                        self.parent.TXT_exp_time.text(),
                        self.parent.TXT_avg_num.text())
        return detail
            
    def toStatusBar(self, txt):
        if not self.parent == None:
            self.parent.toStatusBar(txt)
        else:
            print(txt)
            

if __name__ == "__main__":
    ph = ParametricHeatingGUI({"sequencer"})
    ph.show()