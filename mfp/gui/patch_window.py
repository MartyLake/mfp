#! /usr/bin/env python
'''
patch_window.py
The main MFP window and associated code 
'''

from gi.repository import Gtk, GObject, Clutter, GtkClutter, Pango

from text_element import TextElement
from processor_element import ProcessorElement
from message_element import MessageElement
from enum_element import EnumElement
from plot_element import PlotElement
from patch_element import PatchElement 

from mfp import MFPGUI
from mfp.main import MFPCommand
from mfp import log 

from .input_manager import InputManager
from .console import ConsoleMgr 
from .modes.global_mode import GlobalMode 
from .modes.patch_edit import PatchEditMode
from .modes.patch_control import PatchControlMode 
from .modes.select_mru import SelectMRUMode

class PatchWindow(object):
	def __init__(self):
		# load Glade ui
		self.builder = Gtk.Builder()
		self.builder.add_from_file("mfp/gui/mfp.glade")

		# install Clutter stage in Gtk window
		self.window = self.builder.get_object("main_window")
		self.embed = GtkClutter.Embed.new()
		self.embed.set_sensitive(True)
		self.embed.set_size_request(600, 400)
		self.stage = self.embed.get_stage()
		box = self.builder.get_object("stage_box")
		box.pack_start(self.embed, True, True, 0)

		# significant widgets we will be dealing with later 
		self.console_view = self.builder.get_object("console_text")
		self.log_view = self.builder.get_object("log_text") 
		self.object_view = self.builder.get_object("object_tree") 
		self.layer_view = self.builder.get_object("layer_tree") 
		self.layer_store = None 
		self.object_store = None 

		# objects for stage -- self.group gets moved/scaled to adjust 
		# the view, so anything not in it will be static on the stage 
		self.group = Clutter.Group()
		self.hud_history = [] 
		self.autoplace_marker = None 
		self.autoplace_layer = None 

		self.stage.add_actor(self.group)

		# self.objects is PatchElement subclasses represented the
		# currently-displayed patch(es)
		self.patches = [] 
		self.objects = [] 

		self.selected_patch = None 
		self.selected_layer = None  
		self.selected = None

		self.input_mgr = InputManager(self)
		self.console_mgr = ConsoleMgr("MFP interactive console", self.console_view)
		self.console_mgr.start()

		# dumb colors 
		self.color_unselected = Clutter.Color()
		self.color_unselected.from_string('Black')
		self.color_selected = Clutter.Color()
		self.color_selected.from_string('Red')
		self.color_bg = Clutter.Color()
		self.color_bg.from_string("White")

		# configure Clutter stage 
		self.stage.set_color(self.color_bg)
		self.stage.set_property('user-resizable', True)
		self.zoom = 1.0
		self.view_x = 0
		self.view_y = 0

		# show top-level window
		self.stage.show()
		self.window.show_all()
		
		# set up key and mouse handling 
		self.init_input()
		self.init_layer_view()
		self.init_object_view()

	def init_input(self):
		def grab_handler(stage, event):
			if not self.embed.has_focus():
				self.embed.grab_focus()
			self.input_mgr.handle_event(stage, event)

		def handler(stage, event):
			self.input_mgr.handle_event(stage, event)

		self.embed.set_can_focus(True)
		self.embed.grab_focus()

		# hook up signals 
		self.stage.connect('button-press-event', grab_handler)
		self.stage.connect('button-release-event', grab_handler)
		self.stage.connect('key-press-event', grab_handler)
		self.stage.connect('key-release-event', grab_handler)
		self.stage.connect('destroy', self.quit)
		self.stage.connect('motion-event', handler)
		self.stage.connect('enter-event', handler)
		self.stage.connect('leave-event', handler) 
		self.stage.connect('scroll-event', grab_handler) 

		# set initial major mode 
		self.input_mgr.global_mode = GlobalMode(self)
		self.input_mgr.major_mode = PatchEditMode(self)

		# set tab stops on keybindings view 
		ta = Pango.TabArray.new(1, True)
		ta.set_tab(0, Pango.TabAlign.LEFT, 120)
		self.builder.get_object("key_bindings_text").set_tabs(ta)

		# show keybindings 
		self.display_bindings()

	def init_layer_view(self):
		self.layer_store = Gtk.TreeStore(GObject.TYPE_PYOBJECT, GObject.TYPE_STRING,
										 GObject.TYPE_STRING)
		self.layer_view.set_model(self.layer_store)
		self.layer_view.get_selection().connect("changed", self.layer_select_cb)


		for header, num, edited_cb in [("Layer", 1, self.layer_name_edited_cb), 
								       ("Scope", 2, self.layer_scope_edited_cb)]:
			r = Gtk.CellRendererText()
			if edited_cb: 
				r.set_property("editable", 1)
				r.connect("edited", edited_cb)
			col = Gtk.TreeViewColumn(header, r, text=num)
			self.layer_view.append_column(col)

		self.layer_store_update()

	def init_object_view(self):
		def select_cb(selection):
			model, iter = selection.get_selected()
			if iter is None: 
				self.unselect_all()
			else:
				obj = self.object_store.get_value(iter, 1) 
				if isinstance(obj, PatchElement) and obj is not self.selected:
					self.select(obj)
					if obj.layer is not None:
						self.layer_select(obj.layer)

		self.object_store = Gtk.TreeStore(GObject.TYPE_STRING, GObject.TYPE_PYOBJECT)
		self.object_view.set_model(self.object_store)
		self.object_view.get_selection().connect("changed", select_cb)

		r = Gtk.CellRendererText()
		r.set_property("editable", True)
		r.connect("edited", self.object_name_edited_cb)
		col = Gtk.TreeViewColumn("Name", r, text=0)
		self.object_view.append_column(col)

	def object_name_edited_cb(self, renderer, path, new_value):
		from .patch_layer import PatchLayer 

		iter = self.object_store.get_iter_from_string(path)
		obj = self.object_store.get_value(iter, 1)
		if isinstance(obj, PatchElement):
			obj.obj_name = new_value
			MFPCommand().rename_obj(obj.obj_id, new_value)
			obj.send_params()

		elif isinstance(obj, PatchLayer):
			oldscopename = obj.scope 
			for l in self.selected_patch.layers:
				if l.scope == oldscopename:
					l.scope = new_value
			MFPCommand.rename_scope(oldscopename, new_value)
			seld.selected_patch.send_params()
		self.object_store_update()
		self.layer_store_update()
		return True 

	def add_patch(self, patch_info):
		self.patches.append(patch_info)
		self.selected_patch = patch_info
		self.layer_store_update()
		if len(patch_info.layers): 
			self.layer_select(self.selected_patch.layers[0])
		
	def object_selection_update(self):
		found = []
		def	check(model, path, it, data):
			if self.object_store.get_value(it, 1) == self.selected:
				found[:] = path
				return True
			return False 

		model, iter = self.object_view.get_selection().get_selected()

		if iter is None or self.object_store.get_value(iter, 1) != self.selected: 
			self.object_store.foreach(check, None)
			if found:
				self.object_view.get_selection().select_path(found[0])

	def object_store_update(self):
		scopes = {} 
		self.object_store.clear()

		for p in self.patches:
			piter = self.object_store.append(None)
			self.object_store.set_value(piter, 0, p.obj_name or "Default Patch")
			self.object_store.set_value(piter, 1, p)

			oiter = self.object_store.append(piter)
			self.object_store.set_value(oiter, 0, "__patch__")
			self.object_store.set_value(oiter, 1, p)
			scopes['__patch__'] = oiter 

			for l in p.layers: 
				if l.scope is None:
					continue 
				elif scopes.get(l.scope) is not None:
					continue
				oiter = self.object_store.append(piter)
				self.object_store.set_value(oiter, 0, l.scope)
				self.object_store.set_value(oiter, 1, l)
				scopes[l.scope] = oiter

		for o in self.objects:
			if o.obj_name is None:
				continue

			if o.layer.scope is None:
				parent = None 
			else:
				parent = scopes.get(o.layer.scope)
			oiter = self.object_store.append(parent)
			self.object_store.set_value(oiter, 0, o.obj_name)
			self.object_store.set_value(oiter, 1, o)
		
		self.object_view.expand_all()

	def active_layer(self):
		return self.selected_layer

	def active_group(self):
		return self.selected_layer.group 

	def ready(self):
		if self.window and self.window.get_realized():
			return True
		else:
			return False 

	def stage_pos(self, x, y):
		success, new_x, new_y = self.group.transform_stage_point(x, y)
		if success:
			return (new_x, new_y) 
		else:
			return (x, y)

	def display_bindings(self):
		lines = ["Active key/mouse bindings"]
		for m in self.input_mgr.minor_modes: 
			lines.append("\nMinor mode: " + m.description)
			for b in m.directory():
				lines.append("%s\t%s" % (b[0], b[1]))

		m = self.input_mgr.major_mode
		lines.append("\nMajor mode: " + m.description)
		for b in m.directory():
			lines.append("%s\t%s" % (b[0], b[1]))

		lines.append("\nGlobal bindings:")
		m = self.input_mgr.global_mode 
		for b in m.directory():
			lines.append("%s\t%s" % (b[0], b[1]))

		txt = '\n'.join(lines)

		tv = self.builder.get_object("key_bindings_text")
		buf = tv.get_buffer()
		iterator = buf.get_end_iter()
		buf.delete(buf.get_start_iter(), buf.get_end_iter())
		buf.insert(buf.get_end_iter(), txt) 


	def show_autoplace_marker(self, x, y):
		if self.autoplace_marker is None:
			self.autoplace_marker = Clutter.Text()
			self.autoplace_marker.set_text("+")
			self.autoplace_layer = self.selected_layer
			self.autoplace_layer.group.add_actor(self.autoplace_marker)
		elif self.autoplace_layer != self.selected_layer: 
			self.autoplace_layer.group.remove_actor(self.autoplace_marker)
			self.autoplace_layer = self.selected_layer 
			self.autoplace_layer.group.add_actor(self.autoplace_marker)
		self.autoplace_marker.set_position(x, y)
		self.autoplace_marker.set_depth(-10)
		self.autoplace_marker.show()

	def hide_autoplace_marker(self):
		if self.autoplace_marker:
			self.autoplace_marker.hide()

	def toggle_major_mode(self):
		if isinstance(self.input_mgr.major_mode, PatchEditMode):
			self.input_mgr.set_major_mode(PatchControlMode(self))
		else:
			self.input_mgr.set_major_mode(PatchEditMode(self))
		return True 

	def register(self, element):
		self.objects.append(element)
		self.input_mgr.event_sources[element] = element
		self.active_group().add_actor(element)

		self.active_layer().add(element)

		if element.obj_id is not None:
			element.send_params()
		self.object_store_update()

	def unregister(self, element):
		if self.selected == element:
			self.unselect(element)

		element.layer.remove(element)
		self.objects.remove(element)

		del self.input_mgr.event_sources[element]
		self.active_group().remove_actor(element)
		self.object_store_update()

		# FIXME hook
		SelectMRUMode.forget(element)

	def refresh(self, element): 
		self.object_store_update()

	def add_element(self, factory, x=None, y=None):
		if x is None:
			x = self.input_mgr.pointer_x
		if y is None:
			y = self.input_mgr.pointer_y
		
		b = factory(self, x, y)
		self.select(b)
		b.begin_edit()	
		return True 

	def quit(self, *rest):
		log.debug("Quit command from GUI or WM, shutting down")
		if self.console_mgr:
			self.console_mgr.quitreq = True 
			self.console_mgr.join()
			log.debug("Console thread reaped")

		MFPCommand().quit()
		return True 

	def console_write(self, msg):
		buf = self.console_view.get_buffer()
		iterator = buf.get_end_iter()
		mark = buf.get_mark("console_mark")
		if mark is None:
			mark = Gtk.TextMark.new("console_mark", False)
			buf.add_mark(mark, iterator)

		buf.insert(iterator, msg, -1)
		iterator = buf.get_end_iter()
		buf.move_mark(mark, iterator)
		self.console_view.scroll_to_mark(mark, 0, True, 1.0, 0.9)

	def log_write(self, msg):
		# this is a bit complicated so that we ensure scrolling is 
		# reliable... scroll_to_iter can act odd sometimes 
		buf = self.log_view.get_buffer()
		iterator = buf.get_end_iter()
		mark = buf.get_mark("log_mark")
		if mark is None:
			mark = Gtk.TextMark.new("log_mark", False)
			buf.add_mark(mark, iterator)
		buf.insert(iterator, msg, -1)
		iterator = buf.get_end_iter()
		buf.move_mark(mark, iterator)
		self.log_view.scroll_to_mark(mark, 0, True, 0, 0.9)
	
	def hud_write(self, msg, disp_time=3.0):
		def anim_complete(anim):
			new_history = [] 
			for h_actor, h_anim, h_msg in self.hud_history: 
				if anim != h_anim:
					new_history.append((h_actor, h_anim, h_msg))
				else:
					h_actor.destroy()
			self.hud_history = new_history


		if not len(self.hud_history) or self.hud_history[-1][2] != msg:
			for actor, anim, oldmsg in self.hud_history:
				actor.set_position(actor.get_x(), actor.get_y() - 20)
		else:
			self.hud_history[-1][1].completed() 

		actor = Clutter.Text()
		self.stage.add_actor(actor)
		actor.set_position(10, self.stage.get_height() - 25)
		actor.set_property("opacity", 255)
		actor.set_markup(msg)

		animation = actor.animatev(Clutter.AnimationMode.EASE_IN_CUBIC, 
							       disp_time * 1000.0, [ 'opacity' ], [ 0 ])
		self.hud_history.append((actor, animation, msg))
		animation.connect_after("completed", anim_complete)

	

# additional methods in @extends wrappers 
import patch_layer
import patch_funcs 


