class BoundedCanvas:
    """A mixin that keeps track of canvas size."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.reset_extent()

    def reset_extent(self):
        """Resets the size to 0."""
        self.x1 = 0
        self.x2 = 0
        self.y1 = 0
        self.y2 = 0
        self.w = 0
        self.h = 0

    def check_extent(self, xs, ys):
        """Grows the canvas if needed such that the given coordinates fit inside it.

        Arguments:
        xs --- list of x values to check.
        ys --- list of y values to check.
        """
        if isinstance(xs, int):
            xs = [xs]
        if isinstance(ys, int):
            ys = [ys]
        for x in xs:
            if x < self.x1:
                self.x1 = x
            if x > self.x2:
                self.x2 = x
        for y in ys:
            if y < self.y1:
                self.y1 = y
            if y > self.y2:
                self.y2 = y
        self.w = self.x2 - self.x1
        self.h = self.y2 - self.y1

    def get_extent(self):
        return self.x1, self.y1, self.x2, self.y2
