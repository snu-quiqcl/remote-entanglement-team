# Import required modules for sequencer programming
import sys, os
import importlib
import yaml

from SequencerProgram_v1_07 import SequencerProgram, reg
import SequencerUtility_v1_01 as su
from ArtyS7_v1_02 import ArtyS7


# import HardwareDefinition_type
dir_name = os.path.dirname("//172.22.22.101/qc_user/Experiment_Scripts/Chamber_3G_SNU/PMT_align/HardwareDefinition_SNU_v4_01.py")
hd_module = os.path.basename("//172.22.22.101/qc_user/Experiment_Scripts/Chamber_3G_SNU/PMT_align/HardwareDefinition_SNU_v4_01.py")[:-3]

if dir_name not in sys.path:
    sys.path.append(dir_name)
hd = importlib.import_module(hd_module)


data_list = []

data_dict_0 = dict()

for time_length_0 in range(0, 2500000, 50000):
	data_dict_1 = dict()
	
	s = SequencerProgram()
	
	# initialize sequecer
	# reset all counters and stopwatches in HardwareDefinition
	s.trigger_out([hd.shutter_control_counter_reset, hd.PMT1_counter_reset, hd.shutter_control_stopwatch_reset, hd.PMT1_stopwatch_reset, hd.pulse_trigger_stopwatch_reset, ])
	
	# initialize all registers to zero
	for i in range(32):
		s.load_immediate(reg[i], 0)
	
	# instructions programmed by GUI
	
	s.repeat = \
	s.set_output_port(hd.counter_control_port, [(hd.shutter_control_counter_enable, 0), (hd.PMT1_counter_enable, 0), ])
	s.set_output_port(hd.external_control_port, [(hd.Microwave_12_6GHz_out, 0), (hd.EOM_14_7GHz_out, 1), (hd.EOM_2_1GHz_out, 0), (hd.AOM_200_205MHz_out, 0), (hd.AOM_on_off_out, 0), (hd.external_trigger_out, 0), ])
	s.wait_n_clocks(65532)
	s.wait_n_clocks(34460)
	s.trigger_out([hd.PMT1_counter_reset, ])
	
	s.init = \
	s.set_output_port(hd.external_control_port, [(hd.EOM_14_7GHz_out, 0), ])
	s.wait_n_clocks(49996)
	s.set_output_port(hd.external_control_port, [(hd.EOM_2_1GHz_out, 1), (hd.AOM_on_off_out, 1), ])
	s.wait_n_clocks(6)
	if time_length_0 == 0:
		s.set_output_port(hd.external_control_port, [(hd.EOM_2_1GHz_out, 0), ])
		s.wait_n_clocks(996)
	else:
		s.set_output_port(hd.external_control_port, [(hd.Microwave_12_6GHz_out, 1), ])
		n_cycles = int((time_length_0 - 10)/10)
		while n_cycles > 65535:
			s.wait_n_clocks(65532)
			n_cycles -= 65535
		if n_cycles < 4:
			for i in range(n_cycles):
				s.nop()
		else:
			s.wait_n_clocks(n_cycles-3)
		s.set_output_port(hd.external_control_port, [(hd.Microwave_12_6GHz_out, 0), (hd.EOM_2_1GHz_out, 0), ])
		s.wait_n_clocks(996)
	s.set_output_port(hd.counter_control_port, [(hd.PMT1_counter_enable, 1), ])
	s.set_output_port(hd.external_control_port, [(hd.EOM_2_1GHz_out, 1), (hd.AOM_200_205MHz_out, 1), (hd.AOM_on_off_out, 0), ])
	s.wait_n_clocks(49996)
	s.read_counter(reg[8], hd.PMT1_counter_result)
	s.set_output_port(hd.external_control_port, [(hd.EOM_2_1GHz_out, 0), (hd.AOM_200_205MHz_out, 0), ])
	s.set_output_port(hd.counter_control_port, [(hd.PMT1_counter_enable, 0), ])
	s.write_to_fifo(reg[8], reg[8], reg[8], 5)
	s.set_output_port(hd.external_control_port, [(hd.EOM_14_7GHz_out, 1), ])
	s.add(reg[31], reg[31], 1)
	s.branch_if_less_than("repeat", reg[31], 100)
	
	# turn off counters and stop sequencer
	s.set_output_port(hd.counter_control_port, [(hd.shutter_control_counter_enable, 0), (hd.PMT1_counter_enable, 0), ])
	s.stop()
	
	# Send Instructions and Start Sequencer
	if 'sequencer' in vars():
		sequencer.close()
	sequencer = ArtyS7('COM7')
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
	
	data_dict_1 = dict()
	for packet in data:
		if packet[2] not in data_dict_1.keys():
			data_dict_1[packet[2]] = 1
		else:
			data_dict_1[packet[2]] += 1
	
	time_length_key = str(time_length_0/1000) + 'us'
	data_dict_0[time_length_key] = data_dict_1


with open("SequencerData/sequencerGUI_data_200831_173744.yaml", 'w') as f:
	yaml.dump(data_dict_0, f)

empty_data = True
for data in data_list:
    for packet in data:
        empty_data = False
        print(packet)
    print()
if empty_data:
    print("empty data_list")
