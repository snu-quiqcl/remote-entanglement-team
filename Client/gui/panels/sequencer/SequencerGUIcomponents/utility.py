
from .const import *

def string_to_regular_expression(string):
	"""
	string: String
	return: a string of regular expression
	returns the regular expression form of the input string
	conversion is done according to the reg_exp_dict in const

	Note that this function is used only for this module
	That is, this is not a general function that converts any string into regular expressions
	this should of course not be applied to general situations
	"""
	for key in reg_exp_dict:
		string = string.replace(key, reg_exp_dict[key])
	return string

def place_code_in_for_loop(iter_index, iter_range, body_code):
	tabbed_body = insert_tab_in_front_of_row(body_code)
	code = "for {} in {}:\n{}".format(iter_index, iter_range, tabbed_body)
	return code

def place_code_in_while_loop(while_cond, while_body):
	tabbed_body = insert_tab_in_front_of_row(while_body)
	code = "while {}:\n{}".format(while_cond, tabbed_body)
	return code

def place_code_in_if_cond(if_cond, if_body, else_body="", elif_conds=[], elif_bodies=[]):
	if len(elif_conds) != len(elif_bodies):
		print("The lengths of elif_conds and elif_bodies do not match.")
		return
	tabbed_body = insert_tab_in_front_of_row(if_body)
	if_code = "if {}:\n{}".format(if_cond, tabbed_body)
	
	for i in range(len(elif_conds)):
		tabbed_body = insert_tab_in_front_of_row(elif_bodies[i])
		one_elif_code = "elif {}:\n{}".format(elif_conds[i], tabbed_body)
		if_code += one_elif_code
	
	if else_body != "":
		tabbed_body = insert_tab_in_front_of_row(else_body)
		else_code = "else:\n{}".format(tabbed_body)
		if_code += else_code

	return if_code

def insert_tab_in_front_of_row(code):
	code = "\t" + code
	code = code.replace("\n", "\n\t")
	if code[-2:] == "\n\t":
		code = code[:-1]
	else:
		code += "\n"
	return code
