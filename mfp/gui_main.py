#! /usr/bin/env python
'''
gui_main.py
Gui for MFP -- main thread

Copyright (c) Bill Gribble <grib@billgribble.com>
'''

# FIXME
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('GtkClutter', '1.0')
gi.require_version('Clutter', '1.0')

import asyncio
import inspect
import threading
import argparse
from datetime import datetime

import gbulb

from carp.channel import UnixSocketChannel
from carp.host import Host
from flopsy import Store

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
    def __init__(self):
        self.call_stats = {}
        self.objects = {}
        self.mfp = None
        self.debug = False
        self.asyncio_tasks = {}
        self.asyncio_task_last_id = 0
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
            'stroke-color:debug': 'default-stroke-color-debug',
            'fill-color:selected': 'default-fill-color-selected',
            'fill-color:debug': 'default-fill-color-debug',
            'text-color:selected': 'default-text-color-selected',
            'text-cursor-color': 'default-text-cursor-color'
        }
        self.appwin = None

    def remember(self, obj):
        self.objects[obj.obj_id] = obj

    def recall(self, obj_id):
        return self.objects.get(obj_id)

    async def _task_wrapper(self, coro, task_id):
        rv = None
        try:
            rv = await coro
        except Exception as e:
            log.error(f"Exception in task: {coro} {e}")
        finally:
            if task_id in self.asyncio_tasks:
                del self.asyncio_tasks[task_id]
        return rv

    def async_task(self, coro):
        if inspect.isawaitable(coro):
            current_thread = threading.get_ident()
            task_id = self.asyncio_task_last_id
            self.asyncio_task_last_id += 1

            if current_thread == self.asyncio_thread:
                task = asyncio.create_task(self._task_wrapper(coro, task_id))
            else:
                task = asyncio.run_coroutine_threadsafe(
                    self._task_wrapper(coro, task_id), self.asyncio_loop
                )
            self.asyncio_tasks[task_id] = task
            return task
        else:
            return coro

    def _callback_wrapper(self, thunk):
        try:
            return thunk()
        except Exception as e:
            log.debug("Exception in GUI operation:", e)
            log.debug_traceback()
            return False

    # FIXME -- yooooooooo
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
    ColorDB().insert('default-stroke-color-debug',
                     ColorDB().find(0x3f, 0xbf, 0x7f, 0xff))
    ColorDB().insert('default-fill-color',
                     ColorDB().find(0xd4, 0xdc, 0xff, 0xff))
    ColorDB().insert('default-fill-color-selected',
                     ColorDB().find(0xe4, 0xec, 0xff, 0xff))
    ColorDB().insert('default-fill-color-debug',
                     ColorDB().find(0xcd, 0xf8, 0xec, 0xff))
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


async def main():
    from mfp.gui.patch_window import AppWindow
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
    await host.connect(channel)

    if args.get("logstart"):
        st = datetime.strptime(args.get("logstart"), "%Y-%m-%dT%H:%M:%S.%f")
        if st:
            log.log_time_base = st

    log.log_module = "gui"
    log.log_func = log.rpclog
    log.log_debug = True

    setup_default_colors()

    # set up Flopsy store manager
    Store.setup_asyncio()

    MFPCommandFactory = await host.require(MFPCommand)
    mfp_connection = await MFPCommandFactory()

    print("[LOG] DEBUG: About to create MFPGUI")
    from mfp.gui.backends import clutter  # noqa
    AppWindow.backend_name = "clutter"

    gui = MFPGUI()
    gui.mfp = mfp_connection
    gui.debug = debug
    gui.appwin = AppWindow()

    print("[LOG] DEBUG: created MFPGUI")
    if debug:
        import yappi
        yappi.start()

    await host.export(GUICommand)
    print("[LOG] DEBUG: published GUICommand")
    try:
        await asyncio.wait(host.tasks)
    except asyncio.exceptions.CancelledError:
        pass
    print("[LOG] DEBUG: GUI process terminating")


async def main_error_wrapper():
    main_task = asyncio.create_task(main())
    try:
        await main_task
    except Exception as e:
        import traceback
        print(f"[LOG] ERROR: GUI process failed with {e}")
        tb = traceback.format_exc()
        print(f"[LOG] ERROR: {tb}")
    ex = main_task.exception()
    print(f"[LOG] ERROR: main task exited {ex}")

def main_sync_wrapper():
    import asyncio

    gbulb.install(gtk=True)
    asyncio.run(main_error_wrapper())
