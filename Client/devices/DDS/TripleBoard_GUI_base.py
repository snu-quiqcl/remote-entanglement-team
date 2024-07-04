# -*- coding: utf-8 -*-
"""
Created on Sun Aug 29 22:03:48 2021

@author: QCP32
"""

class DDS_gui_base(object):
    """
    DDS gui base is made to save trivial informations.
    Thought it would be useful to communicate through a TCP server
    """
    
    _widget_x = 10
    _widget_y = 130
    _widget_width = 560
    _widget_height = 430
    
    """
    DDS dict contains all board informations
    Each board_dict contains freq/power/phase and each step informations
    """
    DDS_dict = {}
    Board_dict = {'freq': 20,
                  'freq unit': 'MHz',
                  
                  'power': 0,
                  'power step': 1,
                  
                  'phase': 0,
                  'phase step': 1,
                  
                  'run': False}
    