#! /usr/bin/env python
'''
gui_app.py
GTK/clutter gui for MFP -- main thread

Copyright (c) 2010 Bill Gribble <grib@billgribble.com>
'''

import asyncio
import inspect
import threading
import argparse
import sys
from datetime import datetime

from carp.channel import UnixSocketChannel
from carp.host import Host

from mfp import log

from .singleton import Singleton
from .mfp_command import MFPCommand
from .gui_command import GUICommand


def clutter_do(func):
    def wrapped(*args, **kwargs):
        from mfp.gui_main import MFPGUI
        MFPGUI().clutter_do(lambda: func(*args, **kwargs))

    return wrapped


class MFPGUI (Singleton):
    def __init__(self, mfp_proxy):
        self.call_stats = {}
        self.objects = {}
        self.mfp = mfp_proxy
        self.appwin = None
        self.debug = False
        self.asyncio_loop = asyncio.get_event_loop()
        self.asyncio_thread = threading.get_ident()

        self.style_defaults = {
            'font-face': 'Cantarell,Sans',
            'font-size': 16,
            'canvas-color': 'default-canvas-color',
            'stroke-color': 'default-stroke-color',
            'fill-color': 'default-fill-color',
            'text-color': 'default-text-color',
            'stroke-color:selected': 'default-stroke-color-selected',
            'fill-color:selected': 'default-fill-color-selected',
            'text-color:selected': 'default-text-color-selected',
            'text-cursor-color': 'default-text-cursor-color'
        }

        self.clutter_thread = threading.Thread(target=self.clutter_proc)
        self.clutter_thread.start()

    def remember(self, obj):
        self.objects[obj.obj_id] = obj

    def recall(self, obj_id):
        return self.objects.get(obj_id)

    def async_task(self, call_result, wait=False):
        if inspect.isawaitable(call_result):
            current_thread = threading.get_ident()
            if current_thread == self.asyncio_thread:
                task = asyncio.create_task(call_result)
            else:
                task = asyncio.run_coroutine_threadsafe(call_result, self.asyncio_loop)
                if wait:
                    return task.result()
            return task
        else:
            return call_result

    def _callback_wrapper(self, thunk):
        try:
            return thunk()
        except Exception as e:
            log.debug("Exception in GUI operation:", e)
            log.debug_traceback()
            return False

    def clutter_do_later(self, delay, thunk):
        from gi.repository import GObject
        count = self.call_stats.get("clutter_later", 0) + 1
        self.call_stats['clutter_later'] = count
        GObject.timeout_add(int(delay), self._callback_wrapper, thunk)

    def clutter_do(self, thunk):
        from gi.repository import GObject
        count = self.call_stats.get("clutter_now", 0) + 1
        self.call_stats['clutter_now'] = count
        GObject.idle_add(self._callback_wrapper, thunk, priority=GObject.PRIORITY_DEFAULT)

    def clutter_proc(self):
        try:
            from gi.repository import GObject, Gtk, GtkClutter

            # explicit init seems to avoid strange thread sync/blocking issues
            GObject.threads_init()
            GtkClutter.init([])

            # create main window
            from mfp.gui.patch_window import PatchWindow
            self.appwin = PatchWindow()

        except Exception:
            log.error("Fatal error during GUI startup")
            log.debug_traceback()
            return

        try:
            # direct logging to GUI log console
            Gtk.main()
        except Exception as e:
            log.error("Caught GUI exception:", e)
            log.debug_traceback()
            sys.stdout.flush()

    def finish(self):
        from gi.repository import Gtk
        if self.debug:
            import yappi
            yappi.stop()
            yappi.convert2pstats(yappi.get_func_stats()).dump_stats(
                'mfp-gui-funcstats.pstats')

        log.log_func = None
        if self.appwin:
            self.appwin.quit()
            self.appwin = None
        Gtk.main_quit()


def setup_default_colors():
    from .gui.colordb import ColorDB
    ColorDB().insert('default-canvas-color',
                     ColorDB().find(0xf7, 0xf9, 0xf9, 0))
    ColorDB().insert('default-stroke-color',
                     ColorDB().find(0x1f, 0x30, 0x2e, 0xff))
    ColorDB().insert('default-stroke-color-selected',
                     ColorDB().find(0x00, 0x7f, 0xff, 0xff))
    ColorDB().insert('default-fill-color',
                     ColorDB().find(0xd4, 0xdc, 0xff, 0xff))
    ColorDB().insert('default-fill-color-selected',
                     ColorDB().find(0xe4, 0xec, 0xff, 0xff))
    ColorDB().insert('default-alt-fill-color',
                     ColorDB().find(0x7d, 0x83, 0xff, 0xff))
    ColorDB().insert('default-text-color',
                     ColorDB().find(0x1f, 0x30, 0x2e, 0xff))
    ColorDB().insert('default-light-text-color',
                     ColorDB().find(0xf7, 0xf9, 0xf9, 0xff))
    ColorDB().insert('default-text-color-selected',
                     ColorDB().find(0x00, 0x7f, 0xff, 0xff))
    ColorDB().insert('default-edit-badge-color',
                     ColorDB().find(0x74, 0x4b, 0x94, 0xff))
    ColorDB().insert('default-learn-badge-color',
                     ColorDB().find(0x19, 0xff, 0x90, 0xff))
    ColorDB().insert('default-error-badge-color',
                     ColorDB().find(0xb7, 0x21, 0x21, 0xff))
    ColorDB().insert('default-text-cursor-color',
                     ColorDB().find(0x0, 0x0, 0x0, 0x40))
    ColorDB().insert('transparent',
                     ColorDB().find(0x00, 0x00, 0x00, 0x00))


async def loggo(*args, **kwargs):
    print(f"[loggo] {args} {kwargs}")


async def main():
    import gi
    gi.require_version('Gtk', '3.0')
    gi.require_version('GtkClutter', '1.0')
    gi.require_version('Clutter', '1.0')

    parser = argparse.ArgumentParser()
    parser.add_argument("-l", "--logstart", default=None,
                        help="Reference time for log messages")
    parser.add_argument("-s", "--socketpath", default="/tmp/mfp_rpcsock",
                        help="Path to Unix-domain socket for RPC")
    parser.add_argument("-d", "--debug", action="store_true",
                        help="Enable debugging behaviors")

    args = vars(parser.parse_args())
    socketpath = args.get("socketpath")
    debug = args.get('debug')

    print("[LOG] DEBUG: GUI process starting")

    channel = UnixSocketChannel(socket_path=socketpath)
    host = Host(
        label="MFP GUI",
    )
    host.on("status", loggo)
    host.on("connect", loggo)
    host.on("message", loggo)
    host.on("exports", loggo)
    host.on("disconnect", loggo)
    host.on("call", loggo)

    await host.connect(channel)

    if args.get("logstart"):
        st = datetime.strptime(args.get("logstart"), "%Y-%m-%dT%H:%M:%S.%f")
        if st:
            log.log_time_base = st

    log.log_module = "gui"
    log.log_func = log.rpclog
    log.log_debug = True

    setup_default_colors()

    MFPCommandFactory = await host.require(MFPCommand)
    mfp_connection = await MFPCommandFactory()

    gui = MFPGUI(mfp_connection)
    gui.debug = debug

    if debug:
        import yappi
        yappi.start()

    await host.export(GUICommand)
    await asyncio.wait(host.tasks)


def main_sync_wrapper():
    import asyncio
    asyncio.run(main())

