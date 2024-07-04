
import os, sys
import importlib
from serial.serialutil import SerialException
from PyQt5 import uic
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtWidgets import QApplication
from sequencerGUI_theme import SequencerGUI_theme_base

from SequencerGUIcomponents import *

file_name = os.path.abspath(__file__)
dir_name = os.path.dirname(file_name)

qt_designer_file_sequencer = dir_name + UI_FILE_NAME
Ui_Main_Window, QtBaseClass = uic.loadUiType(qt_designer_file_sequencer)

class SequencerGUI(QtWidgets.QMainWindow, Ui_Main_Window, SequencerGUI_theme_base):
    
	_saved_seq_file = ""
    
	def __init__(self, device_dict={}, parent=None, theme="black"):
		super(SequencerGUI, self).__init__(parent=parent)
		self.hd = None
		self.hd_file_name = ""
		self.row_headers = []
		self.serial = ""
		self.device_dict = device_dict
		self.parent=parent
		self._theme = theme
		self.setupUi(self)

		self.full_layout = QtWidgets.QVBoxLayout(self.centralwidget)
		self.full_layout.setObjectName("full_layout")
		self.top_layout = QtWidgets.QHBoxLayout()
		self.top_layout.setObjectName("top_layout")
		self.main_layout = QtWidgets.QVBoxLayout()
		self.main_layout.setObjectName("main_layout")
		self.append_column_layout = QtWidgets.QHBoxLayout()
		self.append_column_layout.setObjectName("append_column_layout")
		self.table_layout = QtWidgets.QHBoxLayout()
		self.table_layout.setObjectName("table_layout")
		self.text_display_layout = QtWidgets.QHBoxLayout()
		self.text_display_layout.setObjectName("text_display_layout")
		self.bottom_layout = QtWidgets.QHBoxLayout()
		self.bottom_layout.setObjectName("bottom_layout")

		self.full_layout.addLayout(self.top_layout)
		self.full_layout.addLayout(self.main_layout)
		self.full_layout.addLayout(self.bottom_layout)

		self.main_layout.addLayout(self.append_column_layout)
		self.main_layout.addLayout(self.table_layout)
		self.main_layout.addLayout(self.text_display_layout)

		# top_layout
		self.label_hd = self.make_label("Hardware Definition")
		self.line_edit_hd = self.make_line_edit()
		self.btn_hd = self.make_tool_btn()

		self.top_layout.addWidget(self.label_hd)
		self.top_layout.addWidget(self.line_edit_hd)
		self.top_layout.addWidget(self.btn_hd)
		self.top_layout.setAlignment(QtCore.Qt.AlignLeft)

		# main_layout
		self.btn_append_column = self.make_push_btn("Add Column")
		self.table_time_table = self.make_table()
		self.text_display = self.make_text_browser()

		self.append_column_layout.addWidget(self.btn_append_column)
		self.append_column_layout.setAlignment(QtCore.Qt.AlignRight)
		self.table_layout.addWidget(self.table_time_table)
		self.text_display_layout.addWidget(self.text_display)

		# # bottom_layout
		self.label_serial = self.make_label("serial port(COM):", alignment=QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
		self.line_edit_serial = self.make_line_edit(max_width=100)
		self.btn_to_python = self.make_push_btn("To Python", max_width=100)
		self.btn_program = self.make_push_btn("Program", max_width=100)
		
		self.bottom_layout.addWidget(self.label_serial)
		self.bottom_layout.addWidget(self.line_edit_serial)
		self.bottom_layout.addWidget(self.btn_to_python)
		self.bottom_layout.addWidget(self.btn_program)
		self.bottom_layout.setAlignment(QtCore.Qt.AlignRight)

		# signal-slot connection
		self.btn_hd.clicked.connect(self.read_hd)
		self.btn_append_column.clicked.connect(self.table_time_table.append_column)
		self.btn_to_python.clicked.connect(self.btn_to_python_clicked_slot)
		self.btn_program.clicked.connect(self.btn_program_clicked_slot)
		self.line_edit_serial.editingFinished.connect(self.get_serial)

		if "sequencer" in self.device_dict.keys():
			self.sequencer = self.device_dict["sequencer"]
			hw_def_from_device_dict = self.sequencer.default_hw_def_dir + '/' + self.sequencer.hw_def + '.py'
			self.line_edit_serial.setText(self.sequencer.com_port)
			self.line_edit_hd.setText(hw_def_from_device_dict)
			self.read_hd_file(hw_def_from_device_dict)
            
	# make GUI components
	def make_push_btn(self, text="PushButton", max_width=0):
		btn = QtWidgets.QPushButton(self.centralwidget)
		btn.setText(text)
		if max_width > 0:
			btn.setMaximumWidth(max_width)
		return btn

	def make_tool_btn(self, text="..."):
		btn = QtWidgets.QToolButton(self.centralwidget)
		btn.setText(text)
		return btn

	def make_label(self, text="TextLabel", alignment=None):
		label = QtWidgets.QLabel(self.centralwidget)
		label.setText(text)
		if alignment != None:
			label.setAlignment(alignment)
		return label

	def make_line_edit(self, max_width = 0):
		line_edit = QtWidgets.QLineEdit(self.centralwidget)
		if max_width > 0:
			line_edit.setMaximumWidth(max_width)
		return line_edit

	def make_text_browser(self):
		text_browser = QtWidgets.QTextBrowser(self.centralwidget)
		text_browser.setMaximumHeight(100)
		return text_browser

	def make_table(self):
		return TimeTableWidget(self.hd, self, self.centralwidget, self._theme)

	# Slot methods / sub-slot methods
	def read_hd(self):
		"""
		reads a HardwareDefinition file and sets input_mapping and output_mapping
		time_table is newly generated
		"""
		# read file
		file_name, _ = QtWidgets.QFileDialog.getOpenFileName(directory="./", filter="Python Files (*.py)")
		if file_name[-3:] != ".py":
			self.text_display.append("did not select a Python module")
			return
		self.read_hd_file(file_name)
        
	def read_hd_file(self, file_name):
		dir_name = os.path.dirname(file_name)
		hd_module = os.path.basename(file_name)[:-3]

		# import the selected module(file)
		if dir_name not in sys.path:
			sys.path.append(dir_name)
		hd = importlib.import_module(hd_module)

		if "input_mapping" not in hd.__dict__.keys() or "output_mapping" not in hd.__dict__.keys():
			self.text_display.append("selected module is not a HardwareDefinition module")
			return

		self.hd = hd
		self.hd_file_name = file_name
		self.line_edit_hd.setText(dir_name + '/' + hd_module + '.py')

		# reset(delete and remake) the time_table
		self.table_layout.removeWidget(self.table_time_table)
		self.table_time_table.deleteLater()
		self.table_time_table = self.make_table()
		self.table_layout.addWidget(self.table_time_table)

		self.btn_append_column.clicked.connect(self.table_time_table.append_column)
		self.btn_program.clicked.connect(self.table_time_table.program)

	def get_serial(self):
		self.serial = self.line_edit_serial.text()
		return self.serial

	def btn_program_clicked_slot(self):
		if "runner_panel" in self.parent.panel_dict.keys():
			runner = self.parent.panel_dict["runner_panel"]
			if self._saved_seq_file == "":
				self.text_display.append("You should generate any seqeunce files first.")
				return
			else:
				runner.loadSequencerFile(self._saved_seq_file)
				self.text_display.append("Programmed to the runner.")
                
		else:
			self.text_display.append("No sequencer runner panel detected. Abort programming.")

	def btn_to_python_clicked_slot(self):
		file_name, _ = QtWidgets.QFileDialog.getSaveFileName(directory="./SequencerCodes", filter="Python Files (*.py)")
		if file_name == "":
			return

		self.table_time_table.program(run=False, save_file=True, file_name=file_name)
		self._saved_seq_file = file_name
		if self.hd == None:
			self.text_display.append(
				"No HardwareDefinition file selected. Need to modify HardwareDefinition directory manually")
		self.text_display.append("Saved the sequencer file as '%s'." % file_name)


if __name__ == "__main__":
	if QApplication.instance():
		app = QApplication.instance()
	else:
		app = QApplication(sys.argv)

	sequncer_gui = SequencerGUI()
	sequncer_gui.show()
	sequncer_gui.changeTheme("white")
# 	sys.exit(app.exec_())
