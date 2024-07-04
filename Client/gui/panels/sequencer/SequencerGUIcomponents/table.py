"""
This module defines TimeTableWidget class which is used as the time_table in SequencerGUI
This class inherits QtWidgets.QTableWidget
row: time sequence of each elements(e.g. output, counter, stopwatch)
column: one time interval

This class also converts the time_table into python codes
"""
import os
from datetime import datetime
from PyQt5 import QtWidgets, QtGui, QtCore
from SequencerProgram_v1_07 import SequencerProgram, reg

from .items import *
from .interval import *
from .const import *
from .utility import *

file_name = os.path.abspath(__file__)
dir_name = os.path.dirname(file_name)

class TimeTableWidget(QtWidgets.QTableWidget):
	def __init__(self, hardware_definition, GUI, parent=None, theme="black"):
		super().__init__(parent=parent)
		self._theme = theme
		self.hd = hardware_definition
		self.interval_list = []
		self.GUI = GUI
		self.set_new_sequencer()
		self.set_row_headers()
		self.append_column()

		self.reg_used_flag = [False] * REG_LENGTH
		self.reg_assign_dict = dict()
		self.iter_index_dict = dict()
		self.instruction_label_list = []

		self.cellClicked.connect(self.cell_clicked_slot)
		self.cellChanged.connect(self.cell_changed_slot)
		self.setCurrentCell(0, 0)


	def set_new_sequencer(self):
		"""
		Generate a new SequencerProgram instance
		When programming a sequencer repeatedly, need to use different sequencer each time
		"""
		self.s = SequencerProgram()
		for interval in self.interval_list:
			interval.set_sequencer(self.s)

	# table-related methods
	def set_row_headers(self):
		"""
		Generates self.row_headers according to hd.input_mapping and hd.output_mapping
		self.row_headers define the order of rows of time_table
		"""
		# define self.row_headers
		self.row_headers = [ROW_HEADER_ADD_DELETE_COLUMN,
							ROW_HEADER_INSTRUCTION_LABELS, 
							ROW_HEADER_TIME_LENGTH_UNIT, 
							ROW_HEADER_TIME_LENGTH,
							]
		if self.hd != None:
			for (mapping_name, pin_name) in self.hd.output_mapping.items():
				row_header = mapping_name + ROW_HEADER_OUTPUT_SUFFIX
				if getattr(self.hd, row_header, "") != "":
					self.row_headers.append(row_header)
			for (pin_name, mapping_name) in self.hd.input_mapping.items():
				row_header = mapping_name + ROW_HEADER_COUNTER_SUFFIX
				if getattr(self.hd, row_header + "_enable", "") != "":
					self.row_headers.append(row_header)
			for (pin_name, mapping_name) in self.hd.input_mapping.items():
				row_header = mapping_name + ROW_HEADER_STOPWATCH_SUFFIX
				if getattr(self.hd, row_header + "_reset", "") != "":
					self.row_headers.append(row_header)
		self.row_headers.append(ROW_HEADER_TLI)
		self.row_headers.append(ROW_HEADER_FIFO)
		self.row_headers.append(ROW_HEADER_BRANCH)

		# set row header of the table
		self.setRowCount(len(self.row_headers))
		for r in range(self.rowCount()):
			self.setRowHeight(r, TABLE_CELL_H)
			self.setVerticalHeaderItem(r, QtWidgets.QTableWidgetItem(self.row_headers[r]))
			self.verticalHeaderItem(r).setSizeHint(QtCore.QSize(TABLE_VERTICAL_HEADER_W, -1))

	def insert_column(self, column_number):
		"""
		column_number: int
		Add one column(interval) of the table at (column_number)-th column
		The type of each item(cell) in the column is determined according to the row_headers
		The generated interval is added to self.interval_list
		"""
		interval = TimeInterval(self)

		# adjust column_number if out-of-range
		if column_number > self.columnCount():
			column_number = self.columnCount()
		elif column_number < 0:
			column_number = 0

		# insert column
		self.insertColumn(column_number)
		self.setColumnWidth(column_number, TABLE_CELL_W)
		self.setHorizontalHeaderItem(column_number, QtWidgets.QTableWidgetItem(""))

		# generate item for each cell
		for r in range(self.rowCount()):
			if self.row_headers[r] == ROW_HEADER_ADD_DELETE_COLUMN:
				self.setItem(r, column_number, AddDeleteColumnItem(interval, self._theme))
			elif self.row_headers[r] == ROW_HEADER_INSTRUCTION_LABELS:
				self.setItem(r, column_number, InstructionLabelsItem(interval, self._theme))
			elif self.row_headers[r] == ROW_HEADER_TIME_LENGTH_UNIT:
				self.setItem(r, column_number, TimeLengthUnitItem(interval, self._theme))
			elif self.row_headers[r] == ROW_HEADER_TIME_LENGTH:
				self.setItem(r, column_number, TimeLengthItem(interval, self._theme))
			elif self.row_headers[r].endswith(ROW_HEADER_OUTPUT_SUFFIX):
				self.setItem(r, column_number, OutputItem(interval, self._theme))
			elif self.row_headers[r].endswith(ROW_HEADER_COUNTER_SUFFIX):
				self.setItem(r, column_number, CounterItem(interval, self._theme))
			elif self.row_headers[r].endswith(ROW_HEADER_STOPWATCH_SUFFIX):
				self.setItem(r, column_number, StopwatchItem(interval, self._theme))
			elif self.row_headers[r] == ROW_HEADER_TLI:
				self.setItem(r, column_number, ReadOnlyItem(interval, self._theme))
			elif self.row_headers[r] == ROW_HEADER_FIFO:
				self.setItem(r, column_number, WriteToFIFOItem(interval, self._theme))
			elif self.row_headers[r] == ROW_HEADER_BRANCH:
				self.setItem(r, column_number, BranchItem(interval, self._theme))
			else:
				# This is in fact an error
				self.setItem(r, column_number, TimeTableWidgetItem(interval, self._theme))
			
			interval.append_item(self.item(r, column_number))
		self.insert_interval(interval, column_number)

	def append_column(self):
		"""
		Add one column(interval) of the table at the end
		The type of each item(cell) in the column is determined according to the row_headers
		The generated interval is added to self.interval_list
		"""
		self.insert_column(self.columnCount())

	def delete_column(self, column_number):
		"""
		column_number: int
		Delete (column_number)-th column(interval) of the table
		When column_number is out of range(negative or larger than self.columnCount()),
		no column is deleted
		"""
		if column_number < 0 or column_number >= self.columnCount():
			return

		self.delete_interval(column_number)
		self.removeColumn(column_number)

		# need to check all instructions because of branches
		# e.g. when a column(with instruction labels) being targeted is deleted, should raise an error
		self.check_all_instructions()

	def insert_interval(self, interval, column_number):
		"""
		interval: TimeInterval
		column_number: int
		Insert an interval in self.interval_list
		As self.interval_list is a double-linked list, this method also handles the pointer relation of intervals

		Note: this method should always be used as a sub-method of self.insert_column(column_number)
		so that the columns and intervals coincide
		"""
		if column_number < 0:
			column_number = 0
		elif column_number > len(self.interval_list):
			column_number = len(self.interval_list)

		if column_number > 0:
			self.interval_list[column_number-1].set_next_interval(interval)
			interval.set_prev_interval(self.interval_list[column_number-1])
		if column_number < len(self.interval_list):
			interval.set_next_interval(self.interval_list[column_number])
			self.interval_list[column_number].set_prev_interval(interval)

		self.interval_list.insert(column_number, interval)

	def delete_interval(self, column_number):
		"""
		column_number: int
		Delete an interval in self.interval_list
		As self.interval_list is a double-linked list, this method also handles the pointer relation of intervals
		if column_number is out of range(negative or larger than len(self.interval_list)),
		no interval is deleted

		Note: this method should always be used as a sub-method of self.delete_column(column_number)
		so that the columns and intervals coincide
		"""
		if column_number < 0 or column_number >= len(self.interval_list):
			return

		if column_number > 0:
			self.interval_list[column_number-1].set_next_interval(self.interval_list[column_number].next_interval)
		if column_number < len(self.interval_list) - 1:
			self.interval_list[column_number+1].set_prev_interval(self.interval_list[column_number].prev_interval)

		del self.interval_list[column_number]

	# utility methods
	def check_all_instructions(self):
		"""
		Check instruction of all intervals in self.interval_list
		"""
		for interval in self.interval_list:
			interval.check_instruction()

	def write_text_display(self, string):
		"""
		string: str
		Write(show) string on the text_display(text_browser) of the GUI window
		"""
		self.GUI.text_display.append(string)

	def get_serial(self):
		"""
		return: str
		Returns a string written in line_edit_serial of GUI
		"""
		return self.GUI.get_serial()

	# program(convert to python codes) methods
	def program(self, run=True, save_file=False, file_name=None, yaml_file_name=None):
		"""
		run: boolean.
		save_file: boolean
		file_name: str
		yaml_file_name: str
		return: str
		Converts the time_table into a python file(code) and returns the generated file in string
		to save the data fetched from sequencer (after running the python file),
		YAML data type is used.
		Currently, the data is saved in the rabi oscillation form.
		In future revision, it needs to save data in much more general format.

		when run == True, this method actually runs the generated python file
		when save_file == True, this method saves the generated python file with the designated file_name
		when file_name == None, 
			"SequencerCodes/sequencerGUI_toPython_yymmdd_HHMMSS.py" is used as the default file_name for the saved file
			(yymmdd_HHMMSS is the datetime when this method saves the file)
		when yaml_file_name == None, 
			"SequencerData/sequencerGUI_data_yymmdd_HHMMSS.yaml" is used as the default yaml_file_name to save the data fetched from sequencer
			(yymmdd_HHMMSS is the datetime when this method runs/saves the file)
		"""
		# check errors. if there are any errors, return
		error_columns = []
		for c, interval in enumerate(self.interval_list):
			if interval.is_error():
				error_columns.append(c)
		if len(error_columns) > 0:
			self.write_text_display("Instruction Error in columns {}".format(error_columns))
			return

		self.reset_instruction_label_list()
		self.assign_register()
		self.reset_iter_index()

		python_file_header, python_file_main, python_file_footer = self.read_template(TEMPLATE_FILE_NAME)
		python_file_main = python_file_main.replace("{sequencer_code}", self.get_sequencer_code())

		# Note, temporarily use same code for run==True and run==False (i.e. no if __name__=="__main__")
		for i in range(len(self.iter_index_dict)-1, -1, -1):
			iter_index_string = ITER_INDEX_PREFIX + str(i)
			pre_python_file_main = "{}{} = dict()\n\n".format(DATA_DICT_PREFIX, i+1)
			python_file_main = pre_python_file_main + python_file_main
			python_file_main += "\ntime_length_key = str({}/1000) + 'us'\n".format(iter_index_string)
			python_file_main += "{}{}[time_length_key] = {}{}\n".format(DATA_DICT_PREFIX, i, DATA_DICT_PREFIX, i+1)
			python_file_main = place_code_in_for_loop(iter_index_string, self.iter_index_dict[iter_index_string], python_file_main)
		if len(self.iter_index_dict) > 0:
			python_file_main = "{}0 = dict()\n\n".format(DATA_DICT_PREFIX) + python_file_main
		python_file = python_file_header + python_file_main + python_file_footer
		if save_file:
			if file_name == None:
				# use current datetime in default file_name so that file_names do not coincide
				now_string = datetime.now().strftime("%y%m%d_%H%M%S")
				file_name = "SequencerCodes/sequencerGUI_toPython_{}.py".format(now_string)
			f = open(file_name, 'w')
			f.write(python_file)
			f.write("\n")
			f.close()
		if run:
			exec(python_file)

		return python_file

	# sub-methods of self.program()
	# instruction_label related methods
	def reset_instruction_label_list(self):
		"""
		resets self.instruction_label_list
		self.instruction_label_list contains all the instruction labels used in the time_table
		"""
		self.instruction_label_list = []
		for interval in self.interval_list:
			for label in interval.instruction_labels:
				self.instruction_label_list.append(label)

	def get_instruction_label(self):
		"""
		return: str
		makes and returns a new instruction label that does not overlap with other instruction labels in the table
		"""
		counter = 0
		while True:
			label = INSTRUCTION_LABEL_PREFIX + str(counter)
			if label not in self.instruction_label_list:
				break
			counter += 1
		self.instruction_label_list.append(label)
		return label

	# register assignment related methods
	def assign_register(self):
		"""
		Assign registers for branch instructions
		register assignment information is stored in self.reg_assign_dict(key: branch target, value: register index)
		"""
		self.find_unused_register()
		self.reg_assign_dict = dict()
		for r in range(self.rowCount()):
			if self.row_headers[r] == ROW_HEADER_BRANCH:
				for c in range(self.columnCount()):
					target = self.item(r, c).get_target_from_text()
					if target != "" and target not in self.reg_assign_dict.keys():
						self.reg_assign_dict[target] = self.get_unused_register_index()

	def find_unused_register(self):
		"""
		Run through time_table and check which registers are being used
		register usage information is stored in self.reg_used_flag
		"""
		self.reg_used_flag = [False] * REG_LENGTH

		for r in range(self.rowCount()):
			if self.row_headers[r].endswith(ROW_HEADER_COUNTER_SUFFIX)		\
			or self.row_headers[r].endswith(ROW_HEADER_STOPWATCH_SUFFIX)	\
			or self.row_headers[r] == ROW_HEADER_TLI:
				for c in range(self.columnCount()):
					item = self.item(r, c)
					if QtCore.QRegExp(string_to_regular_expression("read reg[n]")).exactMatch(item.text()):
						self.reg_used_flag[item.get_reg_index_from_text()] = True
			elif self.row_headers[r] == ROW_HEADER_FIFO:
				for c in range(self.columnCount()):
					item = self.item(r, c)
					if QtCore.QRegExp(string_to_regular_expression("reg[n], reg[n], reg[n], event_label")).exactMatch(item.text()):
						reg_indices = item.get_reg_indices_from_text()
						for i in range(3):
							self.reg_used_flag[reg_indices[i]] = True

	def get_unused_register_index(self):
		"""
		return: int
		According to self.reg_used_flag, returns the index of which the register is not being used
		Returns -1 if all registers are being used (should raise an error instead in further revision)
		"""
		for i in range(REG_LENGTH-1, -1, -1):
			if not self.reg_used_flag[i]:
				self.reg_used_flag[i] = True
				return i
		# should raise an error
		self.write_text_display("all registers are used. program failed.")
		return -1

	# iter_index related methods
	def reset_iter_index(self):
		"""
		resets self.iter_index_dict which stores the mapping information between iter_index and time_range
		"""
		self.iter_index_dict = dict()

	def get_iter_index_string(self, time_range):
		"""
		time_range: range class
		return: str
		Returns a string that can be used as an iteration index over time_range
		Returns "" if len(time_range) <= 1 (i.e. when no iteration is required)
		The mapping information between iteration indices and time_range is stored in self.iter_index_dict
		(key: iter_index, value: time_range)
		"""
		if len(time_range) <= 1:
			return ""
		iter_index = ITER_INDEX_PREFIX + str(len(self.iter_index_dict))
		self.iter_index_dict[iter_index] = time_range
		return iter_index

	# read sequencer_template.py
	def read_template(self, template_file_name):
		"""
		template_file_name: str
		return: (header, main, footer)
				header: str. header part of template
				main: str. main part of template
				footer: str. footer part of template
		reads a template file for generating a python file.
		the header, main, footer parts of the template is divided by START_MAIN_TEMPLATE, END_MAIN_TEMPLATE
		this method splits the template file into header, main, footer parts and returns them as a tuple
		"""
		# Hmm... why not just use split method..?
		try: f = open(dir_name + "/sequencer_template.py")
		except Exception as e: print(e)
		header = ""
		main = ""
		footer = ""
		line = f.readline()
		while line != START_MAIN_TEMPLATE:
			header += line
			line = f.readline()
		line = f.readline()
		while line != END_MAIN_TEMPLATE:
			main += line
			line = f.readline()
		f.close()
		return (header, main, footer)

	# getting SequencerProgram code
	def get_sequencer_code(self):
		"""
		return: str
		returns the assembly code part of a sequencer program
		"""
		python_code = self.initial_instructions_to_python()
		python_code += "# instructions programmed by GUI\n"

		# main programming procedure
		prev_0ns = False
		for interval in self.interval_list:
			if prev_0ns:
				prev_0ns = False
				continue

			time_range = interval.get_time_length()
			iter_index_string = self.get_iter_index_string(time_range)
			if len(time_range) > 1:
				if 0 in time_range:
					prev_0ns = True
					if interval.next_interval != None:
						next_iter_index_string = self.get_iter_index_string(interval.next_interval.get_time_length())

						instruction_0ns = interval.instruction_labels_to_python()
						instruction_0ns += self.interval_to_python(interval.next_interval, next_iter_index_string, prev_0ns)
						instruction_no_0ns = self.interval_to_python(interval, iter_index_string)
						instruction_no_0ns += self.interval_to_python(interval.next_interval, next_iter_index_string)
						instruction = place_code_in_if_cond(if_cond="{} == 0".format(iter_index_string),
															if_body=instruction_0ns,
															else_body=instruction_no_0ns)
					else:
						instruction_no_0ns = self.interval_to_python(interval, iter_index_string)
						instruction = place_code_in_if_cond(if_cond="{} != 0".format(iter_index_string),
															if_body=instruction_no_0ns)
				else:
					instruction = self.interval_to_python(interval, iter_index_string)
			else:
				instruction = self.interval_to_python(interval, iter_index_string)
			
			if "\\" in instruction:
				python_code += "\n"
			python_code += instruction

		python_code += self.final_instructions_to_python()

		return python_code

	def initial_instructions_to_python(self):
		"""
		return: str
		returns a string of initialization codes
		1. generate a SequencerProgram instance
		2. reset all counters and stopwatches
		3. initialize all register(reg[0]~reg[31]) to 0
		"""
		code = "s = SequencerProgram()\n\n"
		code += "# initialize sequecer\n"
		
		# reset all counters and stopwatches
		trigger_string = ""
		for r in range(len(self.row_headers)):
			if self.row_headers[r].endswith(ROW_HEADER_COUNTER_SUFFIX) \
			or self.row_headers[r].endswith(ROW_HEADER_STOPWATCH_SUFFIX):
				trigger_string += "hd." + self.row_headers[r] + "_reset, "
		if trigger_string != "":
			code += "# reset all counters and stopwatches in HardwareDefinition\n"
			code += "s.trigger_out([{}])\n".format(trigger_string)
			code += "\n"

		# initialize all registers to zero
		code += "# initialize all registers to zero\n"
		code += place_code_in_for_loop("i", "range({})".format(REG_LENGTH), "s.load_immediate(reg[i], 0)\n")
		code += "\n"
		return code

	def interval_to_python(self, interval, iter_index_string="", prev_0ns=False):
		"""
		interval: TimeInterval
		iter_index_string: str (used only when len(interval.time_length) > 1)
		prev_0ns: boolean
		Generate the code string for one interval
		Use interval.to_python() method and append instructions to adjust timing(e.g. nop, wait)
		"""
		instruction, consumed_time = interval.to_python(prev_0ns)
		time_length = interval.get_time_length()
		if len(time_length) == 1:
			n_cycles = int((time_length[0] - consumed_time)/10)

			if n_cycles > INT16_MAX * 4:
				reg_index = self.get_unused_register_index()
				if reg_index != -1:
					label = self.get_instruction_label()
					instruction += "s.load_immediate(reg[{}], 0)\n".format(reg_index)
					n_cycles -= 1
					iteration = n_cycles // INT16_MAX

					instruction += "s.{} = \\\n".format(label)
					instruction += "s.wait_n_clocks({})\n".format(INT16_MAX-3-2)
					instruction += "s.add(reg[{}], reg[{}], 1)\n".format(reg_index, reg_index)
					instruction += 's.branch_if_less_than("{}", reg[{}], {})\n'.format(label, reg_index, iteration)
					n_cycles %= INT16_MAX

			while n_cycles > INT16_MAX:
				instruction += "s.wait_n_clocks({})\n".format(INT16_MAX-3)
				n_cycles -= INT16_MAX

			if n_cycles < 4:
				for i in range(n_cycles):
					instruction += "s.nop()\n"
			else:
				instruction += "s.wait_n_clocks({})\n".format(n_cycles-3)
		else:
			if consumed_time == 0:
				instruction += "n_cycles = int({}/10)\n".format(iter_index_string)
			else:
				instruction += "n_cycles = int(({} - {})/10)\n".format(iter_index_string, consumed_time)
			
			more_than_INT16_MAX_cycles = False
			more_than_4_INT16_MAX_cycles = False
			for time in time_length:
				if (time - consumed_time) > INT16_MAX * 10:
					more_than_INT16_MAX_cycles = True
					
				if (time - consumed_time) > INT16_MAX * 40:
					more_than_4_INT16_MAX_cycles = True
					break

			if more_than_4_INT16_MAX_cycles:
				reg_index = self.get_unused_register_index()
				if reg_index != -1:
					label = self.get_instruction_label()
					if_body = "n_cycles -= 1  # one cycle for load_immediate\n"
					if_body += "iteration = n_cycles // {}\n".format(INT16_MAX)
					if_body += "s.load_immediate(reg[{}], 0)\n".format(reg_index)
					if_body += "s.{} = \\\n".format(label)
					if_body += "s.wait_n_clocks({})\n".format(INT16_MAX-3-2)
					if_body += "s.add(reg[{}], reg[{}], 1)\n".format(reg_index, reg_index)
					if_body += 's.branch_if_less_than("{}", reg[{}], iteration)\n'.format(label, reg_index)
					if_body += "n_cycles %= {}\n".format(INT16_MAX)
					instruction += place_code_in_if_cond(
										"n_cycles > {} * 4".format(INT16_MAX), 
										if_body)
					
			if more_than_INT16_MAX_cycles:
				instruction += place_code_in_while_loop(
									"n_cycles > {}".format(INT16_MAX), 
									"s.wait_n_clocks({})\nn_cycles -= {}\n".format(INT16_MAX-3, INT16_MAX))
			instruction += place_code_in_if_cond(
								"n_cycles < 4",
								place_code_in_for_loop("i", "range(n_cycles)", "s.nop()\n"),
								else_body="s.wait_n_clocks(n_cycles-3)\n")
		return instruction

	def final_instructions_to_python(self):
		"""
		return: str
		Returns a string of codes that needs to be run at the end of every Sequencer Program
		1. turn off all counters
		2. stop sequencer(s.stop())
		"""
		code = "\n# turn off counters and stop sequencer\n"

		# stop all counters
		counter_string = ""
		for r in range(len(self.row_headers)):
			if self.row_headers[r].endswith(ROW_HEADER_COUNTER_SUFFIX):
				counter_string += "(hd.{}_enable, 0), ".format(self.row_headers[r])
		if counter_string != "":
			code += "s.set_output_port(hd.counter_control_port, [{}])\n".format(counter_string)

		# stop sequencer
		code += "s.stop()"

		return code

	# slot methods
	def cell_clicked_slot(self):
		self.currentItem().cell_clicked()

	def cell_changed_slot(self):
		# need to define a signal that only detects text change
		self.currentItem().text_changed()

	# Override Functions
	def setItem(self, row, column, item):
		"""
		row: int
		column: int
		item: TimeTableWidgetItem(QtWidgets.QTableWidgetItem will also work but not recommended)
		overrides QtWidgets.QTableWidget.setItem(row, column, item)
		this method not only sets the item, but also applies cell widget
		"""
		super().setItem(row, column, item)
		if item.cell_widget != None:
			self.setCellWidget(row, column, item.cell_widget)
