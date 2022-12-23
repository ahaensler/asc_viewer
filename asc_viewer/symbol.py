import wx
import math
from asc_viewer.bounded_canvas import BoundedCanvas

window_types = {
    "0": "InstName",
    "3": "Value",
    "39": "SpiceLine",
    "123": "Value2",
    "?": "SpiceLine2",
}


class Pin:
    """An LtSpice symbol pin as defined in an .asy file"""

    def __init__(self):
        self.name = None
        self.order = None
        self.align = None
        self.x = None
        self.y = None
        self.text_x = None
        self.text_y = None

    def rect(self):
        return (self.x - 5, self.y - 5, 10, 10)


class Symbol(BoundedCanvas):
    """An LtSpice symbol as defined in an .asy file"""

    def __init__(self, parent, filename):
        """Arguments:
        parent -- A wx class that provides a graphics context, i.e., AscViewer
        filename -- the full filename of the .asy file
        """
        super().__init__()
        self.filename = filename
        self.loaded = False
        self.lines = []
        self.circles = []
        self.arcs = []
        self.windows = {}
        self.pins = []
        self.circles = []
        self.texts = []
        self.rectangles = []
        self.attrs = {}
        self.parent = parent

    def load(self):
        """Loads the symbol from file."""
        if self.loaded:
            return
        dc = wx.ClientDC(self.parent)
        gc = wx.GraphicsContext.Create(dc)

        f = open(self.filename, encoding="iso-8859-1")
        self.reset_extent()
        last_pin = None
        for line in f:
            line = line.strip()
            if len(line) == 0:
                continue
            words = line.split(" ")
            if words[0] == "SymbolType":
                self.type = words[1]
            elif words[0] == "LINE":
                line = dict(style=words[1], coords=[int(x) for x in words[2:]])
                self.check_extent(
                    [line["coords"][0], line["coords"][2]],
                    [line["coords"][1], line["coords"][3]],
                )
                self.lines.append(line)
            elif words[0] == "CIRCLE":
                c = [int(x) for x in words[2:]]
                self.check_extent([c[0], c[2]], [c[1], c[3]])
                c = (
                    min(c[0], c[2]),
                    min(c[1], c[3]),
                    abs(c[2] - c[0]),
                    abs(c[3] - c[1]),
                )
                c = dict(style=words[1], coords=c)
                self.circles.append(c)
            elif words[0] == "ARC":
                c = [int(x) for x in words[2:]]
                self.check_extent([c[0], c[2]], [c[1], c[3]])
                x1, y1, w, h = (
                    min(c[0], c[2]),
                    min(c[1], c[3]),
                    abs(c[2] - c[0]),
                    abs(c[3] - c[1]),
                )
                cx, cy, rx, ry = (x1 + w / 2, y1 + h / 2, w / 2, h / 2)
                angle1 = int(math.atan2(c[5] - cy, c[4] - cx) * 180 / math.pi)
                angle2 = int(math.atan2(c[7] - cy, c[6] - cx) * 180 / math.pi)
                if angle2 > angle1:
                    angle2 -= 360
                coords = [cx, cy, rx, ry, angle1, angle2]
                c = dict(style=words[1], coords=coords)
                self.arcs.append(c)
            elif words[0] == "TEXT":
                x = int(words[1])
                y = int(words[2])
                align = words[3]
                size = int(words[4])
                text = " ".join(words[5:])
                self.check_extent(x - 15, y - 15)

                x, y, y2 = self.parent.align_text(
                    x, y, text, align, size, 0, gc.CreateMatrix()
                )
                t = dict(x=x, y=y, size=size, text=text)
                self.texts.append(t)
            elif words[0] == "WINDOW":
                x = int(words[2])
                y = int(words[3])
                type = window_types[words[1]]
                window = dict(type=type, x=x, y=y, align=words[4], size=int(words[5]))
                self.check_extent(x - 15, y - 15)
                self.windows[type] = window
            elif words[0] == "RECTANGLE":
                c = [int(x) for x in words[2:]]
                self.check_extent([c[0], c[2]], [c[1], c[3]])
                c = [
                    min(c[0], c[2]),
                    min(c[1], c[3]),
                    abs(c[2] - c[0]),
                    abs(c[3] - c[1]),
                ]
                rect = dict(style=words[1], coords=c)
                self.rectangles.append(rect)
            elif words[0] == "PIN":
                last_pin = Pin()
                last_pin.x = int(words[1])
                last_pin.y = int(words[2])
                map_align = {
                    "left": "Right",
                    "right": "Left",
                    "top": "Bottom",
                    "bottom": "Top",
                    "none": "",
                }
                last_pin.align = words[3].capitalize()
                offset = int(words[4])
                last_pin.text_x = last_pin.x
                last_pin.text_y = last_pin.y
                if last_pin.align == "Top":
                    last_pin.text_y = last_pin.y + offset
                elif last_pin.align == "Bottom":
                    last_pin.text_y = last_pin.y - offset
                elif last_pin.align == "Left":
                    last_pin.text_x = last_pin.x + offset
                elif last_pin.align == "Right":
                    last_pin.text_x = last_pin.x - offset
                self.check_extent(last_pin.x, last_pin.y)
                self.pins.append(last_pin)
                # self.rectangles.append(dict(style='Normal', coords=c))
            elif words[0] == "PINATTR":
                assert last_pin
                key, value = words[1], words[2]
                if key == "PinName":
                    last_pin.name = value
                elif key == "SpiceOrder":
                    last_pin.order = int(value)
                else:
                    assert f"Unknown pin attribute {key}"
            elif words[0] == "SYMATTR":
                self.attrs[words[1]] = " ".join(words[2:])
        self.loaded = True

        # assign zero-based pin indices
        self.pins.sort(key=lambda pin: pin.order)
        for i, pin in enumerate(self.pins):
            pin.index = i

        # create the path that draws the symbol
        path = self.parent.gc.CreatePath()
        for line in self.lines:
            c = line["coords"]
            path.MoveToPoint(c[0], c[1])
            path.AddLineToPoint(c[2], c[3])
        for circle in self.circles:
            path.AddEllipse(*circle["coords"])
        for arc in self.arcs:
            c = arc["coords"]
            path.MoveToPoint(
                c[0] + c[2] * math.cos(c[4] / 180 * math.pi),
                c[1] + c[3] * math.sin(c[4] / 180 * math.pi),
            )
            for a in range(c[4], c[5], -10):
                path.AddLineToPoint(
                    c[0] + c[2] * math.cos(a / 180 * math.pi),
                    c[1] + c[3] * math.sin(a / 180 * math.pi),
                )
        self.path = path

    def paint(self, gc, old_m, rotation, attrs, windows):
        """Paints the symbol in its instantiated representation as part of a larger schematic.
        Arguments:

        gc -- A wx graphics context.
        old_m -- A matrix to be used for drawing the symbol, rotation is supplied separately.
        rotation -- Symbol rotation in degrees.
        attrs -- Attributes of the symbol instance.
        windows -- Windows supplied by the symbold instance.
        """
        gc.StrokePath(self.path)
        for text in self.texts:
            gc.SetFont(self.parent.fonts[text["size"]])
            gc.DrawText(text["text"], text["x"], text["y"])
        for rect in self.rectangles:
            gc.DrawRectangle(*rect["coords"])

        combined_windows = self.windows | windows

        m = gc.GetTransform()
        gc.SetTransform(old_m)  # un-rotated transform
        # get text rotation matrix
        text_m = gc.CreateMatrix(*old_m.Get())
        text_m.Invert()
        text_m.Concat(m)

        for pin in self.pins:
            if not pin.name:
                continue  # unnamed pin
            if not pin.align or pin.align == "None":
                continue  # hidden pin
            x, y, y2 = self.parent.align_text(
                pin.text_x, pin.text_y, pin.name, pin.align, 2, 0, text_m
            )  # pin names have a fixed size of 1.5
            gc.DrawText(pin.name, x, y, angle=0)

        for type, window in combined_windows.items():
            gc.SetFont(self.parent.fonts[window["size"]])
            text = attrs.get(type)
            if text is None:
                text = self.attrs.get(type, "NA")  # use default attr from symbol
            x, y, y2 = self.parent.align_text(
                window["x"],
                window["y"],
                text,
                window["align"],
                window["size"],
                rotation,
                text_m,
            )
            angle = 90 if window["align"][0] == "V" else 0
            if rotation == 270 or rotation == 90:
                angle -= 90
            if angle:
                y = y2
            gc.DrawText(text, x, y, angle=angle / 180 * math.pi)
