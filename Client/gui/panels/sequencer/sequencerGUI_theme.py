# -*- coding: utf-8 -*-
"""
Created on Thu Oct 28 17:55:59 2021

@author: QCP32
"""
class SequencerGUI_theme_base():
    
    _themes = ["black", "white"]
    _theme = "white"
                                     
    _mainwindow_stylesheet = {"white": """
                                      QWidget{
                                             background-color:rgb(255,255,255);
                                             selection-background-color:rgb(130,150,200);
                                             gridline-color:rgb(120,120,120);
                                             color:rgb(0,0,0);
                                             }
                                     QHeaderView{background-color:rgb(210,210,210);}
                                     QHeaderView::section{background-color:rgb(210,210,210);}
                                     QHeaderView::section::checked{background-color:rgb(130,150,200);color:rgb(255,255,255);}
                                     QTableCornerButton::section{background-color:rgb(255,255,255);}
                                     QComboBox{background-color:rgb(210,210,210);}
                                     QPushButton{background-color:rgb(255,255,255);}
                                     """,
                              "black": """
                                      QWidget{
                                             background-color:rgb(40,40,40);
                                             selection-background-color:rgb(210,120,20);
                                             color:rgb(180,180,180);
                                             gridline-color:rgb(120,120,120);
                                             }
                                     QHeaderView{background-color:rgb(80,80,80);}
                                     QHeaderView::section{background-color:rgb(80,80,80);}
                                     QHeaderView::section::checked{background-color:rgb(210,120,20);color:rgb(255,255,255);}
                                     QTableCornerButton::section{background-color:rgb(40,40,40);}
                                     QComboBox{background-color:rgb(80,80,80);}
                                     QPushButton{background-color:rgb(40,40,40);}
                                     """}
    
    _pushbutton_stylesheet = {"white": "background-color:rgb(210,210,210)",
                              "black": "background-color:rgb(80,80,80)"}
                                       
    _label_stylesheet = {"white": "background-color:rgb(210,210,210);border:1px solid darkgray",
                         "black": "background-color:rgb(80,80,80);border:1px solid gray"}

    def changeTheme(self, theme):
        self._theme = theme
        self.setStyleSheet(self._mainwindow_stylesheet[self._theme])
        
        # # # # # buttons
        self.btn_hd.setStyleSheet(self._pushbutton_stylesheet[self._theme])
        self.btn_program.setStyleSheet(self._pushbutton_stylesheet[self._theme])
        self.btn_to_python.setStyleSheet(self._pushbutton_stylesheet[self._theme])
        self.btn_append_column.setStyleSheet(self._pushbutton_stylesheet[self._theme])
        
        # line edit
        self.text_display.setStyleSheet(self._label_stylesheet[self._theme])
        self.line_edit_hd.setStyleSheet(self._label_stylesheet[self._theme])
        self.line_edit_serial.setStyleSheet(self._label_stylesheet[self._theme])
    