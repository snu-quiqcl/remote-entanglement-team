# -*- coding: utf-8 -*-
"""
Created on Wed Feb  7 07:59:12 2018

@author: 1109282

According to the given mapping, we will add alias for each pin
"""

from HardwareDefinition_v4_01 import *

# Input port pin mapping
# For input pin, there will be only one driver
input_mapping = {'jb_0': 'PMT','ja_2': 'PMT2', 'ja_2': 'shutter_control'}

# Output port pin mapping
# For output pin, there might be more than one device controlled by the output pin
                  
output_mapping = {'MW': 'ja_5', \
                  'EOM_7G_1' : 'ja_1', \
                  'EOM_7G_2'  : 'ja_0', \
                  'EOM_2G': 'ja_6', \
                  'AOM' : 'ja_7', \
                  'AOM_400': 'ja_4'}

description = {'MW': 'Turing MW on/off', \
		'EOM_7G_1': 'Cooling sideband', \
		'EOM_7G_2': 'Cooling sideband', \
		'EOM_2G': 'Initialization beam', \
		'AOM': '359 nm laser beam', \
        'AOM_400': '400 MHz AOM'}

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
    
    
    