# Import required modules for sequencer programming
import sys, os
import importlib
import yaml

from SequencerProgram_v1_07 import SequencerProgram, reg
import SequencerUtility_v1_01 as su
from ArtyS7_v1_02 import ArtyS7


# import HardwareDefinition_type
dir_name = os.path.dirname("//172.22.22.101/qc_user/Users/HunHuh/SequencerGUI/HardwareDefinition_type_EX.py")
hd_module = os.path.basename("//172.22.22.101/qc_user/Users/HunHuh/SequencerGUI/HardwareDefinition_type_EX.py")[:-3]

if dir_name not in sys.path:
    sys.path.append(dir_name)
hd = importlib.import_module(hd_module)


data_list = []

s = SequencerProgram()

# initialize sequecer
# reset all counters and stopwatches in HardwareDefinition
s.trigger_out([hd.push_button1_counter_reset, hd.push_button2_counter_reset, hd.push_button1_stopwatch_reset, hd.push_button2_stopwatch_reset, ])

# initialize all registers to zero
for i in range(32):
	s.load_immediate(reg[i], 0)

# instructions programmed by GUI
s.set_output_port(hd.external_control_port, [(hd.LED1_out, 1), ])
s.wait_n_clocks(996)
s.set_output_port(hd.counter_control_port, [(hd.push_button1_counter_enable, 1), ])
s.set_output_port(hd.external_control_port, [(hd.LED2_out, 1), ])
s.set_output_port(hd.external_control_port, [(hd.LED1_out, 0), ])
s.set_output_port(hd.external_control_port, [(hd.LED1_out, 1), (hd.LED2_out, 0), ])
s.set_output_port(hd.external_control_port, [(hd.LED1_out, 0), ])

# turn off counters and stop sequencer
s.set_output_port(hd.counter_control_port, [(hd.push_button1_counter_enable, 0), (hd.push_button2_counter_enable, 0), ])
s.stop()

# Send Instructions and Start Sequencer
if 'sequencer' in vars():
	sequencer.close()
sequencer = ArtyS7('')
sequencer.check_version(hd.HW_VERSION)

s.program(show=False, target=sequencer)

sequencer.auto_mode()
sequencer.start_sequencer()

# Data Acquisition
data = []

while sequencer.sequencer_running_status() == 'running':
	data_count = sequencer.fifo_data_length()
	data += sequencer.read_fifo_data(data_count)

data_count = sequencer.fifo_data_length()
while data_count > 0:
	data += sequencer.read_fifo_data(data_count)
	data_count = sequencer.fifo_data_length()

data_list.append(data)
print(data)

# rabi-type data processing
data_dict_0 = dict()
for packet in data:
	if packet[2] not in data_dict_0.keys():
		data_dict_0[packet[2]] = 1
	else:
		data_dict_0[packet[2]] += 1


with open("SequencerData/sequencerGUI_data_200905_183257.yaml", 'w') as f:
	yaml.dump(data_dict_0, f)

empty_data = True
for data in data_list:
    for packet in data:
        empty_data = False
        print(packet)
    print()
if empty_data:
    print("empty data_list")
