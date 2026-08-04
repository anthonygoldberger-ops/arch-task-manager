import os
import signal
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('Gio', '2.0')
from gi.repository import Gtk, Gdk, Gio, GLib, GObject, Pango
from typing import List, Dict, Optional, Set

from ..monitors.process_monitor import ProcessMonitor, ProcessInfo
from ..utils.elevation import PrivilegeElevator
from .dialogs import FdInspectorDialog, EnvInspectorDialog, ReniceDialog

def format_bytes(bytes_val: float) -> str:
    """Formats raw bytes value into human-readable B, KiB, MiB, GiB, TiB."""
    if bytes_val < 1024:
        return f"{int(bytes_val)} B"
    elif bytes_val < 1024 * 1024:
        return f"{bytes_val / 1024:.1f} KiB"
    elif bytes_val < 1024 * 1024 * 1024:
        return f"{bytes_val / (1024 * 1024):.1f} MiB"
    else:
        return f"{bytes_val / (1024 * 1024 * 1024):.2f} GiB"

class ProcessGObject(GObject.Object):
    """GObject wrapper for ProcessInfo to bind with Gtk.ColumnView / ListStore."""
    __gproperties__ = {}

    def __init__(self, info: ProcessInfo):
        super().__init__()
        self.info = info
        self.pid = info.pid
        self.ppid = info.ppid
        self.name = info.name
        self.user = info.user
        self.state = info.state
        self.cpu_percent = info.cpu_percent
        self.rss_bytes = info.rss_bytes
        self.vsize_bytes = info.vsize_bytes
        self.read_bytes_sec = info.read_bytes_sec
        self.write_bytes_sec = info.write_bytes_sec
        self.nice = info.nice
        self.threads = info.threads
        self.start_time_str = info.start_time_str
        self.cmdline = info.cmdline

