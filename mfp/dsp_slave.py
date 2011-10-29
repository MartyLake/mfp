#! /usr/bin/env python2.6 
'''
dsp_slave.py
Python main loop for DSP subprocess 

Copyright (c) 2010 Bill Gribble <grib@billgribble.com>
'''
import mfpdsp
from rpc_wrapper import RPCWrapper, rpcwrap

class DSPObject(RPCWrapper):
	objects = {}
	def __init__(self, obj_id, name, inlets, outlets, params={}):
		self.obj_id = obj_id 
		RPCWrapper.__init__(self, obj_id, name, inlets, outlets, params)
		if self.local:
			self.c_obj = mfpdsp.proc_create(name, inlets, outlets, params)
			DSPObject.objects[self.obj_id] = self.c_obj

	@rpcwrap
	def delete(self):
		return mfpdsp.proc_destroy(self.c_obj)

	@rpcwrap
	def getparam(self, param):
		return mfpdsp.proc_getparam(self.c_obj, param)
	
	@rpcwrap
	def setparam(self, param, value):
		return mfpdsp.proc_setparam(self.c_obj, param, value)

	@rpcwrap
	def connect(self, outlet, target, inlet):
		return mfpdsp.proc_connect(self.c_obj, outlet, DSPObject.objects.get(target), 
							       inlet)

	@rpcwrap
	def disconnect(self, outlet, target, inlet):
		return mfpdsp.proc_disconnect(self.c_obj, outlet, DSPObject.objects.get(target), 
								      inlet)

def dsp_init(pipe):
	from main import MFPCommand
	import threading 

	RPCWrapper.node_id = "JACK DSP"
	DSPObject.pipe = pipe
	DSPObject.local = True
	MFPCommand.local = False

	pipe.on_finish(dsp_finish)

	# start JACK thread 
	mfpdsp.dsp_startup(1, 1)
	mfpdsp.dsp_enable()

	# start response thread 
	rt = threading.Thread(target=dsp_response)
	rt.start()

ttq = False
def dsp_response():
	from main import MFPCommand
	global ttq
	mfp = MFPCommand()
	while not ttq:
		messages = mfpdsp.dsp_response_wait()
		if messages is None:
			print "(no messages)"
			continue
		for m in messages:
			print "Received dsp message", m
			# mfp.send_dsp_message(m)

def dsp_finish():
	global ttq
	ttq = True
	mfpdsp.dsp_shutdown()


