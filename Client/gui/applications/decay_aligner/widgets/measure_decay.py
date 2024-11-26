"""
Created on Nov 26, 2024
@author: Seungwoo Yu

"""
from SequencerProgram_v1_07 import SequencerProgram, reg
import SequencerUtility_v1_01 as su
from ArtyS7_v1_02 import ArtyS7
import HardwareDefinition_SNU_v4_02 as hd

MAX_TIME_DIFFERENCE = 123
WAITING_TIME_FOR_STOPWATCH = int(200/8)#minimum is 4
WAITING_TIME_FOR_AOM_OFF = 2
COOLING_TIME = 4
TIME_1US = 100
THRESHOLD=117
RUN_NUMBER = 50000
SUCCESS_NUMBER = 50000


run_counter_R                    = reg[0]
success_counter_R                = reg[1]
AOM_counter_R                    = reg[2]
sw_flags_R                       = reg[3]
pulse_trigger_timing_R           = reg[4]
PMT_timing_R                     = reg[5]
time_diff_R                      = reg[6]

memory_pointer_R                 = reg[10]
communication_first_R            = reg[11]
communication_second_R           = reg[12]
communication_third_R            = reg[13]
time_delta_R                     = reg[15]


#sequencer code
s = SequencerProgram()
s.load_immediate(communication_first_R, 0) # Reset value for the momery initialization
s.load_immediate(memory_pointer_R, 0)


#memory init, 0~max_time_diff_to_record init
s.memory_initialization = \
\
s.store_word_to_memory(memory_pointer_R, communication_first_R)
s.add(memory_pointer_R, memory_pointer_R, 1)
s.branch_if_less_than('memory_initialization', memory_pointer_R, MAX_TIME_DIFFERENCE)

#Reset run_number
s.load_immediate(run_counter_R, 0, 'reg[0] will be used for run number')
s.load_immediate(success_counter_R, SUCCESS_NUMBER, 'success_counter_R will be used for success number')

s.outer_repeat = \
\
s.load_immediate(reg[1], 0) # reg[1] is for the cooling time

s.repeat = \
\
s.load_immediate(reg[1], 0) # reg[1] is for the cooling time

s.cooling = \
\
s.wait_n_clocks(TIME_1US-3-2)
s.add(AOM_counter_R, AOM_counter_R, 1)
s.branch_if_less_than('cooling', AOM_counter_R, COOLING_TIME)

# Tunr off AOM
s.set_output_port(hd.external_control_port, [(hd.AOM1_out, 0)])
s.wait_n_clocks(WAITING_TIME_FOR_AOM_OFF-3, 'Wait for totally turning off the AOM')

# Trigger
s.set_output_port(hd.external_control_port, [(hd.TRIG_out, 1)])
s.set_output_port(hd.external_control_port, [(hd.TRIG_out, 0)])

# Run stopwatch
s.trigger_out([hd.PMT_stopwatch_reset , hd.SYNC_stopwatch_reset, ], 'Reset stopwatches')
s.nop() # Between reset and start of the stopwatches, add at least one clock
s.trigger_out([hd.PMT_stopwatch_start, hd.SYNC_stopwatch_start, ], 'Start stopwatches')
s.wait_n_clocks(WAITING_TIME_FOR_STOPWATCH-3, 'Wait for totally turning off the AOM')

# Turn on AOM
s.set_output_port(hd.external_control_port, [(hd.AOM1_out, 1)])

# Collect the result of stopwatch measurements
s.read_counter(sw_flags_R,              hd.Trigger_level, 'Read status of stopwatches')
s.read_counter(pulse_trigger_timing_R,  hd.SYNC_stopwatch_result, 'Read pulse trigger stopwatch result')
s.read_counter(PMT_timing_R,           hd.PMT_stopwatch_result, 'Read PMT1 stopwatch result')

# Check if PMT A has arrived
s.check_PMT_triggered = \
\
s.branch_if_equal_with_mask('decide_repeat', sw_flags_R, \
    0 , 1 << hd.PMT_stopwatch_stopped_TLI)

# Calculate time difference and decide whether it lies between the desired range
s.subtract(time_diff_R, PMT_timing_R, pulse_trigger_timing_R)
s.branch_if_less_than('store_time_difference', time_diff_R, MAX_TIME_DIFFERENCE)
s.jump('decide_repeat')

#if count is success, add 1 in address number time_diff_R
s.store_time_difference = \
\
s.subtract(success_counter_R, success_counter_R, 1, 'success_counter--')
s.load_word_from_memory(memory_pointer_R, time_diff_R)
s.add(memory_pointer_R, memory_pointer_R, 1)
s.store_word_to_memory(time_diff_R, memory_pointer_R)

# Decide whether we will repeat running
s.decide_repeat = \
\
s.branch_if_less_than('transfer_statistics', success_counter_R, 1)
s.add(run_counter_R, run_counter_R, 1, 'run_counter_R++')
s.branch_if_less_than('repeat', run_counter_R, RUN_NUMBER)

s.transfer_statistics = \
\
s.load_immediate(memory_pointer_R, 0, 'memory pointer is used as address pointer and counter')
s.transfer_repeat = \
\
s.load_word_from_memory(communication_first_R, memory_pointer_R)
s.add(memory_pointer_R, memory_pointer_R, 1)
s.load_word_from_memory(communication_second_R, memory_pointer_R)
s.add(memory_pointer_R, memory_pointer_R, 1)
s.load_word_from_memory(communication_third_R, memory_pointer_R)
s.add(memory_pointer_R, memory_pointer_R, 1)
s.write_to_fifo(communication_first_R, communication_second_R, communication_third_R, 100)
s.branch_if_less_than('transfer_repeat', memory_pointer_R, MAX_TIME_DIFFERENCE)

s.stop()