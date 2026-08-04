import math
import collections
from typing import List, Tuple, Optional
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, cairo

class RollingGraphWidget(Gtk.DrawingArea):
    """
    GTK4 Cairo DrawingArea for rendering smooth, live-updating rolling history graphs.
    Supports single or multi-series lines, gradient fill background, grid lines, and labels.
    """
    def __init__(
        self,
        max_points: int = 60,
        colors: Optional[List[Tuple[float, float, float]]] = None,
        title: str = "",
        unit_suffix: str = "%",
        auto_scale: bool = False
    ):
        super().__init__()
        self.max_points = max_points
        self.title = title
        self.unit_suffix = unit_suffix
        self.auto_scale = auto_scale

        # Default cyan/blue gradient color palette
        self.colors = colors or [
            (0.2, 0.6, 1.0), # Bright blue
            (0.1, 0.8, 0.6), # Teal/Cyan
            (0.9, 0.4, 0.2), # Orange
            (0.7, 0.3, 0.9)  # Purple
        ]

        # Series data: list of deque objects
        self.series_data: List[collections.deque] = [collections.deque(maxlen=max_points)]
        self.set_draw_func(self._on_draw)

    def add_point(self, value: float, series_index: int = 0):
        """Appends a new data sample to specified series index and queues redraw."""
        while len(self.series_data) <= series_index:
            self.series_data.append(collections.deque(maxlen=self.max_points))
        self.series_data[series_index].append(value)
        self.queue_draw()

    def add_multi_points(self, values: List[float]):
        """Appends values for multiple series at once."""
        for idx, val in enumerate(values):
            self.add_point(val, idx)

    def _on_draw(self, drawing_area, cr: cairo.Context, width: int, height: int):
        # 1. Background Fill
        cr.set_source_rgba(0.08, 0.09, 0.11, 1.0) # Dark sleek slate
        cr.rectangle(0, 0, width, height)
        cr.fill()

        # Margin and plot area
        margin_top = 24
        margin_bottom = 20
        margin_left = 10
        margin_right = 10
        plot_w = width - margin_left - margin_right
        plot_h = height - margin_top - margin_bottom

        if plot_w <= 10 or plot_h <= 10:
            return

        # 2. Draw Grid Lines
        cr.set_source_rgba(0.2, 0.25, 0.3, 0.4)
        cr.set_line_width(1.0)
        grid_rows = 4
        for i in range(grid_rows + 1):
            y = margin_top + (plot_h / grid_rows) * i
            cr.move_to(margin_left, y)
            cr.line_to(margin_left + plot_w, y)
            cr.stroke()

        # 3. Determine Max Range
        max_val = 100.0 if not self.auto_scale else 1.0
        if self.auto_scale:
            for deque_data in self.series_data:
                if deque_data:
                    max_val = max(max_val, max(deque_data))
            max_val = math.ceil(max_val * 1.1) if max_val > 0 else 1.0

        # 4. Draw Header Title & Current Max Value
        cr.set_source_rgba(0.85, 0.88, 0.92, 1.0)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(11.0)

        # Title
        cr.move_to(margin_left, 16)
        cr.show_text(self.title)

        # Latest Value
        if self.series_data and self.series_data[0]:
            latest = self.series_data[0][-1]
            val_text = f"{latest:.1f}{self.unit_suffix}"
            cr.move_to(width - margin_right - 60, 16)
            cr.show_text(val_text)

        # 5. Draw Data Series Lines & Filled Areas
        step_x = plot_w / max(1, self.max_points - 1)

        for s_idx, deque_data in enumerate(self.series_data):
            if not deque_data or len(deque_data) < 2:
                continue

            r, g, b = self.colors[s_idx % len(self.colors)]

            # Build line path
            cr.move_to(margin_left, margin_top + plot_h - (deque_data[0] / max_val) * plot_h)
            for i, val in enumerate(deque_data):
                x = margin_left + i * step_x
                y = margin_top + plot_h - (val / max_val) * plot_h
                cr.line_to(x, y)

            # Gradient fill under curve for primary series
            if s_idx == 0:
                # Save path for filling
                pattern = cairo.LinearGradient(0, margin_top, 0, margin_top + plot_h)
                pattern.add_color_stop_rgba(0, r, g, b, 0.35)
                pattern.add_color_stop_rgba(1, r, g, b, 0.02)

                fill_path = cr.copy_path()
                cr.line_to(margin_left + (len(deque_data) - 1) * step_x, margin_top + plot_h)
                cr.line_to(margin_left, margin_top + plot_h)
                cr.close_path()

                cr.set_source(pattern)
                cr.fill()

                # Restore stroke path
                cr.new_path()
                cr.append_path(fill_path)

            # Stroke main line
            cr.set_source_rgba(r, g, b, 0.95)
            cr.set_line_width(1.8)
            cr.stroke()

        # Border box around graph
        cr.set_source_rgba(0.25, 0.3, 0.38, 0.6)
        cr.set_line_width(1.0)
        cr.rectangle(margin_left, margin_top, plot_w, plot_h)
        cr.stroke()
