import math
import time
import collections
from typing import List, Tuple, Optional
import cairo
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Gdk, Adw

# Preset Standard Color Palettes
COLOR_CPU = [(0.208, 0.518, 0.894)] # GNOME Blue #3584e4
COLOR_MEMORY = [(0.569, 0.255, 0.675)] # GNOME Purple #9141ac
COLOR_DISK = [(0.180, 0.761, 0.494), (0.902, 0.380, 0.000)] # Read Green #2ec27e, Write Orange #e66100
COLOR_NET = [(0.071, 0.596, 0.608), (0.878, 0.106, 0.141)] # Download Teal #12989b, Upload Pink/Red #e01b24
COLOR_TEMP = [(0.953, 0.400, 0.149)] # Vibrant Thermal Orange/Red #f36626

def format_graph_value(val: float, unit_suffix: str, auto_scale: bool) -> str:
    """Formats values for graph labels and tooltips."""
    if not auto_scale:
        return f"{val:.1f}{unit_suffix}"
    
    # Auto-scale byte rates (B/s, KiB/s, MiB/s, GiB/s)
    if "B/s" in unit_suffix or "B" in unit_suffix:
        if val < 1024:
            return f"{val:.0f} B/s"
        elif val < 1024 * 1024:
            return f"{val / 1024:.1f} KiB/s"
        elif val < 1024 * 1024 * 1024:
            return f"{val / (1024 * 1024):.1f} MiB/s"
        else:
            return f"{val / (1024 * 1024 * 1024):.2f} GiB/s"
    return f"{val:.1f}{unit_suffix}"

