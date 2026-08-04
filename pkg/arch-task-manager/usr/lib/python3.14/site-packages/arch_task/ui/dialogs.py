import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib
from typing import List, Tuple, Dict, Callable

class FdInspectorDialog(Adw.Window):
    """Modal window inspecting open file descriptors of a process."""
    def __init__(self, parent: Gtk.Window, pid: int, process_name: str, fds: List[Tuple[str, str]]):
        super().__init__(transient_for=parent, modal=True, title=f"File Descriptors — PID {pid} ({process_name})")
        self.set_default_size(650, 450)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.set_content(main_box)

        # Header Bar
        header = Adw.HeaderBar()
        main_box.append(header)

        # Search Bar
        search_entry = Gtk.SearchEntry(placeholder_text="Filter file descriptors...")
        search_entry.set_margin_start(12)
        search_entry.set_margin_end(12)
        main_box.append(search_entry)

        # Scrolled List
        scrolled = Gtk.ScrolledWindow(vexpand=True)
        main_box.append(scrolled)

        list_box = Gtk.ListBox(css_classes=["boxed-list"])
        list_box.set_margin_start(12)
        list_box.set_margin_end(12)
        list_box.set_margin_bottom(12)
        scrolled.set_child(list_box)

        for fd_num, target in fds:
            row = Adw.ActionRow(title=f"FD {fd_num}", subtitle=target)
            row._search_text = f"{fd_num} {target}".lower()
            list_box.append(row)

        def filter_func(row):
            query = search_entry.get_text().strip().lower()
            if not query:
                return True
            return query in getattr(row, "_search_text", "")

        list_box.set_filter_func(filter_func)
        search_entry.connect("search-changed", lambda e: list_box.invalidate_filter())

class EnvInspectorDialog(Adw.Window):
    """Modal window inspecting environment variables of a process."""
    def __init__(self, parent: Gtk.Window, pid: int, process_name: str, env_vars: Dict[str, str]):
        super().__init__(transient_for=parent, modal=True, title=f"Environment Variables — PID {pid} ({process_name})")
        self.set_default_size(700, 500)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.set_content(main_box)

        header = Adw.HeaderBar()
        main_box.append(header)

        search_entry = Gtk.SearchEntry(placeholder_text="Filter environment variables...")
        search_entry.set_margin_start(12)
        search_entry.set_margin_end(12)
        main_box.append(search_entry)

        scrolled = Gtk.ScrolledWindow(vexpand=True)
        main_box.append(scrolled)

        list_box = Gtk.ListBox(css_classes=["boxed-list"])
        list_box.set_margin_start(12)
        list_box.set_margin_end(12)
        list_box.set_margin_bottom(12)
        scrolled.set_child(list_box)

        for k, v in sorted(env_vars.items()):
            row = Adw.ActionRow(title=k, subtitle=v)
            row.set_subtitle_selectable(True)
            row._search_text = f"{k}={v}".lower()
            list_box.append(row)

        def filter_func(row):
            query = search_entry.get_text().strip().lower()
            if not query:
                return True
            return query in getattr(row, "_search_text", "")

        list_box.set_filter_func(filter_func)
        search_entry.connect("search-changed", lambda e: list_box.invalidate_filter())

class ReniceDialog(Adw.Window):
    """Modal dialog allowing nice value adjustment from -20 (highest) to +19 (lowest)."""
    def __init__(self, parent: Gtk.Window, pids: List[int], current_nice: int, callback: Callable[[int], None]):
        super().__init__(transient_for=parent, modal=True, title=f"Renice Process(es) {pids}")
        self.set_default_size(400, 250)
        self.callback = callback

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_margin_start(20)
        box.set_margin_end(20)
        box.set_margin_top(20)
        box.set_margin_bottom(20)
        self.set_content(box)

        label = Gtk.Label(label=f"Set new scheduling priority for PID(s): {', '.join(map(str, pids))}\n(-20 = Highest priority, 19 = Lowest priority)")
        label.set_wrap(True)
        box.append(label)

        self.scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, -20, 19, 1)
        self.scale.set_value(current_nice)
        self.scale.set_draw_value(True)
        self.scale.set_value_pos(Gtk.PositionType.BOTTOM)
        box.append(self.scale)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10, halign=Gtk.Align.END)
        box.append(btn_box)

        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda e: self.destroy())
        btn_box.append(cancel_btn)

        apply_btn = Gtk.Button(label="Apply Renice", css_classes=["suggested-action"])
        apply_btn.connect("clicked", self._on_apply)
        btn_box.append(apply_btn)

    def _on_apply(self, btn):
        new_val = int(self.scale.get_value())
        self.callback(new_val)
        self.destroy()
