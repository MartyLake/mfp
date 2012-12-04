#! /usr/bin/env python2.6
'''
label_edit.py: Minor mode for editing contents of a clutter.Text label

Copyright (c) 2010 Bill Gribble <grib@billgribble.com>
'''

from ..input_mode import InputMode 
from mfp import log 

from gi.repository import Clutter 

class LabelEditMode (InputMode):
	def __init__(self, window, element, label, multiline=False, markup=False):
		self.manager = window.input_mgr 
		self.element = element 
		self.widget = label
		self.multiline = multiline 
		self.markup = markup
		self.text = self.widget.get_text()
		self.cursor_color = Clutter.Color.new(0, 0, 0, 64)
		self.undo_stack  = [ (self.text, len(self.text)) ] 
		self.undo_pos = -1
		self.editpos = 0

		self.activate_handler_id = None
		self.text_changed_handler_id = None 

		InputMode.__init__(self, "Edit text")
	
		if not self.multiline:
			self.bind("RET", self.commit_edits, "Accept edits")
		else:
			self.bind("C-RET", self.commit_edits, "Accept edits")

		self.bind("ESC", self.rollback_edits, "Discard edits")
		self.bind("LEFT", self.move_left, "Move cursor left")
		self.bind("RIGHT", self.move_right, "Move cursor right")
		self.bind("UP", self.move_up, "Move cursor up one line")
		self.bind("DOWN", self.move_down, "Move cursor down one line")
		self.bind("C-z", self.undo_edit, "Undo typing")
		self.bind("C-r", self.redo_edit, "Redo typing")


		inittxt = self.element.label_edit_start()
		if inittxt: 
			self.text = inittxt

		self.update_label(raw=True)
		self.start_editing() 


	def start_editing(self):
		def synth_ret(*args):
			self.manager.synthesize("RET")

		if self.multiline is False: 
			self.widget.set_single_line_mode(True)
			self.activate_handler_id = self.widget.connect("activate", synth_ret)
		else:
			self.widget.set_single_line_mode(False)

		self.text_changed_handler_id= self.widget.connect("text-changed", self.text_changed)

		self.editpos = len(self.text)
		self.widget.set_editable(True)
		self.widget.set_cursor_color(self.cursor_color)
		self.widget.set_cursor_visible(True)
		#self.widget.set_cursor_size(8)
		self.update_cursor()

	def end_editing(self):
		self.widget.set_editable(False)
		self.widget.set_cursor_visible(False)
		if self.activate_handler_id:
			self.widget.disconnect(self.activate_handler_id)
			self.widget.set_activatable(False)
			self.widget.set_single_line_mode(False)
			self.activate_handler_id = None
		if self.text_changed_handler_id:
			self.widget.disconnect(self.text_changed_handler_id)

	def text_changed(self, *args):
		new_text = self.widget.get_text()
		if new_text == self.text:
			return True 

		if self.undo_pos < -1:
			self.undo_stack[self.undo_pos:] = []
			self.undo_pos = -1

		self.undo_stack.append((self.text, self.editpos))
		self.text = new_text
		editpos = self.widget.get_cursor_position()
		if editpos == -1:
			self.editpos = len(self.text)
		else: 
			self.editpos = editpos+1
		return True 

	def commit_edits(self):
		self.text = self.widget.get_text()
		self.end_editing()
		self.update_label(raw=False)
		self.element.label_edit_finish(self.widget, self.text)
		self.element.end_edit()
		return True 

	def rollback_edits(self):
		txt, pos = self.undo_stack[0] 
		self.text = txt
		self.end_editing()
		self.update_label(raw=False)
		self.element.label_edit_finish(self.widget, None)
		self.element.end_edit()
		return True 

	def erase_forward(self):
		if self.editpos > (len(self.text) -1):
			return True 

		if self.undo_pos < -1:
			self.undo_stack[self.undo_pos:] = []
			self.undo_pos = -1
		self.undo_stack.append(self.text)
		self.text = self.text[:self.editpos] + self.text[self.editpos+1:]
		self.update_label(raw=True)
		return True 

	def erase_backward(self):
		if self.editpos <= 0:
			self.editpos = 0
			return True

		if self.undo_pos < -1:
			self.undo_stack[self.undo_pos:] = []
			self.undo_pos = -1

		self.undo_stack.append(self.text)
		self.text = self.text[:self.editpos-1] + self.text[self.editpos:]
		self.editpos = max(self.editpos - 1, 0)
		self.update_label(raw=True)
		return True 

	def move_to_start(self):
		self.editpos = 0
		self.update_label(raw=True)

	def move_to_end(self):
		self.editpos = len(self.text)
		self.update_label(raw=True)

	def move_left(self):
		self.editpos = max(self.editpos-1, 0)
		self.update_cursor()
		return True 

	def move_right(self):
		self.editpos = min(self.editpos+1, len(self.text))
		self.update_cursor()
		return True 

	def move_up(self):
		lines_above = self.text[:self.editpos].split("\n")
		line_pos = len(lines_above[-1])
		if len(lines_above) > 2:
			self.editpos = (sum([len(l) + 1 for l in lines_above[:-2] ])
				            + min(len(lines_above[-2]), line_pos))
		elif len(lines_above) > 1:
			self.editpos = min(len(lines_above[0]), line_pos)
		else: 
			self.editpos = 0
		self.update_cursor()
		return True

	def move_down(self):
		lines_above = self.text[:self.editpos].split("\n")
		lines_below = self.text[self.editpos:].split("\n")
		line_pos = len(lines_above[-1])
		line_start = self.editpos 

		if len(lines_below) > 1:
			self.editpos = (line_start + len(lines_below[0]) + 1 
				            + min(len(lines_below[1]), line_pos))  
		else:
			self.editpos = len(self.text)
		self.update_cursor()
		return True

	def undo_edit(self):
		#print "undo:", self.undo_pos, self.undo_stack
		if self.undo_pos == -1:
			self.undo_stack.append((self.text, self.editpos))
			self.undo_pos = -2
		if self.undo_pos > (-len(self.undo_stack)):
			self.text, self.editpos = self.undo_stack[self.undo_pos] 
			self.undo_pos = max(-len(self.undo_stack), self.undo_pos - 1)
			self.update_label(raw=True)

		return True 

	def redo_edit(self):
		#print "redo:", self.undo_pos, self.undo_stack
		if self.undo_pos < -1:
			self.undo_pos += 1
			self.text, self.editpos = self.undo_stack[self.undo_pos] 
			self.update_label(raw=True)
		return True 

	def update_cursor(self):
		self.widget.grab_key_focus()
		self.widget.set_cursor_position(self.editpos)
		self.widget.set_selection(self.editpos, self.editpos)

	def update_label(self, raw=True):
		if raw or self.markup is False:
			self.widget.set_use_markup = False 
			self.widget.set_text(self.text)
		else:
			self.widget.set_markup(self.text)
		self.update_cursor()
		return True 



					
