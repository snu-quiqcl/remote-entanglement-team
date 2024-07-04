"""
This module defines TimeTableWidgetItem class and classes that inherit it
TimeTableWidgetItem class in herits QtWidgets.QTableWidgetItem
and as a result, these classes correspond to one cell of TimeTableWidget

Note that TimeTableWidgetItem class is intended as an abstract class
In other words, it is not recommended to make a TimeTableWidgetItem instance
"""

from PyQt5 import QtWidgets, QtGui, QtCore

from .const import *
from .utility import *

class TimeTableWidgetItem(QtWidgets.QTableWidgetItem):
    def __init__(self, interval, theme):
        super().__init__()
        self._theme = theme
        if self._theme == "white":
            self.white_background = QtGui.QColor(0xFF, 0xFF, 0xFF) # white
            self.colored_background = QtGui.QColor(145, 168, 210)
            self.default_foreground = QtGui.QColor(0, 0, 0)
            self.error_background = QtGui.QColor(0xFF, 0, 0, 0x7F)  # red(half-opacity)
        elif self._theme == "black":
            self.white_background = QtGui.QColor(40, 40, 40) # darkgray
            self.colored_background = QtGui.QColor(240, 180, 60)
            self.default_foreground = QtGui.QColor(180, 180, 180)
            self.error_background = QtGui.QColor(0xFF, 0, 0, 0x7F)  # red(half-opacity)
        self.setBackground(self.white_background)

        self.interval = interval
        self.time_table = self.interval.time_table

        self.use_output_port = False
        self.output_status = 0

        self.string_restriction = False
        self.allowed_string = [""]

        self.cell_widget = None

    def cell_clicked(self):
#           if self.use_output_port:
        self.output_status = -self.output_status + 1
        self.change_background()
        self.interval.check_instruction()
        # also need to check next instruction because of set_output, set_counter
        if self.interval.next_interval != None:
             self.interval.next_interval.check_instruction()
             # also need to check next next instruction in case next_interval has 0ns time_length
             if 0 in self.interval.next_interval.get_time_length() and self.interval.next_interval.next_interval != None:
                  self.interval.next_interval.next_interval.check_instruction()

    def text_changed(self):
          if not self.check_allowed_string(self.text()):
               self.setText("")
          self.interval.check_instruction()

    def check_allowed_string(self, string):
          regular_expression = QtCore.QRegExp(self.get_regular_expression())
          if not self.string_restriction or regular_expression.exactMatch(string):
               return True
          else:
               self.time_table.write_text_display("Can only write {} in this cell.".format(self.allowed_string))
               return False

    def change_background(self):
          if self.output_status:
               self.setBackground(self.colored_background)
               self.setForeground(QtGui.QColor(0, 0, 0))
          else:
               self.setBackground(self.white_background)
               self.setForeground(self.default_foreground)

    def show_error_background(self):
          # need revision...
          if not self.use_output_port:
               self.setBackground(self.error_background)

    def undo_error_background(self):
          self.change_background()

    def get_regular_expression(self):
          reg_exp = ""
          for string in self.allowed_string:
               if string == "":
                    continue
               reg_exp += string_to_regular_expression(string)
               reg_exp += "|"
          reg_exp = reg_exp[:-1]  # delete last "|"

          if "" in self.allowed_string:
               reg_exp = "(" + reg_exp + ")?"

          return reg_exp

    def get_reg_index_from_text(self):
          """
          returns the index of reg in the text
          Note that this method returns only the first index in text
          """
          if "reg[" not in self.text():
               return -1
          text = self.text()
          text = text[text.find("[")+1:]
          text = text[:text.find("]")]
          return int(text)


class AddDeleteColumnItem(TimeTableWidgetItem):
     def __init__(self, interval, theme):
          super().__init__(interval, theme)
          self._theme = theme
          self.cell_widget = ButtonTableCellWidget(parent=self.time_table, 
                                                             item = self,
                                                             column_number=2,
                                                             text_list=["Delete", "Add"])

          self.cell_widget.cellWidget(0, 0).clicked.connect(self.delete_button_clicked_slot)
          self.cell_widget.cellWidget(0, 1).clicked.connect(self.add_button_clicked_slot)

     # slot method
     def delete_button_clicked_slot(self):
          if self.time_table.columnCount() == 1:
               return
          self.time_table.delete_column(self.get_column_number())

     def add_button_clicked_slot(self):
          self.time_table.insert_column(self.get_column_number()+1)

     # get function
     def get_column_number(self):
          return self.interval.get_column_number()