class RollingGraphWidget(Gtk.DrawingArea):
    """
    High-performance GTK4 Cairo DrawingArea rendering smooth anti-aliased Bezier vector graphs
    with subtle gradient fills, theme awareness, and interactive hover tooltips.
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

        self.colors = colors or COLOR_CPU

        # Data structure: List of (deque of values, deque of timestamps)
        self.series_data: List[collections.deque] = [collections.deque(maxlen=max_points)]
        self.series_timestamps: List[collections.deque] = [collections.deque(maxlen=max_points)]

        # Interactive Hover state
        self.mouse_x: Optional[float] = None
        self.mouse_y: Optional[float] = None
        self.is_hovering: bool = False

        # Setup GTK drawing and mouse motion events
        self.set_draw_func(self._on_draw)

        motion_ctrl = Gtk.EventControllerMotion.new()
        motion_ctrl.connect("motion", self._on_mouse_motion)
        motion_ctrl.connect("leave", self._on_mouse_leave)
        self.add_controller(motion_ctrl)

    def add_point(self, value: float, series_index: int = 0, timestamp: Optional[float] = None):
        """Appends a new data sample with timestamp and updates drawing area immediately."""
        now = timestamp or time.time()
        while len(self.series_data) <= series_index:
            self.series_data.append(collections.deque(maxlen=self.max_points))
            self.series_timestamps.append(collections.deque(maxlen=self.max_points))
            
        self.series_data[series_index].append(value)
        self.series_timestamps[series_index].append(now)

        self.queue_draw()

    def add_multi_points(self, values: List[float], timestamp: Optional[float] = None):
        """Appends values for multiple series at once."""
        now = timestamp or time.time()
        for idx, val in enumerate(values):
            self.add_point(val, idx, timestamp=now)

    def _on_mouse_motion(self, controller, x, y):
        self.mouse_x = x
        self.mouse_y = y
        self.is_hovering = True
        self.queue_draw()

    def _on_mouse_leave(self, controller):
        self.is_hovering = False
        self.mouse_x = None
        self.mouse_y = None
        self.queue_draw()

    def _get_theme_colors(self) -> Tuple[Tuple[float, float, float], Tuple[float, float, float], Tuple[float, float, float], float]:
        """Detects Libadwaita dark vs light theme and returns matching Cairo RGBA tokens."""
        is_dark = True
        try:
            is_dark = Adw.StyleManager.get_default().get_dark()
        except Exception:
            pass

        if is_dark:
            bg_color = (0.10, 0.11, 0.14)      # Dark slate canvas
            grid_color = (0.22, 0.25, 0.32)    # Subtle grid line
            text_color = (0.85, 0.88, 0.92)    # Crisp light text
            border_alpha = 0.4
        else:
            bg_color = (0.97, 0.97, 0.98)      # Light canvas
            grid_color = (0.82, 0.85, 0.88)    # Light gray grid
            text_color = (0.15, 0.18, 0.22)    # Dark text
            border_alpha = 0.3

        return bg_color, grid_color, text_color, border_alpha

    def _compute_smooth_bezier_path(self, points: List[Tuple[float, float]]) -> List[Tuple[str, List[float]]]:
        """
        Generates smooth cubic Bezier curve commands (move_to, curve_to) using Catmull-Rom / Spline interpolation.
        """
        if not points:
            return []
        if len(points) == 1:
            return [("move_to", [points[0][0], points[0][1]])]
        if len(points) == 2:
            return [
                ("move_to", [points[0][0], points[0][1]]),
                ("line_to", [points[1][0], points[1][1]])
            ]

        commands = [("move_to", [points[0][0], points[0][1]])]
        n = len(points)

        for i in range(n - 1):
            p0 = points[max(0, i - 1)]
            p1 = points[i]
            p2 = points[i + 1]
            p3 = points[min(n - 1, i + 2)]

            # Control points calculated using Catmull-Rom to Bezier conversion (smoothness = 0.2)
            tension = 0.2
            cp1_x = p1[0] + (p2[0] - p0[0]) * tension
            cp1_y = p1[1] + (p2[1] - p0[1]) * tension
            cp2_x = p2[0] - (p3[0] - p1[0]) * tension
            cp2_y = p2[1] - (p3[1] - p1[1]) * tension

            commands.append(("curve_to", [cp1_x, cp1_y, cp2_x, cp2_y, p2[0], p2[1]]))

        return commands

    def _on_draw(self, drawing_area, cr: cairo.Context, width: int, height: int):
        cr.set_antialias(cairo.ANTIALIAS_BEST)
        bg_rgb, grid_rgb, text_rgb, border_alpha = self._get_theme_colors()

        # 1. Canvas Background
        cr.set_source_rgb(*bg_rgb)
        cr.rectangle(0, 0, width, height)
        cr.fill()

        # Dimensions & Margins
        margin_top = 28
        margin_bottom = 22
        margin_left = 12
        margin_right = 55 # Space for right-aligned Y-axis labels
        plot_w = width - margin_left - margin_right
        plot_h = height - margin_top - margin_bottom

        if plot_w <= 10 or plot_h <= 10:
            return

        # 2. Dynamic Auto-scaling & Range Calculation
        max_val = 100.0 if not self.auto_scale else 1.0
        if self.auto_scale:
            for deque_data in self.series_data:
                if deque_data:
                    max_val = max(max_val, max(deque_data))
            max_val = math.ceil(max_val * 1.15) if max_val > 0 else 1.0

        # 3. Draw Faint Horizontal Gridlines & Y-Axis Value Labels
        grid_rows = 4
        cr.set_line_width(1.0)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(9.5)

        for i in range(grid_rows + 1):
            ratio = i / grid_rows
            y = margin_top + plot_h * (1.0 - ratio)

            # Gridline
            cr.set_source_rgba(*grid_rgb, 0.5 if i % 2 == 0 else 0.25)
            cr.move_to(margin_left, y)
            cr.line_to(margin_left + plot_w, y)
            cr.stroke()

            # Right Y-axis Label
            val_at_grid = max_val * ratio
            label_str = format_graph_value(val_at_grid, self.unit_suffix, self.auto_scale)
            cr.set_source_rgb(*text_rgb)
            cr.move_to(margin_left + plot_w + 6, y + 3)
            cr.show_text(label_str)

        # 4. Header Title & Primary Latest Value Display
        cr.set_source_rgb(*text_rgb)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(11.0)
        cr.move_to(margin_left, 18)
        cr.show_text(self.title)

        if self.series_data and self.series_data[0]:
            latest_val = self.series_data[0][-1]
            latest_str = format_graph_value(latest_val, self.unit_suffix, self.auto_scale)
            cr.move_to(width - margin_right, 18)
            cr.show_text(latest_str)

        # 5. Render Smooth Bezier Vector Lines & Fading Gradient Fills
        step_x = plot_w / max(1, self.max_points - 1)

        hover_closest_idx = None
        hover_closest_dist = float('inf')

        for s_idx, deque_data in enumerate(self.series_data):
            if not deque_data or len(deque_data) < 1:
                continue

            r, g, b = self.colors[s_idx % len(self.colors)]

            # Convert data points to screen coordinates
            screen_pts: List[Tuple[float, float]] = []
            num_pts = len(deque_data)

            for i, val in enumerate(deque_data):
                x = margin_left + (i - (self.max_points - num_pts)) * step_x
                x = max(margin_left, min(margin_left + plot_w, x))
                
                clamped_val = max(0.0, min(max_val, val))
                y = margin_top + plot_h - (clamped_val / max_val) * plot_h
                screen_pts.append((x, y))

                # Check hover proximity
                if self.is_hovering and self.mouse_x is not None:
                    dist = abs(self.mouse_x - x)
                    if dist < hover_closest_dist:
                        hover_closest_dist = dist
                        hover_closest_idx = (s_idx, i, x, y, val)

            # Generate smooth Bezier path commands
            bezier_cmds = self._compute_smooth_bezier_path(screen_pts)
            if not bezier_cmds:
                continue

            # Build Cairo Path
            cr.new_path()
            for cmd, args in bezier_cmds:
                if cmd == "move_to":
                    cr.move_to(*args)
                elif cmd == "line_to":
                    cr.line_to(*args)
                elif cmd == "curve_to":
                    cr.curve_to(*args)

            # Subtle Gradient Fill Beneath Curve
            fill_path = cr.copy_path()
            if screen_pts:
                cr.line_to(screen_pts[-1][0], margin_top + plot_h)
                cr.line_to(screen_pts[0][0], margin_top + plot_h)
                cr.close_path()

                grad = cairo.LinearGradient(0, margin_top, 0, margin_top + plot_h)
                grad.add_color_stop_rgba(0.0, r, g, b, 0.38) # Peak opacity
                grad.add_color_stop_rgba(0.7, r, g, b, 0.10)
                grad.add_color_stop_rgba(1.0, r, g, b, 0.00) # Completely transparent at bottom

                cr.set_source(grad)
                cr.fill()

            # Stroke Bezier Line
            cr.new_path()
            cr.append_path(fill_path)
            cr.set_source_rgba(r, g, b, 0.95)
            cr.set_line_width(2.0)
            cr.stroke()

        # 6. Plot Area Border
        cr.set_source_rgba(*grid_rgb, border_alpha)
        cr.set_line_width(1.0)
        cr.rectangle(margin_left, margin_top, plot_w, plot_h)
        cr.stroke()

        # 7. Interactive Hover Tooltip & Crosshair Line
        if self.is_hovering and hover_closest_idx and self.mouse_x is not None:
            s_idx, point_idx, px, py, p_val = hover_closest_idx

            if margin_left <= self.mouse_x <= margin_left + plot_w:
                # Vertical Crosshair Line
                cr.set_source_rgba(*text_rgb, 0.45)
                cr.set_line_width(1.0)
                cr.set_dash([3, 3])
                cr.move_to(px, margin_top)
                cr.line_to(px, margin_top + plot_h)
                cr.stroke()
                cr.set_dash([]) # Reset dash

                # Highlight Data Node Circle
                hr, hg, hb = self.colors[s_idx % len(self.colors)]
                cr.set_source_rgb(hr, hg, hb)
                cr.arc(px, py, 4.5, 0, 2 * math.pi)
                cr.fill()
                cr.set_source_rgb(1.0, 1.0, 1.0)
                cr.arc(px, py, 2.0, 0, 2 * math.pi)
                cr.fill()

                # Calculate Timestamp / Seconds ago
                t_str = ""
                if s_idx < len(self.series_timestamps) and point_idx < len(self.series_timestamps[s_idx]):
                    ts = self.series_timestamps[s_idx][point_idx]
                    sec_ago = int(time.time() - ts)
                    t_str = f" ({sec_ago}s ago)" if sec_ago > 0 else " (now)"

                # Floating Tooltip Badge
                val_text = f"{format_graph_value(p_val, self.unit_suffix, self.auto_scale)}{t_str}"
                cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
                cr.set_font_size(10.0)
                ext = cr.text_extents(val_text)

                badge_w = ext.width + 16
                badge_h = ext.height + 10
                bx = px + 10
                if bx + badge_w > margin_left + plot_w:
                    bx = px - badge_w - 10
                by = py - badge_h / 2
                by = max(margin_top, min(margin_top + plot_h - badge_h, by))

                # Tooltip Badge Background
                cr.set_source_rgba(*bg_rgb, 0.92)
                cr.rectangle(bx, by, badge_w, badge_h)
                cr.fill()

                cr.set_source_rgba(hr, hg, hb, 0.9)
                cr.set_line_width(1.2)
                cr.rectangle(bx, by, badge_w, badge_h)
                cr.stroke()

                # Tooltip Text
                cr.set_source_rgb(*text_rgb)
                cr.move_to(bx + 8, by + badge_h - 4)
                cr.show_text(val_text)
