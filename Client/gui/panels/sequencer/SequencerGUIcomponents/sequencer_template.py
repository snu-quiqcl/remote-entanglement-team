# Import required modules for sequencer programming
import sys, os
import importlib

from SequencerProgram_v1_07 import SequencerProgram, reg
import SequencerUtility_v1_01 as su
from ArtyS7_v1_02 import ArtyS7
import HardwareDefinition_custom as hd


START_MAIN_TEMPLATE
{sequencer_code}
# This line will be filled automatically 
# From the Sequencer GUI
END_MAIN_TEMPLATE
# End main template
