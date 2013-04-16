#! /usr/bin/env python
'''
patch_json.py
Methods to save and load JSON patch data

Copyright (c) 2012 Bill Gribble <grib@billgribble.com>
'''

import simplejson as json
from .patch import Patch
from .utils import extends
from .bang import BangType, UninitType, Bang, Uninit
from . import log 

class ExtendedEncoder (json.JSONEncoder):
    TYPES = { 'BangType': BangType, 'UninitType': UninitType }

    def default(self, obj):
        if isinstance(obj, tuple(ExtendedEncoder.TYPES.values())):
            key = "__%s__" % obj.__class__.__name__
            return {key: obj.__dict__ }
        else:
            return json.JSONEncoder.default(self, obj)


def extended_decoder_hook (saved):
    if (isinstance(saved, dict) and len(saved.keys()) == 1):
        tname, tdict = saved.items()[0]
        key = tname.strip("_")
        if key == "BangType":
            return Bang
        elif key == "UninitType":
            return Uninit
        else: 
            ctor = ExtendedEncoder.TYPES.get(key)
            if ctor:
                return ctor.load(tdict)
    return saved 


@extends(Patch)
def json_deserialize(self, json_data):
    from .scope import NaiveScope

    f = json.loads(json_data, object_hook=extended_decoder_hook)
    self.init_type = f.get('type')

    # don't swap Patch gui_params if this isn't a top-level patch
    if self.patch is None:
        self.gui_params = f.get('gui_params', {})
        self.gui_params['top_level'] = True
    else:
        # pick out a few things that we need 
        gp = f.get('gui_params', {})
        if 'num_inlets' in gp:
            self.gui_params['num_inlets'] = gp['num_inlets']
        if 'num_outlets' in gp:
            self.gui_params['num_outlets'] = gp['num_outlets']
        self.gui_params['top_level'] = False 

    # reset params that need it 
    self.gui_params["obj_id"] = self.obj_id 
    self.gui_params["name"] = self.name  

    # clear old objects
    for o in self.objects.values():
        o.delete()
    self.objects = {}
    self.scopes = {}
    self.inlet_objects = []
    self.outlet_objects = []
    self.dispatch_objects = [] 

    # create new objects
    # dumb_scope will allow multiple objects with a name, we will resolve when
    # reloading scopes 
    dumb_scope = NaiveScope()
    idmap = self.json_unpack_objects(f, dumb_scope)

    # load new scopes
    scopes = f.get("scopes", {})
    for scopename, bindings in scopes.items():
        s = self.add_scope(scopename)
        for name, oid in bindings.items():
            if name == "self":
                continue

            obj = idmap.get(oid)
            if obj is None:
                log.debug("Error in patch (object %d not found), continuing anyway" % oid)
            else:
                dumb_scope.unbind(obj.name)
                self.bind(name, s, obj)
                obj.scope = s

    self.default_scope = self.scopes.get('__patch__') or self.add_scope("__patch__")
    self.default_scope.bind("self", self)

    # failsafe -- add un-scoped objects to default scope
    for oid, obj in self.objects.items():
        if obj.scope is dumb_scope:
            dumb_scope.unbind(obj.name)
            self.bind(obj.name, self.default_scope, obj)
            obj.scope = self.default_scope

    # make connections
    self.json_unpack_connections(f, idmap)

    inlets = len(self.inlet_objects)
    if not inlets:
        inlets = 1
    self.resize(inlets, len(self.outlet_objects))

@extends(Patch)
def json_unpack_connections(self, data, idmap):
    from main import MFPApp
    for oid, prms in data.get('objects', {}).items():
        oid = int(oid)
        conn = prms.get("connections", [])
        srcobj = idmap.get(oid)
        for outlet in range(0, len(conn)):
            connlist = conn[outlet]
            for c in connlist:
                dstobj = idmap.get(c[0])
                inlet = c[1]
                if dstobj is None:
                    print "Deserializing problem: can't make connection to", c[0]
                    print prms 
                else: 
                    srcobj.connect(outlet, dstobj, inlet)
                    if srcobj.gui_created:
                        MFPApp().gui_command.connect(srcobj.obj_id, outlet, 
                                                     dstobj.obj_id, inlet)

@extends(Patch)
def json_unpack_objects(self, data, scope):
    from main import MFPApp
    idmap = {}
    idlist = data.get('objects').keys()
    idlist.sort(key=lambda x: int(x))
    for oid in idlist:
        prms = data.get('objects')[oid]

        otype = prms.get('type')
        oargs = prms.get('initargs')
        oname = prms.get('name')

        newobj = MFPApp().create(otype, oargs, self, scope, oname)
        newobj.patch = self
        newobj.load(prms)

        if self.gui_created:
            newobj.create_gui()

        idmap[int(oid)] = newobj

    return idmap

@extends(Patch)
def json_serialize(self):
    f = {}
    f['type'] = self.init_type
    f['gui_params'] = self.gui_params

    allobj = {}
    keys = self.objects.keys()
    keys.sort()
    for oid in keys:
        o = self.objects.get(oid)
        if not o.save_to_patch:
            continue
        oinfo = o.save()
        allobj[oid] = oinfo

    f['objects'] = allobj

    scopes = {}
    for scopename, scope in self.scopes.items():
        bindings = {}
        for objname, obj in scope.bindings.items():
            if not obj.save_to_patch:
                continue
            bindings[objname] = obj.obj_id

        scopes[scopename] = bindings

    f['scopes'] = scopes
    return json.dumps(f, indent=4, cls=ExtendedEncoder)