class InstructionLabelsItem(TimeTableWidgetItem):
     def __init__(self, interval, theme):
          super().__init__(interval, theme)
          self._theme = theme
          self.string_restriction = True  # Hmm... well there are still restrictions... right?

     def text_changed(self):
          # all intervals need to be checked in case that changing this label has impact on some branch instructions
          if self.text()[-1:] == ";":
               self.setText(self.text()[:-1])
          elif self.text()[-2:] == "; ":
               self.setText(self.text()[:-2])

          if not self.check_allowed_string(self.text()):
               self.setText("")
          self.interval.set_instruction_labels(self.get_instruction_labels_from_text())

     def check_allowed_string(self, string):
          regular_expression = QtCore.QRegExp(self.get_regular_expression())
          if not self.string_restriction or regular_expression.exactMatch(string):
               return True
          else:
               self.time_table.write_text_display(
                    "An instruction label should contain only alphabets(a-z, A-Z), numbers(0-9) and underscores(_) and must start with an alphabet.")
               self.time_table.write_text_display("For multiple instruction labels, use '; ' for seperation.")
               return False

     def get_regular_expression(self):
          # contains only alphabets, numbers and _. no space
          # starts with an alphabet
          return QtCore.QRegExp("([a-zA-Z]([a-zA-Z0-9_]*)(; [a-zA-Z]([a-zA-Z0-9_]*))*)?")

     def get_instruction_labels_from_text(self):
          if self.text() == "":
               return []
          return self.text().split("; ")


class TimeLengthUnitItem(TimeTableWidgetItem):
     def __init__(self, interval, theme):
          super().__init__(interval, theme)
          self._theme = theme
          self.cell_widget = ComboBoxCellWidget(parent=self.time_table, 
                                                         item=self, 
                                                         select_list=[UNIT_NS, UNIT_US, UNIT_MS, UNIT_S])

          self.cell_widget.currentTextChanged.connect(self.text_changed_slot)

     # slot method
     def text_changed_slot(self):
          self.interval.set_time_length_unit(self.cell_widget.currentText())


class TimeLengthItem(TimeTableWidgetItem):
     def __init__(self, interval, theme):
          super().__init__(interval, theme)
          self._theme = theme
          self.string_restriction = True
          self.allowed_string = ["time_length(ns)", "start:step:stop(ns)"]
          self.time_step = TIME_STEP_NS
          self.time_max = TIME_MAX_NS
          self.setText(str(TIME_STEP_NS))

     def text_changed(self):
          if not self.check_allowed_string(self.text()):
               self.setText(str(self.time_step))

          if self.text() != "" and self.get_time_length_from_text() == range(0):
               self.time_table.write_text_display("Improper time range: {} is an empty range.".format(self.text()))
               self.setText(str(self.time_step))
          elif self.get_time_length_from_text() == range(1):
               self.time_table.write_text_display("Improper time range: {} has only 0ns in range.".format(self.text()))
               self.setText(str(self.time_step))

          for time in self.get_time_length_from_text():
               if time > self.time_max:
                    self.time_table.write_text_display("{} exceeded the time maximum {}.".format(self.text(), self.time_max))
                    self.setText(str(self.time_step))
                    break
          self.interval.set_time_length(self.get_time_length_from_text())

     def set_nano_sec_mode(self):
          self.time_step = TIME_STEP_NS
          self.time_max = TIME_MAX_NS
          self.allowed_string = ["time_length(ns)", "start:step:stop(ns)"]
          self.text_changed()

     def set_micro_sec_mode(self):
          self.time_step = TIME_STEP_US
          self.time_max = TIME_MAX_US
          self.allowed_string = ["time_length(us)", "start:step:stop(us)"]
          self.text_changed()

     def set_milli_sec_mode(self):
          self.time_step = TIME_STEP_MS
          self.time_max = TIME_MAX_MS
          self.allowed_string = ["time_length(ms)", "start:step:stop(ms)"]
          self.text_changed()

     def set_sec_mode(self):
          self.time_step = TIME_STEP_S
          self.time_max = TIME_MAX_S
          self.allowed_string = ["time_length(s)", "start:step:stop(s)"]
          self.text_changed()

     def get_time_length_from_text(self):
          if self.text() == "":
               return range(0)
          if ":" not in self.text():
               time_length = int(self.text())
               return range(time_length, time_length+1)
          start, step, stop = map(int, self.text().split(":"))
          return range(start, stop, step)


