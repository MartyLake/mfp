#! /usr/bin/env python2.6
'''
rpc_wrapper.py:
Simple RPC-able class wrapper working with RPCHost

Copyright (c) 2010-2014 Bill Gribble <grib@billgribble.com>
'''

from request import Request
from mfp import log
from mfp.utils import profile 

def rpcwrap(worker_proc):
    def inner(self, *args, **kwargs):
        if self.local:
            return worker_proc(self, *args, **kwargs)
        else:
            rpcdata = dict(func=worker_proc.__name__, 
                           rpcid=self.rpcid, args=args, kwargs=kwargs)
            return self.call_remotely(rpcdata)
    return inner


class RPCMetaclass(type):
    def __init__(klass, name, bases, xdict):
        type.__init__(klass, name, bases, xdict)
        klass.register(name)


class RPCWrapper (object):
    __metaclass__ = RPCMetaclass

    NO_CLASS = -1
    NO_METHOD = -2
    METHOD_FAILED = -3
    METHOD_OK = -4

    class ClassNotFound(Exception):
        pass

    class MethodNotFound(Exception):
        pass

    class MethodFailed(Exception):
        def __init__(self, local, tb):
            self.traceback = tb
            if local:
                log.debug(tb)
            Exception.__init__(self)

    _rpcid_seq = 0
    rpcobj = {}
    rpctype = {}
    local = False
    rpchost = None
    publishers = [] 
    call_stats = {} 

    def __init__(self, *args, **kwargs):
        self.rpcid = None
        self.peer_id = None 
        
        if self.local:
            self.rpcid = RPCWrapper._rpcid_seq
            RPCWrapper._rpcid_seq += 1
            RPCWrapper.rpcobj[self.rpcid] = self
        else:
            r = Request("create", dict(type=type(self).__name__, 
                                       args=args, kwargs=kwargs))
            self.peer_id = kwargs.get("peer_id")
            if self.peer_id is None:
                if self.publishers: 
                    self.peer_id = self.publishers[0]
                else:
                    self.peer_id = 0

            self.rpchost.put(r, self.peer_id)
            self.rpchost.wait(r)
            if r.response[0] == RPCWrapper.NO_CLASS:
                raise RPCWrapper.ClassNotFound()

            self.rpcid = r.response[0]

    def call_remotely(self, rpcdata):
        r = Request("call", rpcdata)
        self.rpchost.put(r, self.peer_id)
        self.rpchost.wait(r)

        status, retval = r.response 
        if status == RPCWrapper.METHOD_OK:
            return retval 
        elif r.response == RPCWrapper.METHOD_FAILED:
            raise RPCWrapper.MethodFailed(False, retval)

    def call_locally(self, rpcdata):
        count = self.call_stats.get(rpcdata.get('func'), 0)
        self.call_stats[rpcdata.get('func')] = count + 1 

        methname = rpcdata.get('func')
        args = rpcdata.get('args')
        kwargs = rpcdata.get('kwargs')

        meth = getattr(self, methname)
        if meth:
            try:
                rv = meth(*args, **kwargs)
                return rv
            except Exception, e:
                import traceback
                raise RPCWrapper.MethodFailed(True, traceback.format_exc())
        else:
            raise RPCWrapper.MethodNotFound()

    @classmethod
    def register(klass, name):
        klass.rpctype[name] = klass

    @classmethod
    def handle(klass, req, peer_id):
        method = req.method 
        rpcdata = req.params
        rpcid = rpcdata.get('rpcid')
        args = rpcdata.get('args')
        kwargs = rpcdata.get('kwargs')

        req.state = Request.RESPONSE_DONE

        if method == 'create':
            factory = RPCWrapper.rpctype.get(rpcdata.get('type'))
            if factory:
                obj = factory(*args, **kwargs)
                req.response = (obj.rpcid, None)
            else:
                req.response = (RPCWrapper.NO_CLASS, None)
        elif method == 'delete':
            del RPCWrapper.objects[rpcid]
            req.response = (True, None)
        elif method == 'call':
            obj = RPCWrapper.rpcobj.get(rpcid)
            try:
                retval = obj.call_locally(rpcdata)
                req.response = (RPCWrapper.METHOD_OK, retval)
            except RPCWrapper.MethodNotFound, e:
                req.response = (RPCWrapper.NO_METHOD, None)
            except RPCWrapper.MethodFailed, e:
                req.response = (RPCWrapper.METHOD_FAILED, e.traceback)
            except Exception, e:
                import traceback
                einfo = "Method call failed rpcid=%s node=%s\nobj=%s data=%s\n" % (rpcid, self.peer_id, obj, rpcdata)
                req.response = (RPCWrapper.METHOD_FAILED, einfo + traceback.format_exc())
        elif method == 'publish': 
            for clsname in req.params.get("classes"): 
                cls = RPCWrapper.rpctype.get(clsname)
                if cls is not None:
                    cls.publishers.append(peer_id)
            req.response = (True, None) 

        elif method == "peer_exit": 
            # remove this peer as a publisher for any classes
            for clsname, cls in RPCWrapper.rpctype.items():
                if peer_id in cls.publishers:
                    cls.publishers.remove(peer_id)
            klass.rpchost.unmanage(peer_id) 

            req.request_id = None
        else:
            print "rpc_wrapper: WARNING: no handler for method '%s'" % method

        req.method = None 
        req.params = None 

