"""
constants used for SequencerGUI
"""
#-------------general constants---------
INT16_MAX = (1 << 16) - 1
REG_LENGTH = 32
UI_FILE_NAME = "\\SequencerGUIcomponents\\SequencerGUI.ui"
TEMPLATE_FILE_NAME = "SequencerGUIcomponents/sequencer_template.py"
ITER_INDEX_PREFIX = "time_length_"
DATA_DICT_PREFIX = "data_dict_"
INSTRUCTION_LABEL_PREFIX = "repeat_wait_"

START_MAIN_TEMPLATE = "START_MAIN_TEMPLATE\n"
END_MAIN_TEMPLATE = "END_MAIN_TEMPLATE\n"

#-------------table_time_table related constants--------
TABLE_VERTICAL_HEADER_W = 200
TABLE_CELL_W = 105
TABLE_CELL_H = 40

#-------------row_headers related constants---------
ROW_HEADER_ADD_DELETE_COLUMN = "add/delete column"
ROW_HEADER_INSTRUCTION_LABELS = "instruction_label"
ROW_HEADER_TIME_LENGTH_UNIT = "time_length_unit"
ROW_HEADER_TIME_LENGTH = "time_length"

ROW_HEADER_OUTPUT_SUFFIX = "_out"
ROW_HEADER_COUNTER_SUFFIX = "_counter"
ROW_HEADER_STOPWATCH_SUFFIX = "_stopwatch"

ROW_HEADER_TLI = "Trigger-level-in"
ROW_HEADER_FIFO = "write_to_fifo"
ROW_HEADER_BRANCH = "branch/jump"

#-------------instruction related constants---------
INSTRUCTION_NOP = "nop"
INSTRUCTION_OUTPUT = "set_output"
INSTRUCTION_COUNTER = "set_counter"
INSTRUCTION_TRIGGER = "trigger_out"
INSTRUCTION_READ = "read"
INSTRUCTION_FIFO = "write_to_fifo"
INSTRUCTION_BRANCH = "branch/jump"
INSTRUCTION_LOAD_IMMEDIATE = "load_immediate"
INSTRUCTION_OTHERS = "others"

INSTRUCTION_NOP_IDX = 0
INSTRUCTION_OUTPUT_IDX = 1
INSTRUCTION_COUNTER_IDX = 2
INSTRUCTION_TRIGGER_IDX = 3
INSTRUCTION_READ_IDX = 4
INSTRUCTION_FIFO_IDX = 5
INSTRUCTION_BRANCH_IDX = 6
INSTRUCTION_LOAD_IMMEDIATE_IDX = 7
INSTRUCTION_OTHERS_IDX = 8

INSTRUCTION_FLAG_LENGTH = 9

#-------------time_length_unit related constants---------
TIME_STEP_NS = 10
TIME_STEP_US = 1
TIME_STEP_MS = 1
TIME_STEP_S  = 1

TIME_MAX_NS = INT16_MAX * INT16_MAX * 10
TIME_MAX_US = int(TIME_MAX_NS / 1e3)
TIME_MAX_MS = int(TIME_MAX_NS / 1e6)
TIME_MAX_S = int(TIME_MAX_NS / 1e9)

UNIT_NS = "ns"
UNIT_US = "us"
UNIT_MS = "ms"
UNIT_S  = "s"

unit_conversion_dict = {UNIT_NS: 1,
						UNIT_US: int(1e3),
						UNIT_MS: int(1e6),
						UNIT_S: int(1e9)
						}



#-------------regular expression related constants---------
# regular expression for 1 ~ INT16_MAX (does not contain 0)
REG_EXP_INT16 = "([1-9][0-9]{0,3}|[1-5][0-9]{4}|6[0-4][0-9]{3}|65[0-4][0-9]{2}|655[0-2][0-9]|6553[0-5])"

reg_exp_dict = {"(": "\\(",
				")": "\\)",
				"reg[n]": "reg\\[([12]?[0-9]|3[01])\\]",
				"time_length\\(ns\\)": "[1-9][0-9]*0",  # \\(, \\) used instead of (, ) due to replacement order
				"time_length\\(us\\)": "[1-9][0-9]*",   # \\(, \\) used instead of (, ) due to replacement order
				"time_length\\(ms\\)": "[1-9][0-9]*",   # \\(, \\) used instead of (, ) due to replacement order
				"time_length\\(s\\)": "[1-9][0-9]*",    # \\(, \\) used instead of (, ) due to replacement order
				"start:step:stop\\(ns\\)": "(0|[1-9][0-9]*0):(-)?[1-9][0-9]*0:(0|[1-9][0-9]*0)",  # \\(, \\) used instead of (, ) due to replacement order
				"start:step:stop\\(us\\)": "(0|[1-9][0-9]*):(-)?[1-9][0-9]*:(0|[1-9][0-9]*)",     # \\(, \\) used instead of (, ) due to replacement order
				"start:step:stop\\(ms\\)": "(0|[1-9][0-9]*):(-)?[1-9][0-9]*:(0|[1-9][0-9]*)",     # \\(, \\) used instead of (, ) due to replacement order
				"start:step:stop\\(s\\)": "(0|[1-9][0-9]*):(-)?[1-9][0-9]*:(0|[1-9][0-9]*)",      # \\(, \\) used instead of (, ) due to replacement order
				"event_label": "(0|{})".format(REG_EXP_INT16),
				"target": "[a-zA-Z]([a-zA-Z0-9_]*)",
				"iteration": REG_EXP_INT16
			   }