class OutputItem(TimeTableWidgetItem):
     def __init__(self, interval, theme):
          super().__init__(interval, theme)
          self.colored_background = QtGui.QColor(0x9A, 0xCD, 0x32)  # yellowgreen
          self.use_output_port = True
          self.string_restriction = True


class CounterItem(TimeTableWidgetItem):
     def __init__(self, interval, theme):
          super().__init__(interval, theme)
          self.colored_background = QtGui.QColor(0x87, 0xCE, 0xEB)  # skyblue
          self.use_output_port = True
          self.string_restriction = True
          self.allowed_string += ["reset", "read reg[n]"]


class StopwatchItem(TimeTableWidgetItem):
     def __init__(self, interval, theme):
          super().__init__(interval, theme)
          self.string_restriction = True
          self.allowed_string += ["reset", "start", "read reg[n]"]


class ReadOnlyItem(TimeTableWidgetItem):
     def __init__(self, interval, theme):
          super().__init__(interval, theme)
          self.string_restriction = True
          self.allowed_string += ["read reg[n]"]


class WriteToFIFOItem(TimeTableWidgetItem):
     def __init__(self, interval, theme):
          super().__init__(interval, theme)
          self._theme = theme
          self.string_restriction = True
          self.allowed_string = ["reg[n], reg[n], reg[n], event_label"]

     def check_allowed_string(self, string):
          if super().check_allowed_string(string):
               return True
          self.time_table.write_text_display("Maximum value of event_label is 65535.")
          return False

     def get_reg_indices_from_text(self):
          if self.text() == "":
               return tuple()
          text = self.text()
          text = text.replace("reg[", "")
          text = text.replace("]", "")
          return tuple(map(int, text.split(", ")))


class BranchItem(TimeTableWidgetItem):
     def __init__(self, interval, theme):
          super().__init__(interval, theme)
          self._theme = theme
          self.string_restriction = True
          self.allowed_string = ["reset target", "target", "target, iteration"]

     def text_changed(self):
          if not self.check_allowed_string(self.text()):
               self.setText("")
          self.interval.set_branch_target(self.get_target_from_text())

     def check_allowed_string(self, string):
          if super().check_allowed_string(string):
               return True
          self.time_table.write_text_display("Maximum value of iteration is 65535.")
          return False

     def get_target_from_text(self):
          target = self.text()
          target = target.replace("reset ", "")
          if "," in target:
               target = target[:target.find(",")]
          return target

     def get_iteration_from_text(self):
          iteration = -1
          if "," in self.text():
               text = self.text()
               iteration = int(text[text.find(",")+2:])
          return iteration


# cell widgets
class ButtonTableCellWidget(QtWidgets.QTableWidget):
     def __init__(self, parent=None, item=None, row_number=1, column_number=1, text_list=[]):
          super().__init__(parent=parent)
          self.item = item

          for i in range(len(text_list), row_number*column_number):
               text_list.append("PushButton")

          self.setRowCount(row_number)
          self.setColumnCount(column_number)
          for r in range(row_number):
               for c in range(column_number):
                    self.setCellWidget(r, c, QtWidgets.QPushButton(text=text_list[r*column_number+c]))
                    self.cellWidget(r, c).setText(text_list[r*column_number+c])

          row_h = int ((TABLE_CELL_H-2) / row_number)
          col_w = int ((TABLE_CELL_W-2) / column_number)
          for r in range(row_number):
               self.setRowHeight(r, row_h)
          for c in range(column_number):
               self.setColumnWidth(c, col_w)

          self.horizontalHeader().hide()
          self.verticalHeader().hide()


class ComboBoxCellWidget(QtWidgets.QComboBox):
     def __init__(self, parent=None, item=None, select_list=None):
          super().__init__(parent=parent)
          self.item = item
          if select_list != None:
               self.addItems(select_list)


# Not used
# class SpinBoxCellWidget(QtWidgets.QSpinBox):
#      def __init__(self, parent=None, item=None, min_value=0, max_value=int(1e9), single_step=1):
#           super().__init__(parent=parent)
#           self.item = item
#           self.setMinimum(min_value)
#           self.setMaximum(max_value)
#           self.setSingleStep(single_step)

#      def adjust_value(self):
#           self.setValue(self.value() - (self.value() - self.minimum()) % self.singleStep())

