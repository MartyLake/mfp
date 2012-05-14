#! /usr/bin/env python2.6
'''
key_sequencer.py: Collect modifiers and key/mouse clicks into Emacs-like strings

Copyright (c) 2010 Bill Gribble <grib@billgribble.com>
'''

MOD_SHIFT = 65505
MOD_RSHIFT = 65506
MOD_CTRL = 65507
MOD_RCTRL = 65508
MOD_ALT = 65513
MOD_RALT = 65514
MOD_WIN = 65515
MOD_RWIN = 65516
MOD_ALL = [MOD_SHIFT, MOD_RSHIFT, MOD_CTRL, MOD_RCTRL, MOD_ALT, 
		   MOD_RALT, MOD_WIN, MOD_RWIN]

KEY_ESC = 65307 
KEY_TAB = 65289 
KEY_BKSP = 65288
KEY_PGUP = 65365
KEY_PGDN = 65366
KEY_HOME = 65360
KEY_END = 65367
KEY_INS = 65379
KEY_DEL = 65535
KEY_UP = 65362
KEY_DN = 65364
KEY_LEFT = 65361
KEY_RIGHT = 65363
KEY_ENTER = 65293 

def get_key_unicode(ev):
	if ev.unicode_value:
		print "unicode:", ev.unicode_value, type(ev.unicode_value)
		return ord(ev.unicode_value)
	else:
		v = clutter.keysym_to_unicode(ev.keyval)
		print "converted:", v, type(v)
		return v 

class KeySequencer (object):
	def __init__(self):
		self.mouse_buttons = set()
		self.mod_keys = set()
		
		self.sequences = [] 

	def pop(self):
		if len(self.sequences):
			rval = self.sequences[0]
			self.sequences[:1] = []
			return rval
		else:
			return None 

	def process(self, event):
		from gi.repository import Clutter as clutter 
	
		# KEY PRESS 
		if event.type == clutter.EventType.KEY_PRESS: 
			code = event.keyval
			if code in MOD_ALL:
				self.mod_keys.add(code)
			else:
				self.sequences.append(self.canonicalize(event))

		# KEY RELEASE 
		elif event.type == clutter.EventType.KEY_RELEASE:
			code = event.keyval
			if code in MOD_ALL:
				try:
					self.mod_keys.remove(code)
				except KeyError:
					pass

		# BUTTON PRESS, BUTTON RELEASE, MOUSE MOTION
		elif event.type in (clutter.EventType.BUTTON_PRESS, clutter.EventType.BUTTON_RELEASE, clutter.EventType.MOTION,
					        clutter.EventType.SCROLL):
			self.sequences.append(self.canonicalize(event))	
		
	def canonicalize(self, event):
		from gi.repository import Clutter as clutter 
		key = ''
		
		if (MOD_CTRL in self.mod_keys) or (MOD_RCTRL in self.mod_keys):
			key += 'C-'
		if (MOD_ALT in self.mod_keys) or (MOD_RALT in self.mod_keys): 
			key += 'A-'
		if (MOD_WIN in self.mod_keys) or (MOD_RWIN in self.mod_keys):
			key += 'W-'

		if event.type in (clutter.EventType.KEY_PRESS, clutter.EventType.KEY_RELEASE):
			ks = event.keyval
			if ks >= 256 and ((MOD_SHIFT in self.mod_keys) or (MOD_RSHIFT in self.mod_keys)):
				key = 'S-' + key 
		    	
			if ks == KEY_TAB:
				key += 'TAB'
			elif ks == KEY_UP:
				key += 'UP'
			elif ks == KEY_DN:
				key += 'DOWN'
			elif ks == KEY_LEFT:
				key += 'LEFT'
			elif ks == KEY_RIGHT:
				key += 'RIGHT'
			elif ks == KEY_ENTER:
				key += 'RET'
			elif ks == KEY_ESC:
				key += 'ESC'
			elif ks == KEY_DEL:
				key += 'DEL'
			elif ks == KEY_BKSP:
				key += 'BS'
			elif ks == KEY_INS:
				key += 'INS'
			elif ks < 256:
				kuni = get_key_unicode(event)
				if kuni < 32:
					ks = chr(event.keyval)
					if (MOD_SHIFT in self.mod_keys) or (MOD_RSHIFT in self.mod_keys):
						ks = ks.upper()
					key += ks 
				else:
					key += chr(kuni)
			else:
				key += "%d" % ks
		elif event.type in (clutter.EventType.BUTTON_PRESS, clutter.EventType.BUTTON_RELEASE):
			button = event.button
			clicks = event.click_count
			key += "M%d" % button

			if clicks == 2:
				key += "DOUBLE"
			elif clicks == 3:
				key += "TRIPLE"
		
			if event.type == clutter.EventType.BUTTON_PRESS:
				key += 'DOWN'
				self.mouse_buttons.add(button)
			else:
				key += 'UP'
				self.mouse_buttons.remove(button)

		elif event.type == clutter.EventType.MOTION:
			for b in (1,2,3):
				if b in self.mouse_buttons:
					key += 'M%d-' % b
			key += 'MOTION'

		elif event.type == clutter.EventType.SCROLL:
			for b in (1,2,3):
				if b in self.mouse_buttons:
					key += 'M%d-' % b
			key += 'SCROLL'
			if event.scroll_direction:
				key += 'DOWN'
			else:
				key += 'UP'
		return key 	



	
