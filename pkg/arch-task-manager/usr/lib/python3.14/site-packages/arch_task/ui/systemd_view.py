import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GObject, Gio

from ..monitors.systemd_monitor import SystemdMonitor, SystemdUnitInfo

class SystemdView(Gtk.Box):
    """Systemd tab managing system and user scope units and viewing journalctl logs."""
    def __init__(self, main_window: Gtk.Window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.main_window = main_window
        self.monitor = SystemdMonitor()
        self.current_scope = "system"
        self.selected_unit: Optional[SystemdUnitInfo] = None

        self.set_margin_start(8)
        self.set_margin_end(8)
        self.set_margin_top(8)
        self.set_margin_bottom(8)

        # 1. Controls (Scope Toggle + Search)
        top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.append(top_bar)

        self.scope_stack = Gtk.DropDown.new_from_strings(["System Scope (Root/Polkit)", "User Scope"])
        self.scope_stack.connect("notify::selected", self._on_scope_changed)
        top_bar.append(self.scope_stack)

        self.search_entry = Gtk.SearchEntry(placeholder_text="Search systemd units by name or status...")
        self.search_entry.set_hexpand(True)
        top_bar.append(self.search_entry)

        # 2. Main Paned Layout (Unit List on Left, Control & Logs on Right)
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_shrink_start_child(False)
        paned.set_shrink_end_child(False)
        paned.set_position(450)
        self.append(paned)

        # Left: Unit List
        left_scrolled = Gtk.ScrolledWindow(vexpand=True)
        paned.set_start_child(left_scrolled)

        self.unit_list = Gtk.ListBox(css_classes=["boxed-list"])
        self.unit_list.connect("row-selected", self._on_unit_selected)
        left_scrolled.set_child(self.unit_list)

        self.unit_list.set_filter_func(self._filter_unit)
        self.search_entry.connect("search-changed", lambda e: self.unit_list.invalidate_filter())

        # Right: Action Buttons + Journal Logs
        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        right_box.set_margin_start(12)
        right_box.set_margin_end(12)
        paned.set_end_child(right_box)

        # Unit Title Banner & Actions
        self.unit_header = Adw.ActionRow(title="Select a Unit", subtitle="Choose a unit to view details and logs")
        right_box.append(self.unit_header)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        right_box.append(btn_box)

        for act in ["Start", "Stop", "Restart", "Enable", "Disable"]:
            btn = Gtk.Button(label=act)
            btn.connect("clicked", lambda b, a=act.lower(): self._on_unit_action(a))
            btn_box.append(btn)

        # Journalctl Log Viewer
        log_frame = Gtk.Frame(label="Recent Journal Logs (journalctl -u <unit> -n 100)")
        log_frame.set_vexpand(True)
        right_box.append(log_frame)

        log_scroll = Gtk.ScrolledWindow()
        log_frame.set_child(log_scroll)

        self.log_text = Gtk.TextView(editable=False, monospace=True, wrap_mode=Gtk.WrapMode.WORD)
        self.log_text.set_margin_start(6)
        self.log_text.set_margin_end(6)
        self.log_text.set_margin_top(6)
        self.log_text.set_margin_bottom(6)
        log_scroll.set_child(self.log_text)

    def _on_scope_changed(self, dropdown, pspec):
        idx = dropdown.get_selected()
        self.current_scope = "system" if idx == 0 else "user"
        self.refresh_data()

    def _filter_unit(self, row) -> bool:
        query = self.search_entry.get_text().strip().lower()
        if not query:
            return True
        unit: SystemdUnitInfo = getattr(row, "_unit_info", None)
        if not unit:
            return True
        text = f"{unit.unit_name} {unit.active_state} {unit.sub_state} {unit.description}".lower()
        return query in text

    def _on_unit_selected(self, listbox, row):
        if not row:
            return
        unit: SystemdUnitInfo = getattr(row, "_unit_info", None)
        if not unit:
            return
        self.selected_unit = unit
        self.unit_header.set_title(unit.unit_name)
        self.unit_header.set_subtitle(f"State: {unit.active_state} ({unit.sub_state}) | {unit.description}")

        # Fetch logs
        logs = self.monitor.get_unit_logs(unit.unit_name, scope=self.current_scope)
        self.log_text.get_buffer().set_text(logs)

    def _on_unit_action(self, action: str):
        if not self.selected_unit:
            return
        success, msg = self.monitor.control_unit(self.selected_unit.unit_name, action, scope=self.current_scope)
        print(f"Systemd Action {action} on {self.selected_unit.unit_name}: {msg}")
        self.refresh_data()

    def refresh_data(self):
        units = self.monitor.list_units(scope=self.current_scope)

        # Clear existing list
        child = self.unit_list.get_first_child()
        while child:
            next_c = child.get_next_sibling()
            self.unit_list.remove(child)
            child = next_c

        for u in units:
            row = Adw.ActionRow(title=u.unit_name, subtitle=f"{u.active_state} ({u.sub_state}) — {u.description}")
            row._unit_info = u
            if u.active_state == "failed":
                row.add_css_class("error")
            elif u.active_state == "active":
                row.add_css_class("accent")
            self.unit_list.append(row)
