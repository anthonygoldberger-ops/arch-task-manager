import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw

from ..monitors.autostart_monitor import AutostartMonitor, AutostartItem

class AutostartView(Gtk.Box):
    """Startup / Autostart Manager tab for toggling XDG desktop entries and systemd user services."""
    def __init__(self, main_window: Gtk.Window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.main_window = main_window
        self.monitor = AutostartMonitor()

        self.set_margin_start(8)
        self.set_margin_end(8)
        self.set_margin_top(8)
        self.set_margin_bottom(8)

        # Search Bar
        top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.append(top_bar)

        self.search_entry = Gtk.SearchEntry(placeholder_text="Search startup entries by name or command...")
        self.search_entry.set_hexpand(True)
        top_bar.append(self.search_entry)

        # List Scrolled Area
        scrolled = Gtk.ScrolledWindow(vexpand=True)
        self.append(scrolled)

        clamp = Adw.Clamp(maximum_size=900)
        scrolled.set_child(clamp)

        self.pref_group = Adw.PreferencesGroup(title="Login Autostart Entries", description="Toggle applications and services launched automatically at session startup")
        clamp.set_child(self.pref_group)

    def refresh_data(self):
        items = self.monitor.update()

        # Remove existing rows
        child = self.pref_group.get_first_child()
        while child:
            next_c = child.get_next_sibling()
            self.pref_group.remove(child)
            child = next_c

        query = self.search_entry.get_text().strip().lower()

        for item in items:
            if query and query not in f"{item.name} {item.entry_type} {item.command_or_desc}".lower():
                continue

            row = Adw.ActionRow(title=item.name, subtitle=f"[{item.entry_type}] {item.command_or_desc}")
            switch = Gtk.Switch(active=item.enabled, valign=Gtk.Align.CENTER)
            switch.connect("notify::active", lambda s, pspec, itm=item: self._on_toggle(itm, s.get_active()))
            row.add_suffix(switch)
            self.pref_group.add(row)

    def _on_toggle(self, item: AutostartItem, new_state: bool):
        if item.enabled != new_state:
            success, msg = self.monitor.toggle_item(item)
            item.enabled = new_state
            print(f"Autostart toggle {item.name}: {msg}")
