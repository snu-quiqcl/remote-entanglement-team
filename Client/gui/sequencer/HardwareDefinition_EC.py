# -*- coding: utf-8 -*-
"""
Created on Wed Feb  7 07:59:12 2018

@author: 1109282

According to the given mapping, we will add alias for each pin
"""

from HardwareDefinition_v4_03 import *

# Input port pin mapping
# For input pin, there will be only one driver
input_mapping = {'jb_2': 'PMT', 'jb_0': 'PMT2', 'jb_6': 'PMT3', 'jb_4':'PMT4', 'ja_2': 'PULSE_PICK'}

# Output port pin mapping
# For output pin, there might be more than one device controlled by the output pin
output_mapping = {'EOM_7G_1': 'ja_0',
                  'EOM_7G_2': 'ja_1',
                  'AOM': 'ja_3',
                  'PCKR': 'ja_4',
                  'AOM3': 'ja_5',
                  'MW': 'ja_6',
                  'TRG': 'ja_7',
                  'AOM2': 'jb_3',
                  'EOM_2G': 'jb_7'}
description = {'EOM_2G': 'Initialization beam', 'EOM_7G_1': 'Cooling sideband', 'EOM_7G_2': 'Cooling sideband', 'AOM': 'Turning beam on/off', 'MW': 'Turing MW on/off', 'AOM2': 'Cooling beam for 170', 'AOM3': 'Controlling 369 A',
               'PCKR': 'Pulsepicker signal',
               'TRG': 'Temperal signal'}


# Output port configuration
C1_phase_shifter_port = 2
C2_phase_shifter_port = 3


var_dict = globals()
var_list = list(var_dict.keys())

for each_var in var_list:
    for (pin_name, mapping_name) in input_mapping.items():
        pin_name += '_'
        mapping_name += '_'
        index_found = each_var.find(pin_name)
        if index_found == -1:
            continue
        if index_found != 0:
            print('There is a variable (%s) whose name contains %s in the middle' \
                  % (each_var, pin_name))
            continue
        new_var_name = mapping_name + each_var[len(pin_name):]
        var_dict[new_var_name] = var_dict[each_var]

    for (mapping_name, pin_name) in output_mapping.items():
        pin_name += '_'
        mapping_name += '_'
        index_found = each_var.find(pin_name)
        if index_found == -1:
            continue
        if index_found != 0:
            print('There is a variable (%s) whose name contains %s in the middle' \
                  % (each_var, pin_name))
            continue
        new_var_name = mapping_name + each_var[len(pin_name):]
        var_dict[new_var_name] = var_dict[each_var]
