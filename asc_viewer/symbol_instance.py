import wx
import math


class Pin:
    def __init__(self, symbol_pin):
        self.symbol_pin = symbol_pin
        self.x = None
        self.y = None


class SymbolInstance:
    def __init__(self, parent, name, x, y, mirror, rotation):
        self.prefix = parent.instance_name
        self.name = name
        self.x = x
        self.y = y
        self.rotation = rotation
        self.mirror = mirror
        self.attrs = {}
        self.symbol = None
        self.pins = []
        self.windows = {}

        self.matrix = parent.gc.CreateMatrix()
        if self.mirror:
            a, b, c, d, x, y = self.matrix.Get()
            self.matrix.Set(a=-a)
        self.matrix.Rotate(self.rotation / 180 * math.pi)

        self.user_data = None  # links arbitrary user data to this instance

        self.black_pen = wx.Pen(wx.Colour(0, 0, 0), width=2, style=wx.PENSTYLE_SOLID)
        self.red_pen = wx.Pen(wx.Colour(255, 0, 0), width=2, style=wx.PENSTYLE_SOLID)
        self.blue_pen = wx.Pen(wx.Colour(0, 255, 0), width=2, style=wx.PENSTYLE_SOLID)
        self.no_pen = wx.Pen(wx.Colour(0, 0, 0), style=wx.PENSTYLE_TRANSPARENT)
        self.orange_brush = wx.Brush(
            wx.Colour(250, 150, 150), style=wx.BRUSHSTYLE_SOLID
        )
        self.no_brush = wx.Brush(wx.Colour(0, 0, 0), style=wx.BRUSHSTYLE_TRANSPARENT)
        self.user_paint = (
            lambda self, gc, user_data: None
        )  # hook for a user-defined paint function

    def set_symbol(self, symbol):
        self.symbol = symbol
        for symbol_pin in self.symbol.pins:
            pin = Pin(symbol_pin)
            dx, dy = self.matrix.TransformPoint(symbol_pin.x, symbol_pin.y)
            pin.x = self.x + round(
                dx
            )  # rounding is important for pins and wires to line up and connect
            pin.y = self.y + round(dy)
            self.pins.append(pin)

    def get_extent(self):
        # returns the extent of the instance on the canvas
        x0, y0, x1, y1 = self.symbol.get_extent()
        x0, y0 = self.matrix.TransformPoint(x0, y0)
        x1, y1 = self.matrix.TransformPoint(x1, y1)
        x0 += self.x
        x1 += self.x
        y0 += self.y
        y1 += self.y
        # add space to accomodate pen width
        return min(x0, x1) - 2, min(y0, y1) - 2, max(x0, x1) + 2, max(y0, y1) + 2

    def set_user_data(self, user_data):
        self.user_data = user_data

    def set_user_paint_func(self, func):
        self.user_paint = func

    def paint(self, gc):
        old_m = gc.GetTransform()
        gc.Translate(self.x, self.y)
        old_m2 = gc.GetTransform()  # translated to symbol position, but no rotation

        # concat order was inconsistent (https://github.com/wxWidgets/wxWidgets/issues/17670), fixed now
        m2 = gc.CreateMatrix(*old_m2.Get())
        m2.Concat(self.matrix)
        gc.SetTransform(m2)

        if not self.symbol:
            return
        self.user_paint(self, gc, self.user_data)

        self.symbol.paint(gc, old_m2, self.rotation, self.attrs, self.windows)
        gc.SetBrush(self.no_brush)
        gc.SetPen(self.black_pen)
        gc.SetTransform(old_m)
