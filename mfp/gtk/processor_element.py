#! /usr/bin/env python2.6
'''
processor_element.py
A patch element corresponding to a signal or control processor 
'''

import clutter 
import math 
from patch_element import PatchElement
from mfp import MFPGUI
from input_mode import InputMode

class ProcessorElement (PatchElement):
	def __init__(self, window, x, y):
		PatchElement.__init__(self, window, x, y)

		self.proc_id = None 	
		self.proc_type = None
		self.proc_args = None 
		self.connections_out = [] 
		self.connections_in = [] 
		self.editable = False 

		# create elements 
		self.actor = clutter.Group()
		self.rect = clutter.Rectangle()
		self.label = clutter.Text()

		# configure rectangle box 
		self.rect.set_size(35, 20)
		self.rect.set_border_width(2)
		self.rect.set_border_color(window.color_unselected)
		self.rect.set_reactive(False)

		# configure label
		self.label.set_position(4, 1)
		self.label.set_color(window.color_unselected) 
		self.label.connect('text-changed', self.text_changed_cb)
		self.label.set_reactive(False)

		self.actor.add(self.rect)
		self.actor.add(self.label)
		self.actor.set_reactive(True)

		self.move(x, y)

		# add components to stage 
		self.stage.register(self)

	def update_label(self, *args):
		t = self.label.get_text()
		parts = t.split(' ', 1)
		self.proc_type = parts[0]
		if len(parts) > 1:
			self.proc_args = parts[1]

		print "ProcessorElement: processor=%s, args=%s" % (self.proc_type, self.proc_args)
		print self.label.get_text()
		self.proc_id = MFPGUI.create(self.proc_type, self.proc_args)
		if self.proc_id is None:
			print "ProcessorElement: could not create", self.proc_type, self.proc_args

	def text_changed_cb(self, *args):
		lwidth = self.label.get_property('width') 
		bwidth = self.rect.get_property('width')
			
		new_w = None 
		if (lwidth > (bwidth - 14)):
			new_w = lwidth + 14
		elif (bwidth > 35) and (lwidth < (bwidth - 14)):
			new_w = max(35, lwidth + 14)

		if new_w is not None:
			self.rect.set_size(new_w, self.rect.get_property('height'))

	def move(self, x, y):
		self.position_x = x
		self.position_y = y
		self.actor.set_position(x, y)

		for c in self.connections_out:
			c.draw()
		
		for c in self.connections_in:
			c.draw()

	def select(self):
		self.selected = True 
		self.rect.set_border_color(self.stage.color_selected)

	def unselect(self):
		self.selected = False 
		self.rect.set_border_color(self.stage.color_unselected)

	def toggle_edit(self):
		if self.editable:
			self.label.set_editable(False)
			self.stage.stage.set_key_focus(None)
			self.editable = False 
		else:
			self.label.set_editable(True)
			self.stage.stage.set_key_focus(self.label)
			self.editable = True



