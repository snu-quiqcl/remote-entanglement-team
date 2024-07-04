"""
This module defines TimeInterval class which represents one interval of TimeTableWidget,
or in other words, corresponds to one column of TimeTableWidget
This class also checks whether the current interval status can be translated into sequencer methods(self.check_interval())
and outputs the sequencer method(self.to_python())
"""

from PyQt5 import QtWidgets, QtGui, QtCore
from SequencerProgram_v1_07 import SequencerProgram, reg

from .const import *
from .utility import *

class TimeInterval:
	def __init__(self, time_table):
		self.instruction_labels = []
		self.branch_target = ""
		self.being_targeted = False
		self.item_list = []
		self.time_table = time_table
		self.row_headers = time_table.row_headers
		self.hd = time_table.hd
		self.s = time_table.s
		self.prev_interval = None
		self.next_interval = None

		self.time_length = range(TIME_STEP_NS, TIME_STEP_NS+1)
		self.time_length_unit = UNIT_NS

		self.instruction_flags = [0] * INSTRUCTION_FLAG_LENGTH

		self.error_multiple_instruction = False
		self.error_multiple_read = False
		self.error_instruction_label_not_unique = False
		self.error_missing_branch_target = False
		self.error_10ns_for_branch = False
		self.error_10ns_for_branch_target = False
		self.error_consecutive_0ns = False

		self.error_0ns_multiple_instruction = False

	def append_item(self, item):
		"""
		item: TimeTableWidgetItem
		appends item in self.item_list
		"""
		self.item_list.append(item)

	def check_instruction(self):
		self.instruction_flags, self.num_reads = self.get_instruction_flags()
		self.being_targeted = self.check_being_targeted()

		# error checks
		self.error_multiple_instruction 		= not self.check_only_one_instruction()
		self.error_multiple_read 				= not self.check_read_only_one_register()
		self.error_instruction_label_not_unique	= not self.check_instruction_label_uniqueness()
		self.error_missing_branch_target 		= not self.check_branch_target()
		self.error_10ns_for_branch				= not self.check_branch_time_length()
		self.error_10ns_for_branch_target 		= not self.check_branch_target_time_length()
		self.error_consecutive_0ns 				= not self.check_no_consecutive_0ns()

		# error check if prev_interval has 0ns time_length
		if self.prev_interval != None and (0 in self.prev_interval.get_time_length()):
			instruction_flags_0ns, num_reads_0ns = self.get_instruction_flags(prev_interval=self.prev_interval.prev_interval)
			self.error_0ns_multiple_instruction = not self.check_only_one_instruction(instruction_flags=instruction_flags_0ns)
		else:
			self.error_0ns_multiple_instruction = False

		if self.is_error():
			self.activate_error()
		else:
			self.deactivate_error()

	def activate_error(self):
		"""
		Display error signal(item.show_error_background()) and alert error message on the text_display of GUI
		This method is used as a sub-method of self.check_instruction()
		"""
		for item in self.item_list:
			item.show_error_background()
		
		if self.error_multiple_instruction:
			if self.being_targeted:
				self.time_table.write_text_display(
					"For an instruction being targeted, only instructions in {}(or a combination of these) are allowed.".format([INSTRUCTION_NOP, INSTRUCTION_OUTPUT, INSTRUCTION_COUNTER]))
				self.time_table.write_text_display(
					"Current Instruction: {}".format(self.get_instruction_list_from_instruction_flags()))
			else:
				self.time_table.write_text_display(
					"Multiple Instructions({})".format(self.get_instruction_list_from_instruction_flags()))

		if self.error_multiple_read:
			self.time_table.write_text_display(
				"Can only read one counter at a time. Currently reads {} counters.".format(self.instruction_flags[INSTRUCTION_READ_IDX]))
		
		if self.error_instruction_label_not_unique:
			self.time_table.write_text_display("Each instruction label should be unique.")

		if self.error_missing_branch_target:
			self.time_table.write_text_display("Branch target must be one of instruction labels.")
		
		if self.error_10ns_for_branch:
			self.time_table.write_text_display('"target, iteration" requires at least 20ns to execute.')

		if self.error_10ns_for_branch_target:
			self.time_table.write_text_display("An instruction being targeted by a branch requires at least 20ns to execute.")

		if self.error_consecutive_0ns:
			self.time_table.write_text_display("Two consecutive instuctions both having 0ns time_length is prohibited.")

		if self.error_0ns_multiple_instruction:
			instruction_flags_0ns, num_reads_0ns = self.get_instruction_flags(prev_interval=self.prev_interval.prev_interval)
			self.time_table.write_text_display(
				"Multiple Instructions when prior time_length is 0({})".format(
					self.get_instruction_list_from_instruction_flags(instruction_flags=instruction_flags_0ns)))

	def deactivate_error(self):
		"""
		Display no-error signal(item.undo_error_background())
		This method is used as a sub-method of self.check_instruction()
		"""
		for item in self.item_list:
			item.undo_error_background()

	def get_instruction_flags(self, prev_interval=None):
		"""
		prev_interval: TimeInterval (when None, use self.prev_interval)
		return: instruction_flags: list of 0 & 1
				num_reads: int
		Run through each item of the interval and check current status represents which instruction
		the instruction information is stored in instruction_flags
		and num_reads represents the number of read_counter instruction
		"""
		if prev_interval == None:
			prev_interval = self.prev_interval

		instruction_flags = [0] * INSTRUCTION_FLAG_LENGTH
		num_reads = 0

		for r, item in enumerate(self.item_list):
			if self.row_headers[r] == ROW_HEADER_ADD_DELETE_COLUMN:
				pass

			elif self.row_headers[r] == ROW_HEADER_INSTRUCTION_LABELS:
				pass

			elif self.row_headers[r] == ROW_HEADER_TIME_LENGTH_UNIT:
				pass

			elif self.row_headers[r] == ROW_HEADER_TIME_LENGTH:
				pass

			elif self.row_headers[r].endswith(ROW_HEADER_OUTPUT_SUFFIX):
				if prev_interval == None:
					if item.output_status:
						instruction_flags[INSTRUCTION_OUTPUT_IDX] = 1
				else:
					if prev_interval.item_list[r].output_status != item.output_status:
						instruction_flags[INSTRUCTION_OUTPUT_IDX] = 1

			elif self.row_headers[r].endswith(ROW_HEADER_COUNTER_SUFFIX):
				if prev_interval == None:
					if item.output_status:
						instruction_flags[INSTRUCTION_COUNTER_IDX] = 1
				else:
					if prev_interval.item_list[r].output_status != item.output_status:
						instruction_flags[INSTRUCTION_COUNTER_IDX] = 1

				if item.text() in ["reset"]:
					instruction_flags[INSTRUCTION_TRIGGER_IDX] = 1
				elif QtCore.QRegExp(string_to_regular_expression("read reg[n]")).exactMatch(item.text()):
					instruction_flags[INSTRUCTION_READ_IDX] = 1
					num_reads += 1

			elif self.row_headers[r].endswith(ROW_HEADER_STOPWATCH_SUFFIX):
				if item.text() in ["reset", "start"]:
					instruction_flags[INSTRUCTION_TRIGGER_IDX] = 1
				elif QtCore.QRegExp(string_to_regular_expression("read reg[n]")).exactMatch(item.text()):
					instruction_flags[INSTRUCTION_READ_IDX] = 1
					num_reads += 1

			elif self.row_headers[r] == ROW_HEADER_TLI:
				if QtCore.QRegExp(string_to_regular_expression("read reg[n]")).exactMatch(item.text()):
					instruction_flags[INSTRUCTION_READ_IDX] = 1
					num_reads += 1

			elif self.row_headers[r] == ROW_HEADER_FIFO:
				if QtCore.QRegExp(string_to_regular_expression("reg[n], reg[n], reg[n], event_label")).exactMatch(item.text()):
					instruction_flags[INSTRUCTION_FIFO_IDX] = 1

			elif self.row_headers[r] == ROW_HEADER_BRANCH:
				if QtCore.QRegExp(string_to_regular_expression("target")).exactMatch(item.text()) \
				or QtCore.QRegExp(string_to_regular_expression("target, iteration")).exactMatch(item.text()):
					instruction_flags[INSTRUCTION_BRANCH_IDX] = 1
				elif QtCore.QRegExp(string_to_regular_expression("reset target")).exactMatch(item.text()):
					instruction_flags[INSTRUCTION_LOAD_IMMEDIATE_IDX] = 1					

			else:
				# This is in fact an error
				pass

		return (instruction_flags, num_reads)

	def get_instruction_list_from_instruction_flags(self, instruction_flags=None):
		"""
		instruction flags: list of 0 & 1 (when None, use self.instruction_flags)
		return: list of str
		Converts instruction_flags and return a list whose elements are instructions of which corresponding instruction_flag is 1
		"""
		if instruction_flags == None:
			instruction_flags = self.instruction_flags

		instruction_list = []
		if instruction_flags[INSTRUCTION_NOP_IDX] > 0:
			instruction_list.append(INSTRUCTION_NOP)
		if instruction_flags[INSTRUCTION_OUTPUT_IDX] > 0:
			instruction_list.append(INSTRUCTION_OUTPUT)
		if instruction_flags[INSTRUCTION_COUNTER_IDX] > 0:
			instruction_list.append(INSTRUCTION_COUNTER)
		if instruction_flags[INSTRUCTION_TRIGGER_IDX] > 0:
			instruction_list.append(INSTRUCTION_TRIGGER)
		if instruction_flags[INSTRUCTION_READ_IDX] > 0:
			instruction_list.append(INSTRUCTION_READ)
		if instruction_flags[INSTRUCTION_FIFO_IDX] > 0:
			instruction_list.append(INSTRUCTION_FIFO)
		if instruction_flags[INSTRUCTION_BRANCH_IDX] > 0:
			instruction_list.append(INSTRUCTION_BRANCH)
		if instruction_flags[INSTRUCTION_LOAD_IMMEDIATE_IDX] > 0:
			instruction_list.append(INSTRUCTION_LOAD_IMMEDIATE)
		if instruction_flags[INSTRUCTION_OTHERS_IDX] > 0:
			instruction_list.append(INSTRUCTION_OTHERS)
		return instruction_list

	# error checking methods
	# True if no error, False if error
	def check_only_one_instruction(self, instruction_flags=None):
		"""
		instruction flags: list of 0 & 1 (when None, use self.instruction_flags)
		return: boolean
		returns True if this interval represents only one instruction, False if it represents multiple instructions
		exception: when this interval is being targeted by a branch/jump instruction,
				   returns True if the instruction is one or combination of nop, set_output, set_counter
				   returns False otherwise
		"""
		if instruction_flags == None:
			instruction_flags = self.instruction_flags

		if not self.being_targeted:
			return (sum(instruction_flags) <= 1)

		# if the interval is being targeted, only nop, set_output, set_counter (or combination of these) are allowed
		for i in range(len(instruction_flags)):
			if i in [INSTRUCTION_NOP_IDX, INSTRUCTION_OUTPUT_IDX, INSTRUCTION_COUNTER_IDX]:
				continue
			if instruction_flags[i] > 0:
				return False
		return True

	def check_read_only_one_register(self):
		"""
		return: boolean
		returns True if this interval reads only one or less counter, False if it reads more than one counter
		"""
		return (self.num_reads <= 1)

	def check_instruction_label_uniqueness(self):
		"""
		return: boolean
		returns True if instruction_labels of this interval are unique in time_table, False otherwise
		Note that instruction_labels of one interval should also be all distinct
		"""
		if self.instruction_labels == []:
			return True

		for label in self.instruction_labels:
			count = 0
			for interval in self.time_table.interval_list:
				for interval_label in interval.instruction_labels:
					if label == interval_label:
						count += 1
			if count > 1:
				return False
		return True

	def check_branch_target(self):
		"""
		return: boolean
		returns True if branch/jump target of this interval is one of the instruction labels, False otherwise
		"""
		if self.branch_target == "":
			return True

		for interval in self.time_table.interval_list:
			for label in interval.instruction_labels:
				if self.branch_target == label:
					return True
		return False

	def check_branch_time_length(self):
		"""
		return: boolean
		returns False if this interval is a branch instruction with a finite iteration and its time_length is less than 20ns, True otherwise
		Note: a branch instruction with a finite iteration requires at least 20ns to execute 
			  because it is converted to one add and one branch_if_less_than instruction
		"""
		for r, item in enumerate(self.item_list):
			if self.row_headers[r] == ROW_HEADER_BRANCH:
				if item.get_iteration_from_text() == -1:
					return True

		for time_length in self.get_time_length():
			if time_length < 20:
				return False
		return True

	def check_branch_target_time_length(self):
		"""
		return: boolean
		returns False if this interval is being targeted by another branch/jump and its time_length is less than 20ns, True otherwise
		Note: an interval being targeted by a branch/jump requires at least 20ns to execute 
			  because it is converted to set_counter and set_output instructions to fit the output status
		"""
		if not self.being_targeted:
			return True
		
		for time_length in self.get_time_length():
			if time_length < 20:
				return False
		return True

	def check_no_consecutive_0ns(self):
		"""
		return: boolean
		returns False if both self.prev_interval and this interval have 0ns in time_length
		two consecutive 0ns time_length is prohibited
		"""
		if self.prev_interval == None:
			return True
		if 0 not in self.get_time_length():
			return True
		return (0 not in self.prev_interval.get_time_length())
		
	def check_being_targeted(self):
		"""
		return: boolean
		returns True if this interval is a target of any branch/jump instructions in time_table
		"""
		# get the row_number of branch item
		for r in range(len(self.item_list)):
			if self.row_headers[r] == ROW_HEADER_BRANCH:
				break

		# run through all intervals in time_table and match targets to instruction labels of this interval
		for interval in self.time_table.interval_list:
			target = interval.item_list[r].get_target_from_text()
			for label in self.instruction_labels:
				if label == target:
					return True
		return False

	def is_error(self):
		"""
		return: boolean
		returns True if this interval has any errors
		"""
		return self.error_multiple_instruction 			\
			or self.error_multiple_read 				\
			or self.error_instruction_label_not_unique	\
			or self.error_missing_branch_target 		\
			or self.error_10ns_for_branch 				\
			or self.error_10ns_for_branch_target		\
			or self.error_consecutive_0ns				\
			or self.error_0ns_multiple_instruction

	# set functions
	def set_instruction_labels(self, instruction_labels):
		"""
		instruction_labels: list of str
		set self.instruction_labels to instruction_labels
		all instructions must be checked when instruction_labels change
		because instruction_labels are used as targets of (distant) branches/jumps
		"""
		self.instruction_labels = instruction_labels
		self.time_table.check_all_instructions()

	def set_time_length(self, time_length):
		"""
		time_length: range
		set self.time_length to time_length
		need to check_instruction for self.next_interval to detect error_consecutive_0ns
		"""
		self.time_length = time_length
		self.check_instruction()
		if self.next_interval != None:
			self.next_interval.check_instruction()

	def set_time_length_unit(self, time_length_unit):
		"""
		time_length_unit: str
		set self.time_length_unit to time_length_unit
		"""
		self.time_length_unit = time_length_unit

		for r, item in enumerate(self.item_list):
			if self.row_headers[r] == ROW_HEADER_TIME_LENGTH:
				if self.time_length_unit == UNIT_NS:
					item.set_nano_sec_mode()
				elif self.time_length_unit == UNIT_US:
					item.set_micro_sec_mode()
				elif self.time_length_unit == UNIT_MS:
					item.set_milli_sec_mode()
				elif self.time_length_unit == UNIT_S:
					item.set_sec_mode()
				else:
					# This is in fact an error
					pass
				break
		self.check_instruction()

	def set_branch_target(self, branch_target):
		"""
		branch_target: str
		set self.branch_target to branch_target
		all instructions must be checked when branch_target change
		because the targetted instruction must detect error_10ns_for_branch_target
		"""
		self.branch_target = branch_target
		self.time_table.check_all_instructions()

	def set_prev_interval(self, prev_interval):
		"""
		prev_interval: TimeInterval
		set self.prev_interval to prev_interval
		check_instruction is required because set_output, set_counter, error_consecutive_0ns are relevant to prev_interval
		"""
		self.prev_interval = prev_interval
		self.check_instruction()

	def set_next_interval(self, next_interval):
		"""
		next_interval: TimeInterval
		set self.next_interval to next_interval
		"""
		self.next_interval = next_interval

	def set_sequencer(self, sequencer):
		"""
		sequencer: SequencerProgram
		set self.s to sequencer
		"""
		self.s = sequencer

	# get functions
	def get_time_length(self):
		"""
		return: range
		get function of time_length
		returned time_length is in ns unit (unit_conversion value is multiplied)
		"""
		start = self.time_length.start * unit_conversion_dict[self.time_length_unit]
		stop = self.time_length.stop * unit_conversion_dict[self.time_length_unit]
		step = self.time_length.step * unit_conversion_dict[self.time_length_unit]

		return range(start, stop, step)

	def get_column_number(self):
		"""
		return: int
		get function of column_number
		returns column number of this interval in time_table
		"""
		for c, interval in enumerate(self.time_table.interval_list):
			if interval == self:
				return c
		
		# error
		print("Error: column_number not found")
		return -1

	def to_python(self, prev_0ns=False):
		self.check_instruction()
		if self.is_error():
			return

		instruction = self.instruction_labels_to_python()
		consumed_time = 0

		if prev_0ns and self.prev_interval != None:
			prev_interval = self.prev_interval.prev_interval
			instruction_flags, num_reads = self.get_instruction_flags(prev_interval)
		else:
			prev_interval = self.prev_interval
			instruction_flags = self.instruction_flags

		if self.being_targeted:
			counter_string = ""
			output_string = ""
			for r, item in enumerate(self.item_list):
				if self.row_headers[r].endswith(ROW_HEADER_OUTPUT_SUFFIX):
					output_string += "(hd.{}, {}), ".format(self.row_headers[r], item.output_status)
				elif self.row_headers[r].endswith(ROW_HEADER_COUNTER_SUFFIX):
					counter_string += "(hd.{}_enable, {}), ".format(self.row_headers[r], item.output_status)

			instruction += "s.set_output_port(hd.counter_control_port, [{}])\n".format(counter_string)
			instruction += "s.set_output_port(hd.external_control_port, [{}])\n".format(output_string)
			consumed_time += 10

		elif sum(instruction_flags) == 0:
			# current instruction: nop
			if instruction != "":
				instruction += "s.nop()\n"
			else:
				consumed_time -= 10
		elif instruction_flags[INSTRUCTION_OUTPUT_IDX] > 0:
			# current_instruction: set_output
			output_string = ""
			for r, item in enumerate(self.item_list):
				if self.row_headers[r].endswith(ROW_HEADER_OUTPUT_SUFFIX):
					if prev_interval == None:
						if item.output_status:
							output_string += "(hd.{}, {}), ".format(self.row_headers[r], item.output_status)
					else:
						if prev_interval.item_list[r].output_status != item.output_status:
							output_string += "(hd.{}, {}), ".format(self.row_headers[r], item.output_status)
			
			instruction += "s.set_output_port(hd.external_control_port, [{}])\n".format(output_string)
		elif instruction_flags[INSTRUCTION_COUNTER_IDX] > 0:
			# current_instruction: set_counter
			counter_string = ""
			for r, item in enumerate(self.item_list):
				if self.row_headers[r].endswith(ROW_HEADER_COUNTER_SUFFIX):
					if prev_interval == None:
						if item.output_status:
							counter_string += "(hd.{}_enable, {}), ".format(self.row_headers[r], item.output_status)
					else:
						if prev_interval.item_list[r].output_status != item.output_status:
							counter_string += "(hd.{}_enable, {}), ".format(self.row_headers[r], item.output_status)
			
			instruction += "s.set_output_port(hd.counter_control_port, [{}])\n".format(counter_string)
		elif instruction_flags[INSTRUCTION_TRIGGER_IDX] > 0:
			# current_instruction: trigger_out
			trigger_string = ""
			for r, item in enumerate(self.item_list):
				if self.row_headers[r].endswith(ROW_HEADER_COUNTER_SUFFIX):
					if item.text() in ["reset"]:
						trigger_string += "hd.{}_{}, ".format(self.row_headers[r], item.text())
				elif self.row_headers[r].endswith(ROW_HEADER_STOPWATCH_SUFFIX):
					if item.text() in ["reset", "start"]:
						trigger_string += "hd.{}_{}, ".format(self.row_headers[r], item.text())

			instruction += "s.trigger_out([{}])\n".format(trigger_string)
		elif instruction_flags[INSTRUCTION_READ_IDX] > 0:
			# current_instruction: read
			for r, item in enumerate(self.item_list):
				if self.row_headers[r].endswith(ROW_HEADER_COUNTER_SUFFIX):
					if QtCore.QRegExp(string_to_regular_expression("read reg[n]")).exactMatch(item.text()):
						reg_index = item.get_reg_index_from_text()
						read_val = "hd.{}_result".format(self.row_headers[r])
						break
				elif self.row_headers[r].endswith(ROW_HEADER_STOPWATCH_SUFFIX):
					if QtCore.QRegExp(string_to_regular_expression("read reg[n]")).exactMatch(item.text()):
						reg_index = item.get_reg_index_from_text()
						read_val = "hd.{}_result".format(self.row_headers[r])
						break
				elif self.row_headers[r] == ROW_HEADER_TLI:
					if QtCore.QRegExp(string_to_regular_expression("read reg[n]")).exactMatch(item.text()):
						reg_index = item.get_reg_index_from_text()
						read_val = "hd.Trigger_level"
						break
			
			instruction += "s.read_counter(reg[{}], {})\n".format(reg_index, read_val)
		elif instruction_flags[INSTRUCTION_FIFO_IDX] > 0:
			# current_instruction: write_to_fifo
			for r, item in enumerate(self.item_list):
				if self.row_headers[r] == ROW_HEADER_FIFO:
					if QtCore.QRegExp(string_to_regular_expression("reg[n], reg[n], reg[n], event_label")).exactMatch(item.text()):
						reg_indices = item.get_reg_indices_from_text()
					break

			instruction += "s.write_to_fifo(reg[{}], reg[{}], reg[{}], {})\n".format(reg_indices[0], 
																					 reg_indices[1], 
																					 reg_indices[2], 
																					 reg_indices[3])
		elif instruction_flags[INSTRUCTION_BRANCH_IDX] > 0:
			# current_instruction: branch/jump
			for r, item in enumerate(self.item_list):
				if self.row_headers[r] == ROW_HEADER_BRANCH:
					if QtCore.QRegExp(string_to_regular_expression("target")).exactMatch(item.text()) \
					or QtCore.QRegExp(string_to_regular_expression("target, iteration")).exactMatch(item.text()):
						target = item.get_target_from_text()
						iteration = item.get_iteration_from_text()
					break
			if iteration == -1:
				instruction += 's.jump("{}")\n'.format(target)
			else:
				reg_index = self.get_register_index(target)
				instruction += "s.add(reg[{}], reg[{}], 1)\n".format(reg_index, reg_index)
				instruction += 's.branch_if_less_than("{}", reg[{}], {})\n'.format(target, reg_index, iteration)
				consumed_time += 10
		elif instruction_flags[INSTRUCTION_LOAD_IMMEDIATE_IDX] > 0:
			# current_instruction: load_immediate
			for r, item in enumerate(self.item_list):
				if self.row_headers[r] == ROW_HEADER_BRANCH:
					if QtCore.QRegExp(string_to_regular_expression("reset target")).exactMatch(item.text()):
						target = item.get_target_from_text()
						reg_index = self.get_register_index(target)
					break
			instruction += "s.load_immediate(reg[{}], 0)\n".format(reg_index)

		elif instruction_flags[INSTRUCTION_OTHERS_IDX] > 0:
			pass

		consumed_time += 10

		return (instruction, consumed_time)

	def instruction_labels_to_python(self):
		"""
		return: str
		converts self.instruction_labels into python code
		"""
		instruction = ""
		for label in self.instruction_labels:
			instruction += "s.{} = \\\n".format(label)
		return instruction

	def get_register_index(self, target):
		"""
		target: str
		return: int
		returns register index assigned to the target
		"""
		return self.time_table.reg_assign_dict[target]
