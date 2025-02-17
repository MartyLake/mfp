#! /usr/bin/env python
'''
button_element.py
A patch element corresponding to a "bang" or "toggle" style button

Copyright (c) 2012 Bill Gribble <grib@billgribble.com>
'''

from abc import ABC, abstractmethod

from mfp.utils import catchall
from .text_widget import TextWidget
from .backend_interfaces import BackendInterface
from .base_element import BaseElement
from .modes.clickable import ClickableControlMode
from .modes.label_edit import LabelEditMode
from ..gui_main import MFPGUI
from ..bang import Bang


class ButtonElementImpl(ABC, BackendInterface):
    @abstractmethod
    def redraw(self):
        pass


class BangButtonElementImpl(ABC, BackendInterface):
    pass


class ToggleButtonElementImpl(ABC, BackendInterface):
    pass


class ToggleIndicatorElementImpl(ABC, BackendInterface):
    pass


class ButtonElement (BaseElement):
    proc_type = "var"

    style_defaults = {
        'porthole_height': 2,
        'porthole_width': 6,
        'porthole_minspace': 8,
        'porthole_border': 3,
        'fill-color:lit': 'default-alt-fill-color',
        'text-color:lit': 'default-light-text-color'
    }

    PORT_TWEAK = 5

    def __init__(self, window, x, y):
        super().__init__(window, x, y)

        self.indicator = False
        self.message = None

        self.label = TextWidget.build(self)
        self.label.set_color(self.get_color('text-color'))
        self.label.set_font_name(self.get_fontspec())
        self.label.signal_listen('text-changed', self.label_changed_cb)
        self.label.set_reactive(False)
        self.label.set_use_markup(True)
        self.label_text = ''

        self.param_list.append('label_text')

        # request update when value changes
        self.update_required = True

    @classmethod
    def get_factory(cls):
        return ButtonElementImpl.get_backend(MFPGUI().appwin.backend_name)

    def center_label(self):
        label_halfwidth = self.label.get_property('width')/2.0
        label_halfheight = self.label.get_property('height')/2.0

        if label_halfwidth > 1:
            nwidth = max(self.width, 2*label_halfwidth + 10)
            nheight = max(self.height, 2*label_halfheight + 10)
            if nwidth != self.width or nheight != self.height:
                self.set_size(nwidth, nheight)

        if self.width and self.height:
            self.label.set_position(self.width/2.0-label_halfwidth,
                                    self.height/2.0-label_halfheight-2)

    @catchall
    def label_changed_cb(self, *args):
        self.center_label()

    def label_edit_start(self):
        return self.label_text

    async def label_edit_finish(self, widget, new_text, aborted=False):
        if not aborted:
            self.label_text = new_text
            self.send_params()
            if self.indicator:
                self.label.set_markup("<b>%s</b>" % self.label_text)
            else:
                self.label.set_markup(self.label_text)

            self.redraw()

    def configure(self, params):
        set_text = False

        if "value" in params:
            self.message = params.get("value")
            self.indicator = self.message
            set_text = True

        if "label_text" in params:
            self.label_text = params.get("label_text", '')
            set_text = True

        if set_text:
            if self.indicator:
                self.label.set_markup("<b>%s</b>" % (self.label_text or ''))
            else:
                self.label.set_markup(self.label_text or '')
            self.center_label()

        super().configure(params)
        self.redraw()

    def select(self):
        BaseElement.select(self)
        self.redraw()

    def unselect(self):
        BaseElement.unselect(self)
        self.redraw()

    async def make_edit_mode(self):
        if self.obj_id is None:
            # create object
            await self.create(self.proc_type, str(self.indicator))

            # complete drawing
            if self.obj_id is None:
                return None
            self.draw_ports()
        self.redraw()

        return LabelEditMode(self.app_window, self, self.label)

    def make_control_mode(self):
        return ClickableControlMode(self.app_window, self, "Button control")


class BangButtonElement (ButtonElement):
    display_type = "button"

    def __init__(self, window, x, y):
        self.message = Bang

        super().__init__(window, x, y)
        self.param_list.extend(['message'])

    @classmethod
    def get_factory(cls):
        return BangButtonElementImpl.get_backend(MFPGUI().appwin.backend_name)

    def clicked(self):
        if self.obj_id is not None:
            if self.message is Bang:
                MFPGUI().async_task(MFPGUI().mfp.send_bang(self.obj_id, 0))
            else:
                MFPGUI().async_task(MFPGUI().mfp.send(self.obj_id, 0, self.message))
        self.indicator = True
        self.redraw()

        return False

    def unclicked(self):
        self.indicator = False
        self.redraw()

        return False

    def configure(self, params):
        if "message" in params:
            self.message = params.get("message")

        super().configure(params)


class ToggleButtonElement (ButtonElement):
    display_type = "toggle"

    def __init__(self, window, x, y):
        super().__init__(window, x, y)
        self.off_message = False
        self.on_message = True

        self.param_list.extend(['on_message', 'off_message'])

    @classmethod
    def get_factory(cls):
        return ToggleButtonElementImpl.get_backend(MFPGUI().appwin.backend_name)

    def clicked(self):
        message = None
        if self.indicator:
            message = self.off_message
            self.indicator = False
        else:
            message = self.on_message
            self.indicator = True

        if self.obj_id is not None:
            MFPGUI().async_task(MFPGUI().mfp.send(self.obj_id, 0, message))
        self.redraw()
        return False

    def configure(self, params):
        if "on_message" in params:
            self.on_message = params.get("on_message")
        if "off_message" in params:
            self.off_message = params.get("off_message")
        ButtonElement.configure(self, params)

    async def create(self, init_type, init_args):
        await super().create(init_type, init_args)
        if self.obj_id:
            await MFPGUI().mfp.set_do_onload(self.obj_id, True)

    def unclicked(self):
        return False


class ToggleIndicatorElement (ButtonElement):
    display_type = "indicator"

    @classmethod
    def get_factory(cls):
        return ToggleIndicatorElementImpl.get_backend(MFPGUI().appwin.backend_name)

    def make_control_mode(self):
        return BaseElement.make_control_mode(self)

    def select(self, *args):
        super().select()
        self.draw_ports()
        self.redraw()

    def unselect(self, *args):
        super().unselect()
        self.hide_ports()
        self.redraw()

    def draw_ports(self):
        if self.selected:
            super().draw_ports()
