import wx
import math
from asc_viewer.viewport import Viewport
from asc_viewer.symbol_instance import SymbolInstance
import glob, os
import rtreelib as rt
from asc_viewer.symbol import Symbol, window_types
from asc_viewer.bounded_canvas import BoundedCanvas

font_size_factors = [0.625, 1, 1.5, 2, 2.5, 3.5, 5, 7]


class Net:
    """A net as used in LtSpice."""

    def __init__(self, name):
        self.name = name
        self.connections = []  # a list of (SymbolInstance, InstancePin, PinName) tuples
        self.type = None  # denotes spur type as string
        self.wires = set()


class Connection:
    """A connection between a net and an instance."""

    def __init__(self, instance, pin, pin_name):
        self.instance = instance
        self.pin = pin
        self.pin_name = pin_name


class WirePoint:
    """An endpoint of a wire."""

    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.direction = (
            None  # direction for orientation of symbols attached to endpoints
        )
        self.wires = []
        self.net = None  # is set after DFS connects wires to nets


class Wire:
    """A wire as drawn in LtSpice."""

    def __init__(self, x0, y0, x1, y1):
        self.x0 = x0
        self.y0 = y0
        self.x1 = x1
        self.y1 = y1
        self.net = None


class AscCanvas(BoundedCanvas, Viewport):
    """Displays an LtSpice schematic.

    Arguments:
    parent -- the parent window
    symbol_paths -- a list of path names where symbols are stored
    instance_name -- the instance name of this schematic, this is only useful it the schematic is an instantiated subcircuit
    """

    def __init__(self, parent, symbol_paths, instance_name=""):
        super().__init__(parent)

        self.instance_name = instance_name
        self.symbols = {}
        self.filename = None
        self.load_symbols(symbol_paths)

        # create some graphics primitives for later use
        self.fonts = []
        self.dc = wx.ClientDC(self)
        self.gc = wx.GraphicsContext.Create(self.dc)
        self.black_pen = wx.Pen(wx.Colour(0, 0, 0), width=2, style=wx.PENSTYLE_SOLID)
        self.red_pen = wx.Pen(wx.Colour(255, 0, 0), width=2, style=wx.PENSTYLE_SOLID)
        for i in range(4):
            font = self.create_font(font_size_factors[i])
            self.fonts.append(font)
        font_size = 0.8
        self.black_font = self.create_font(font_size, wx.BLACK)
        self.blue_font = self.create_font(font_size, wx.BLUE)
        self.red_font = self.create_font(font_size, wx.RED)
        self.gray_font = self.create_font(font_size, wx.Colour(50, 50, 50, 50))

        self.wires = []
        self.wire_points = {}
        self.net_counter = 0  # for auto-labeling nets
        self.flags = {}  # off-schematic connectors or io pins
        self.texts = []
        self.rtree = rt.RTree()
        self.wire_lookup = rt.RTree()
        self.nets = {}  # name to net
        self.path = self.gc.CreatePath()
        self.symbol_instances = {}

        self.find_data = wx.FindReplaceData()
        self.find_dialog = None  # cannot be initialized here yet

        self.Bind(wx.EVT_CHAR_HOOK, self.on_key)
        self.Bind(wx.EVT_PAINT, self.on_paint)

    def load_symbols(self, symbol_paths):
        """Loads symbols from a list of paths to asy files."""
        if isinstance(symbol_paths, str):
            symbol_paths = [symbol_paths]
        for path in symbol_paths:
            path = os.path.join(path, "*.asy")
            filenames = glob.glob(path)
            for f in filenames:
                name = os.path.basename(f)[:-4]
                self.symbols[name] = Symbol(self, f)

    def create_font(self, size, color=wx.BLACK):
        return self.gc.CreateFont(
            wx.Font(
                int(10 * size),
                wx.FONTFAMILY_DEFAULT,
                wx.FONTSTYLE_NORMAL,
                wx.FONTWEIGHT_NORMAL,
            ),
            col=color,
        )

    def align_text(self, x, y, text, align, size, rotation, morig):
        """Aligns text for presentation. It takes formatting inputs from the asc file,
        i.e., rotation, alignment and matrix transformation and returns coordinates suitable
        for wx's DrawText function."""
        m = self.gc.CreateMatrix()
        m.Concat(morig)
        self.gc.SetFont(self.fonts[size])
        w, h, d, e = self.gc.GetFullTextExtent(text)
        if align[0] == "V":
            align = align[1:]
            m.Translate(x, y)
            m.Rotate(math.pi / 2 * 3)
            m.Translate(-x, -y)
            rotation += 270
        if align == "Right":
            x -= w
            y -= h / 2
        elif align == "Left":
            y -= h / 2
        elif align == "Top":
            x -= w / 2
        elif align == "Bottom":
            x -= w / 2
            y -= h
        elif align == "Center":
            x -= w / 2
            y -= h / 2
        m.Translate(x, y)

        # the only valid text directions are right or up
        if rotation % 360 == 180 or rotation % 360 == 90:
            m.Translate(w / 2, h / 2)
            m.Rotate(math.pi)
            m.Translate(-w / 2, -h / 2)
        x1, y1 = m.TransformPoint(0, 0)
        x2, y2 = m.TransformPoint(w, h)
        return min(x1, x2), min(y1, y2), max(y1, y2)

    def connect_wires(self, wire_point):
        """Connects wires to nets using recursion."""
        stack = [wire_point]
        while stack:
            wire_point = stack.pop()
            # check for a custom net name
            flag = self.flags.get((wire_point.x, wire_point.y))
            if flag:
                assert (
                    self.net_override is None or self.net_override == flag["net"]
                ), f"Conflicting net names are assigned: {self.net_override} and {flag['net']}"
                if self.net_override is None:
                    self.net_counter -= 1
                self.net_override = flag["net"]
                wire_point.net.name = flag["net"]

            for wire in wire_point.wires:
                wire.net = wire_point.net
                wire_point.net.wires.add(wire)
                if wire_point.x == wire.x0 and wire_point.y == wire.y0:
                    neighbor = self.wire_points.get((wire.x1, wire.y1))
                else:
                    neighbor = self.wire_points.get((wire.x0, wire.y0))
                if neighbor.net is None:
                    neighbor.net = wire_point.net
                    stack.append(neighbor)

    def load_asc(self, filename):
        """Loads an LtSpice schematic from the given filename."""
        instances = []
        self.filename = filename
        f = open(filename, encoding="iso-8859-1")
        self.reset_extent()
        sheet_w, sheet_h = 0, 0
        for line in f:
            line = line.strip()
            if len(line) == 0:
                continue
            words = line.split(" ")
            if words[0] == "WIRE":
                wire = Wire(*[int(x) for x in words[1:]])
                self.check_extent([wire.x0, wire.x1], [wire.y0, wire.y1])
                self.wires.append(wire)

                # save endpoints and determine direction of wire ends that is used for some connector symbols and ground
                # default direction at wire end is down
                wire_point0 = self.wire_points.get((wire.x0, wire.y0))
                if wire_point0 is None:
                    wire_point0 = WirePoint(wire.x0, wire.y0)
                    self.wire_points[(wire.x0, wire.y0)] = wire_point0
                wire_point1 = self.wire_points.get((wire.x1, wire.y1))
                if wire_point1 is None:
                    wire_point1 = WirePoint(wire.x1, wire.y1)
                    self.wire_points[(wire.x1, wire.y1)] = wire_point1
                wire_point0.wires.append(wire)
                wire_point1.wires.append(wire)
                if wire.x0 == wire.x1:  # vertical
                    if wire.y0 < wire.y1:
                        wire_point0.direction = 2  # top
                    else:
                        wire_point1.direction = 2
                if wire.y0 == wire.y1:  # horizontal
                    if wire.x0 < wire.x1:
                        wire_point0.direction = 1  # left
                        wire_point1.direction = 3
                    else:
                        wire_point0.direction = 3  # right
                        wire_point1.direction = 1

                min_x, min_y = min(wire.x0, wire.x1), min(
                    wire.y0, wire.y1
                )  # rtree lib needs a well-formed rect
                max_x, max_y = max(wire.x0, wire.x1), max(wire.y0, wire.y1)
                rect = rt.Rect(min_x, min_y, max_x + 1, max_y + 1)
                self.wire_lookup.insert(wire, rect)
            elif words[0] == "TEXT":
                x = int(words[1])
                y = int(words[2])
                align = words[3]
                size = int(words[4])
                text = " ".join(words[5:])
                self.check_extent(x - 15, y - 15)

                x, y, y2 = self.align_text(
                    x, y, text, align, size, 0, self.gc.CreateMatrix()
                )
                t = dict(x=x, y=y, size=size, text=text)

                self.texts.append(t)
            elif words[0] == "SHEET":
                sheet_w, sheet_h = int(words[2]), int(words[3])
            elif words[0] == "FLAG":
                last_flag = dict(
                    x=int(words[1]), y=int(words[2]), net=words[3], type=None
                )
                self.check_extent(last_flag["x"], last_flag["y"])
                self.flags[(last_flag["x"], last_flag["y"])] = last_flag
            elif words[0] == "IOPIN":
                last_flag["type"] = words[3]
            elif words[0] == "SYMATTR":
                attr = " ".join(words[2:])
                if words[1] == "InstName" and self.instance_name != "":
                    attr = self.instance_name + "." + attr
                instances[-1].attrs[words[1]] = attr
            elif words[0] == "SYMBOL":
                instance = SymbolInstance(
                    self,
                    words[1],
                    int(words[2]),
                    int(words[3]),
                    words[4][0] == "M",
                    int(words[4][1:]),
                )
                instances.append(instance)
                self.check_extent(instance.x, instance.y)
                # load default attrs from symbol file
                symbol = self.symbols.get(words[1])
                assert symbol, f"Unknown symbol {words[1]}"
                symbol.load()
                instance.attrs = symbol.attrs.copy()
            elif words[0] == "WINDOW":
                x = int(words[2])
                y = int(words[3])
                window = dict(
                    type=window_types[words[1]],
                    x=x,
                    y=y,
                    align=words[4],
                    size=int(words[5]),
                )
                instances[-1].windows[window["type"]] = window

        # load symbol instances
        self.symbol_instances = {}
        pin_positions = {}
        for instance in instances:
            s = self.symbols.get(instance.name)
            if s is None:
                print(f"Symbol not found {instance.name}")
                self.rtree.insert(
                    instance,
                    rt.Rect(
                        instance.x - 5, instance.y - 5, instance.x + 5, instance.y + 5
                    ),
                )
                continue
            s.load()
            instance.set_symbol(s)
            for pin in instance.pins:
                pin_positions[(pin.x, pin.y)] = (instance, pin)
            x1, y1 = instance.matrix.TransformPoint(s.x1, s.y1)
            x2, y2 = instance.matrix.TransformPoint(s.x2, s.y2)
            if x1 > x2:
                x1, x2 = x2, x1
            if y1 > y2:
                y1, y2 = y2, y1
            self.rtree.insert(
                instance,
                rt.Rect(
                    instance.x + x1, instance.y + y1, instance.x + x2, instance.y + y2
                ),
            )
            self.symbol_instances[instance.attrs["InstName"]] = instance
            self.check_extent(
                [instance.x + s.x1, instance.x + s.x2],
                [instance.y + s.y1, instance.y + s.y2],
            )

        # connect wires to pins
        for wire_point in self.wire_points.values():
            if wire_point.net:
                continue
            self.net_counter += 1
            wire_point.net = Net(f"N{self.net_counter:03d}")
            self.nets[wire_point.net.name] = wire_point.net
            self.net_override = (
                None  # is set to net name if a user-assigned net name is found
            )
            self.connect_wires(wire_point)

        # calculate correct pin index from SpiceOrder

        # add instance connections to nets and label spur types
        for wire_point in self.wire_points.values():
            res = pin_positions.get((wire_point.x, wire_point.y))
            if res:
                instance, pin = res
                pin_name = str(pin.symbol_pin.index)
                connection = Connection(instance, pin, pin_name)
                wire_point.net.connections.append(connection)

        # add net flags to main rtree
        for flag in self.flags.values():
            x1 = flag["x"]
            y1 = flag["y"]
            x2 = x1 + 20
            y2 = y1 + 20
            net = self.nets.setdefault(flag["net"], Net(flag["net"]))
            self.rtree.insert(net, rt.Rect(x1, y1, x2, y2))

        self.x1 -= 10
        self.y1 -= 10
        self.x2 = max(self.x2, sheet_w)
        self.y2 = max(self.y2, sheet_h)
        self.set_size(self.x2 - self.x1, self.y2 - self.y1)
        self.Refresh()

        self.path = self.gc.CreatePath()

        for wire in self.wires:
            self.path.MoveToPoint(wire.x0, wire.y0)
            self.path.AddLineToPoint(wire.x1, wire.y1)

        for wire_point in self.wire_points.values():
            # add dots representing wire connection
            if len(wire_point.wires) > 2:
                self.path.AddRectangle(wire_point.x - 2, wire_point.y - 2, 4, 4)

        for flag in self.flags.values():
            x1, y1 = flag["x"], flag["y"]
            if flag["type"] == "In":
                path = self.gc.CreatePath()
                path.MoveToPoint(x1, y1)
                path.AddLineToPoint(x1 + 10, y1 + 10)
                path.AddLineToPoint(x1 + 10, y1 + 20)
                path.AddLineToPoint(x1 - 10, y1 + 20)
                path.AddLineToPoint(x1 - 10, y1 + 10)
                path.AddLineToPoint(x1, y1)
                wire_point = self.wire_points.get((x1, y1))
                if wire_point and len(wire_point.wires) == 1:
                    direction = wire_point.direction
                    if direction:
                        m = self.gc.CreateMatrix()
                        m.Translate(x1, y1)
                        m.Rotate(math.pi / 2 * direction)
                        m.Translate(-x1, -y1)
                        path.Transform(m)
                self.path.AddPath(path)
            elif flag["type"] == "Out":
                pass
            elif flag["type"] == "BiDir":
                pass
            elif flag["net"] == "0":
                path = self.gc.CreatePath()
                path.MoveToPoint(x1 - 10, y1)
                path.AddLineToPoint(x1 + 10, y1)
                path.MoveToPoint(x1 - 10, y1)
                path.AddLineToPoint(x1, y1 + 10)
                path.MoveToPoint(x1 + 10, y1)
                path.AddLineToPoint(x1, y1 + 10)
                self.path.AddPath(path)

    def mouse_position(self, evt):
        """Returns the mouse position in schematic canvas coordinates."""
        dc = wx.ClientDC(self)
        self.DoPrepareDC(dc)
        x, y = evt.GetLogicalPosition(dc)
        return (x + self.x1, y + self.y1)

    def get_instance_under_mouse(self, evt):
        """Returns the symbol instance under the mouse pointer."""
        if len(self.symbol_instances) == 0:
            return None
        pos = self.mouse_position(evt)
        res = self.rtree.query(pos)
        try:
            return next(res).data
        except StopIteration:
            return None

    def get_net_under_mouse(self, evt):
        """Returns the net under the mouse pointer."""
        pos = self.mouse_position(evt)
        rect = (pos[0] - 5, pos[1] - 5, pos[0] + 5, pos[1] + 5)
        res = self.wire_lookup.query(rect)

        def distance_to_line(x0, y0, x1, y1, x2, y2):
            return (
                abs((x2 - x1) * (y1 - y0) - (x1 - x0) * (y2 - y1))
                / ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
            )

        res = [x.data for x in res]
        if not res:
            return None
        closest_wire = min(
            res,
            key=lambda wire: distance_to_line(
                pos[0], pos[1], wire.x0, wire.y0, wire.x1, wire.y1
            ),
        )
        return closest_wire.net

    def on_key(self, evt):
        k = evt.GetUnicodeKey()
        if evt.ControlDown():
            k = chr(k)
            if k == "F":
                if self.find_dialog is None:
                    title = f"Find in {self.instance_name}"
                    self.find_data.SetFindString("")
                    self.find_dialog = wx.FindReplaceDialog(None, self.find_data, title)
                    self.find_dialog.Bind(wx.EVT_FIND, self.on_find)
                self.find_dialog.Show()
                return
        evt.Skip()

    def on_find(self, evt):
        find = evt.GetFindString()
        self.find_dialog.Destroy()
        self.find_dialog = None

        # search nodes
        r = list(self.rtree.search(None, lambda x: x.data.name == find))
        if len(r):
            r = r[0]
            self.center_on(r.rect.min_x - self.x1, r.rect.min_y - self.y1)
        else:
            wx.MessageDialog(
                None, "No matches", "Error", wx.OK | wx.ICON_QUESTION
            ).ShowModal()

    def go_to_edge(self, instance_name):
        """Scrolls the canvas to the symbol instance specified by instance_name."""
        if not instance_name.startswith(self.instance_name):
            print(f"{instance_name} is not in {self.instance_name}")
            return
        local_instance = instance_name[len(self.instance_name) + 1 :].split(".")[0]
        instance_name = self.instance_name + "." + local_instance
        s = self.symbol_instances.get(instance_name)
        if s is None:
            return
        self.center_on(s.x - self.x1, s.y - self.y1)

    def on_paint(self, evt):
        """Paints the schematic."""
        dc = wx.PaintDC(self)
        self.DoPrepareDC(dc)
        gc = wx.GraphicsContext.Create(dc)
        gc.Translate(-self.x1, -self.y1)

        gc.SetPen(self.black_pen)
        gc.StrokePath(self.path)
        gc.SetFont(self.fonts[1])
        for flag in self.flags.values():
            if flag["net"] == "0":
                continue
            gc.DrawText(flag["net"], flag["x"], flag["y"])

        for instance in self.symbol_instances.values():
            instance.paint(gc)

        for text in self.texts:
            gc.SetFont(self.fonts[text["size"]])
            gc.DrawText(text["text"], text["x"], text["y"])
