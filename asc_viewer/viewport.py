import wx


class Viewport(wx.ScrolledCanvas):
    """An abstract viewport that supports scrolling and zooming, without implementing painting."""

    def __init__(self, *args):
        wx.ScrolledCanvas.__init__(self, *args)
        self.zoom = 1.0

        self.Bind(wx.EVT_MOUSEWHEEL, self.OnWheel)
        self.Bind(wx.EVT_MIDDLE_DOWN, self.OnMiddleDown)
        self.Bind(wx.EVT_MIDDLE_UP, self.OnMiddleUp)
        self.Bind(wx.EVT_MOTION, self.OnMotion)
        self.dragging = ""
        self.w = 1
        self.h = 1
        self.bmp = None
        self.SetScrollRate(1, 1)

    def set_size(self, width, height):
        self.w = width
        self.h = height
        self.zoom = 1
        # zoom to fit:
        #  w, h = self.GetClientSize()
        #  self.zoom = min(w/self.w, h/self.h)
        self.SetScale(self.zoom, self.zoom)
        self.SetVirtualSize(int(self.w * self.zoom), int(self.h * self.zoom))

    def get_scroll_origin(self):
        return [x / self.zoom for x in self.GetViewStart()]

    def set_scroll_origin(self, x, y):
        self.Scroll(int(x * self.zoom), int(y * self.zoom))

    def center_on(self, x, y):
        w, h = self.GetClientSize()
        w /= 2 * self.zoom
        h /= 2 * self.zoom
        x -= w
        y -= h
        self.Scroll(int(x * self.zoom), int(y * self.zoom))

    def set_zoom(self, zoom):
        """Changes scroll origin."""
        if zoom == "full":
            w, h = self.GetClientSize()
            zoom = min(w / self.w, h / self.h)
        self.SetScale(zoom, zoom)
        self.SetVirtualSize(int(self.w * zoom), int(self.h * zoom))
        self.zoom = zoom
        self.Refresh()

    def OnMiddleDown(self, evt):
        dc = wx.ClientDC(self)
        self.DoPrepareDC(dc)
        pos = evt.GetLogicalPosition(dc)
        self.dragging = "middle"
        self.scroll_origin_x, self.scroll_origin_y = self.GetViewStart()
        self.scroll_origin_x /= self.zoom
        self.scroll_origin_y /= self.zoom
        self.drag_origin = pos
        self.drag_pos = pos

    def OnMiddleUp(self, evt):
        self.dragging = ""

    def OnMotion(self, evt):
        if not evt.Dragging():
            return
        dc = wx.ClientDC(self)
        self.DoPrepareDC(dc)
        pos = evt.GetLogicalPosition(dc)
        if self.dragging == "middle":
            x = self.scroll_origin_x + (self.drag_origin[0] - pos[0])
            y = self.scroll_origin_y + (self.drag_origin[1] - pos[1])
            if x < 0:
                self.drag_origin[0] -= int(x)
            if y < 0:
                self.drag_origin[1] -= int(y)
            w, h = self.GetClientSize()
            w /= self.zoom
            h /= self.zoom
            if x > self.w - w:
                self.drag_origin[0] += int(self.w - w - x)
            if y > self.h - h:
                self.drag_origin[1] += int(self.h - h - y)
            self.scroll_origin_x = max(min(x, self.w - w), 0)
            self.scroll_origin_y = max(min(y, self.h - h), 0)
            self.Scroll(
                int(self.scroll_origin_x * self.zoom),
                int(self.scroll_origin_y * self.zoom),
            )
        self.Refresh()
        self.drag_pos = pos

    def OnWheel(self, evt):
        dc = wx.ClientDC(self)
        self.DoPrepareDC(dc)
        pos = evt.GetLogicalPosition(dc)
        offset = self.CalcScrolledPosition(pos[0], pos[1])

        zoom = self.zoom * 1.2 ** (evt.GetWheelRotation() / 120)
        if (
            zoom < 0.2
            and evt.GetWheelRotation() < 0
            or zoom > 16
            and evt.GetWheelRotation() > 0
        ):
            return
        scroll_origin_x, scroll_origin_y = self.GetViewStart()
        scroll_origin_x /= self.zoom
        scroll_origin_y /= self.zoom
        self.SetScale(zoom, zoom)
        self.SetVirtualSize(int(self.w * zoom), int(self.h * zoom))
        scroll_origin_x = int(self.zoom * (scroll_origin_x - pos[0]) + pos[0] * zoom)
        scroll_origin_y = int(self.zoom * (scroll_origin_y - pos[1]) + pos[1] * zoom)
        self.Scroll(scroll_origin_x, scroll_origin_y)
        self.zoom = zoom
        self.Refresh()