class ProcessView(Gtk.Box):
    """Processes tab with Gtk.ColumnView table, sortable headers, filter, context menu, and tree view support."""
    def __init__(self, main_window: Gtk.Window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.main_window = main_window
        self.monitor = ProcessMonitor()
        self.is_tree_view = False
        self.high_cpu_threshold = 50.0 # %
        self.high_mem_threshold = 1024 * 1024 * 1024 # 1 GB

        self.set_margin_start(8)
        self.set_margin_end(8)
        self.set_margin_top(8)
        self.set_margin_bottom(8)

        # 1. Top Controls Bar (Search + Tree Toggle + Highlighting Legend)
        top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.append(top_bar)

        self.search_entry = Gtk.SearchEntry(placeholder_text="Search processes by name, PID, user, cmdline...")
        self.search_entry.set_hexpand(True)
        top_bar.append(self.search_entry)

        self.tree_toggle = Gtk.ToggleButton(label="Tree View")
        self.tree_toggle.set_tooltip_text("Toggle parent-child process hierarchy view")
        self.tree_toggle.connect("toggled", self._on_tree_toggled)
        top_bar.append(self.tree_toggle)

        # 2. Setup Data Model (ListStore + FilterListModel + SortListModel)
        self.store = Gio.ListStore.new(ProcessGObject)
        self.filter_model = Gtk.FilterListModel.new(self.store, None)

        # Custom CustomFilter for search
        self.custom_filter = Gtk.CustomFilter.new(self._filter_func)
        self.filter_model.set_filter(self.custom_filter)
        self.search_entry.connect("search-changed", lambda e: self.custom_filter.changed(Gtk.FilterChange.DIFFERENT))

        self.sort_model = Gtk.SortListModel.new(self.filter_model, None)

        # Selection Model (Multi Selection)
        self.selection_model = Gtk.MultiSelection.new(self.sort_model)

        # 3. Build ColumnView
        self.column_view = Gtk.ColumnView.new(self.selection_model)
        self.column_view.set_show_column_separators(True)
        self.column_view.set_show_row_separators(True)

        # Bind sorting header clicks
        self.sort_model.set_sorter(self.column_view.get_sorter())

        # Scrolled container
        scrolled = Gtk.ScrolledWindow(vexpand=True)
        scrolled.set_child(self.column_view)
        self.append(scrolled)

        # Create Columns
        self._create_columns()

        # 4. Context Menu (Right Click)
        gesture = Gtk.GestureClick.new()
        gesture.set_button(Gdk.BUTTON_SECONDARY) # Right click
        gesture.connect("pressed", self._on_right_click)
        self.column_view.add_controller(gesture)

    def _filter_func(self, item: ProcessGObject) -> bool:
        query = self.search_entry.get_text().strip().lower()
        if not query:
            return True
        info = item.info
        text = f"{info.name} {info.pid} {info.user} {info.cmdline}".lower()
        return query in text

    def _create_columns(self):
        # Column definitions: (title, getter_func, sorter_type)
        cols = [
            ("PID", lambda p: str(p.pid), lambda p: p.pid),
            ("Process Name", lambda p: p.name, lambda p: p.name.lower()),
            ("User", lambda p: p.user, lambda p: p.user),
            ("CPU %", lambda p: f"{p.cpu_percent:.1f}%", lambda p: p.cpu_percent),
            ("RAM (RSS)", lambda p: format_bytes(p.rss_bytes), lambda p: p.rss_bytes),
            ("Virtual RAM", lambda p: format_bytes(p.vsize_bytes), lambda p: p.vsize_bytes),
            ("Disk Read", lambda p: f"{format_bytes(p.read_bytes_sec)}/s", lambda p: p.read_bytes_sec),
            ("Disk Write", lambda p: f"{format_bytes(p.write_bytes_sec)}/s", lambda p: p.write_bytes_sec),
            ("State", lambda p: p.state, lambda p: p.state),
            ("Threads", lambda p: str(p.threads), lambda p: p.threads),
            ("Nice", lambda p: str(p.nice), lambda p: p.nice),
            ("Start Time", lambda p: p.start_time_str, lambda p: p.start_time_str),
        ]

        for title, str_func, sort_key_func in cols:
            factory = Gtk.SignalListItemFactory()
            factory.connect("setup", self._on_factory_setup)
            factory.connect("bind", lambda f, item, sf=str_func: self._on_factory_bind(item, sf))

            sorter = Gtk.CustomSorter.new(lambda a, b, sk=sort_key_func: self._compare_items(a, b, sk))
            column = Gtk.ColumnViewColumn.new(title, factory)
            column.set_sorter(sorter)
            column.set_resizable(True)
            self.column_view.append_column(column)

    def _compare_items(self, a: ProcessGObject, b: ProcessGObject, sort_key_func) -> int:
        ka = sort_key_func(a)
        kb = sort_key_func(b)
        if ka < kb:
            return -1
        elif ka > kb:
            return 1
        return 0

    def _on_factory_setup(self, factory, item):
        label = Gtk.Label(xalign=0.0)
        label.set_margin_start(6)
        label.set_margin_end(6)
        item.set_child(label)

    def _on_factory_bind(self, item, str_func):
        obj: ProcessGObject = item.get_item()
        label: Gtk.Label = item.get_child()
        txt = str_func(obj)
        label.set_text(txt)

        # Highlight high CPU / memory processes visually
        if obj.cpu_percent >= self.high_cpu_threshold:
            label.add_css_class("error") # Red highlight accent
        elif obj.rss_bytes >= self.high_mem_threshold:
            label.add_css_class("warning") # Orange highlight accent
        else:
            label.remove_css_class("error")
            label.remove_css_class("warning")

    def _on_tree_toggled(self, btn):
        self.is_tree_view = btn.get_active()
        self.refresh_data()

    def get_selected_pids(self) -> List[int]:
        pids = []
        bitset = self.selection_model.get_selection()
        for i in range(bitset.get_size()):
            idx = bitset.get_nth(i)
            item: ProcessGObject = self.sort_model.get_item(idx)
            if item:
                pids.append(item.pid)
        return pids

    def _on_right_click(self, gesture, n_press, x, y):
        pids = self.get_selected_pids()
        if not pids:
            return

        menu = Gio.Menu()
        menu.append("Kill (SIGTERM)", "app.proc_kill")
        menu.append("Force Kill (SIGKILL)", "app.proc_force_kill")
        menu.append("Suspend (SIGSTOP)", "app.proc_suspend")
        menu.append("Resume (SIGCONT)", "app.proc_resume")
        menu.append("Renice Priority...", "app.proc_renice")

        section_inspect = Gio.Menu()
        section_inspect.append("Open File Location", "app.proc_open_loc")
        section_inspect.append("Copy PID(s)", "app.proc_copy_pid")
        section_inspect.append("View File Descriptors", "app.proc_view_fds")
        section_inspect.append("View Environment Variables", "app.proc_view_env")
        menu.append_section(None, section_inspect)

        popover = Gtk.PopoverMenu.new_from_model(menu)
        popover.set_parent(self.column_view)
        popover.set_pointing_to(Gdk.Rectangle(int(x), int(y), 1, 1))
        popover.popup()

    def action_kill(self, sig: int = signal.SIGTERM):
        pids = self.get_selected_pids()
        for pid in pids:
            success, msg = PrivilegeElevator.send_signal(pid, sig)
            print(f"Kill action PID {pid}: {msg}")
        self.refresh_data()

    def action_renice(self):
        pids = self.get_selected_pids()
        if not pids:
            return
        dialog = ReniceDialog(self.main_window, pids, 0, lambda val: self._apply_renice(pids, val))
        dialog.present()

    def _apply_renice(self, pids: List[int], val: int):
        for pid in pids:
            PrivilegeElevator.renice_process(pid, val)
        self.refresh_data()

    def action_open_loc(self):
        pids = self.get_selected_pids()
        if not pids:
            return
        binary_path = self.monitor.get_binary_path(pids[0])
        if binary_path and os.path.exists(binary_path):
            dir_path = os.path.dirname(binary_path)
            try:
                Gio.AppInfo.launch_default_for_uri(f"file://{dir_path}", None)
            except Exception:
                pass

    def action_copy_pid(self):
        pids = self.get_selected_pids()
        if pids:
            clipboard = self.get_clipboard()
            clipboard.set(str(pids[0]) if len(pids) == 1 else ", ".join(map(str, pids)))

    def action_view_fds(self):
        pids = self.get_selected_pids()
        if not pids:
            return
        pid = pids[0]
        fds = self.monitor.get_file_descriptors(pid)
        dialog = FdInspectorDialog(self.main_window, pid, str(pid), fds)
        dialog.present()

    def action_view_env(self):
        pids = self.get_selected_pids()
        if not pids:
            return
        pid = pids[0]
        env_vars = self.monitor.get_environment_vars(pid)
        dialog = EnvInspectorDialog(self.main_window, pid, str(pid), env_vars)
        dialog.present()

    def refresh_data(self):
        """Fetches latest process list from monitor and updates ListStore."""
        procs = self.monitor.update()

        # If Tree View is enabled, sort processes by PPID -> PID hierarchy
        if self.is_tree_view:
            tree_map: Dict[int, List[ProcessInfo]] = {}
            for p in procs:
                tree_map.setdefault(p.ppid, []).append(p)

            ordered: List[ProcessInfo] = []
            def walk(ppid: int, indent: int = 0):
                for child in tree_map.get(ppid, []):
                    child.name = ("  " * indent) + ("└─ " if indent > 0 else "") + child.name
                    ordered.append(child)
                    if child.pid != ppid: # avoid infinite loop
                        walk(child.pid, indent + 1)
            walk(0)
            procs = ordered

        self.store.remove_all()
        for p in procs:
            self.store.append(ProcessGObject(p))
