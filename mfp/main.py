#! /usr/bin/env python2.6
'''
main.py: main routine for mfp

Copyright (c) 2010 Bill Gribble <grib@billgribble.com>
'''

import sys, os
import multiprocessing 
import threading

from mfp.dsp_slave import dsp_init, DSPObject
from mfp.gui_slave import gui_init, GUICommand

from mfp.request_pipe import RequestPipe, Request
from mfp import Bang 
from patch import Patch

from singleton import Singleton

from rpc_wrapper import RPCWrapper, rpcwrap
from rpc_worker import RPCWorker

class MFPCommand(RPCWrapper):
	@rpcwrap
	def create(objtype, initargs):
		obj = MFPAPP().create(objtype, initargs)
		MFPAPP().patch.add(obj)
		return obj.obj_id

	@rpcwrap
	def connect(obj_1_id, obj_1_port, obj_2_id, obj_2_port):
		obj_1 = MFPAPP().recall(obj_1_id)
		obj_2 = MFPAPP().recall(obj_2_id)
		r = obj_1.connect(obj_1_port, obj_2, obj_2_port)	
		return r

	@rpcwrap
	def disconnect(obj_1_id, obj_1_port, obj_2_id, obj_2_port):
		obj_1 = MFPAPP().recall(obj_1_id)
		obj_2 = MFPAPP().recall(obj_2_id)

		r = obj_1.disconnect(obj_1_port, obj_2, obj_2_port)
		return r	

	@rpcwrap
	def send_bang(obj_id, port):
		obj = MFPAPP().recall(obj_id)
		obj.send(Bang, port)
		return True

	@rpcwrap
	def delete(obj_id):
		obj = MFPAPP().recall(obj_id)
		print "MFPApp: got delete req for", obj
		obj.delete()

	@rpcwrap
	def gui_params(obj_id, params):
		obj = MFPAPP().recall(args.get('obj_id'))
		obj.gui_params = params


class MFPApp (object):
	__metaclass__ = Singleton
	no_gui = False
	no_dsp = False

	def __init__(self):
		self.dsp_process = None
		self.gui_process = None
		self.gui_cmd = None

		# processor class registry 
		self.registry = {} 
		
		# objects we have given IDs to 
		self.objects = {}
		self.next_obj_id = 0 
	
		self.patch = None	

	def setup(self):
		# dsp and gui processes
		self.dsp_process = RPCWorker("mfp_dsp", dsp_init)
		self.dsp_process.serve(DSPObject)
		
		if not MFPApp.no_gui:
			self.gui_process = RPCWorker("mfp_gui", gui_init)
			self.gui_process.serve(GUICommand)
			self.gui_cmd = GUICommand()

		# while we only have 1 patch, this is it
		self.patch = Patch()

	def remember(self, obj):
		oi = self.next_obj_id
		self.next_obj_id += 1
		self.objects[oi] = obj
		obj.obj_id = oi

		return oi

	def recall(self, obj_id):
		return self.objects.get(obj_id)

	def register(self, name, ctor):
		self.registry[name] = ctor 

	def create(self, name, args=''):
		ctor = self.registry.get(name)
		if ctor is None:
			return None
		else:
			obj = ctor(name, args)
			return obj

	def configure_gui(self, obj, params):
		msg = dict(cmd='configure')
		args = params.get('gui_params')
		# FIXME finish this

	def finish(self):
		if self.dsp_process:
			self.dsp_process.finish()
		if self.gui_process:
			self.gui_process.finish()

def main():
	import builtins 
	import code 

	m = MFPApp()
	builtins.register()
	m.setup()

	def save(fn):
		m.patch.save_file(fn)

	def load(fn):
		m.patch.load_file(fn)

	code.interact(local=locals())

