#! /usr/bin/env python2.7
'''
osc.py: OSC server for MFP

Copyright (c) 2012 Bill Gribble <grib@billgribble.com>
'''

from quittable_thread import QuittableThread
import liblo
from mfp import log


class MFPOscManager(QuittableThread):
    def __init__(self, port):
        self.port = port
        self.server = None
        self.default_handlers = [] 

        try:
            self.server = liblo.Server(self.port)
        except Exception, err:
            print str(err)

        self.server.add_method(None, None, self.default)
        QuittableThread.__init__(self)

    def add_method(self, path, args, handler, data=None):
        if data is not None:
            self.server.add_method(path, args, handler, data)
        else:
            self.server.add_method(path, args, handler)

    def del_method(self, path, args):
        self.server.del_method(path, args)

    def default(self, path, args, types, src):
        print "Got default OSC data:", path, args, types, src
        for handler, data in self.default_handlers: 
            handler(path, args, types, src, data)
        return True

    def add_default(self, handler, data=None):
        self.default_handlers.append((handler, data))

    def del_default(self, handler, data=None):
        self.default_handlers = [ h for h in self.default_handlers 
                                 if h != (handler, data) ]

    def send(self, target, path, data):
        m = liblo.Message(path)
        m.add(data)
        self.server.send(target, m)

    def run(self):
        while not self.join_req and self.server is not None:
            self.server.recv(100)
        log.debug("OSC server exiting")
