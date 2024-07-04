# -*- coding: utf-8 -*-
"""
Base Switch Test script
"""
#%%
import sys
import os, time
import datetime

from SequencerProgram_v1_07 import SequencerProgram, reg
import SequencerUtility_v1_01 as su
from ArtyS7_v1_02 import ArtyS7
import HardwareDefinition_SNU_v4_02 as hd

out_list = []

s=SequencerProgram()

Will_be_replaced_line

s.stop()
#%%

if __name__ == '__main__':
    if 'sequencer' in vars(): # To close the previously opened device when re-running the script with "F5"
        sequencer.close()
    sequencer = ArtyS7('COM9')
    sequencer.check_version(hd.HW_VERSION)
    s.program(show=False, target=sequencer)
    sequencer.auto_mode()

    sequencer.start_sequencer()
    
    while (sequencer.sequencer_running_status() == 'running'):
        time.sleep(0.01)
    
    sequencer.close()