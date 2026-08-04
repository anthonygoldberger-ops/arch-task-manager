import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Gio, Gdk

from .process_view import ProcessView
from .performance_view import PerformanceView
from .network_view import NetworkView
from .systemd_view import SystemdView
from .autostart_view import AutostartView
from ..utils.window_picker import WindowPicker
from ..utils.export import SnapshotExporter

class MainWindow(Adw.ApplicationWindow):
    """Main ArchTask application window with Adw.ViewStack navigation and auto-refresh timer."""
    def __init__(self, app: Adw.Application):
        super().__init__(application=app, title="ArchTask — System & Task Manager")
        self.set_default_size(1100, 750)

        self.refresh_interval_ms = 1500 # Default 1.5s
        self.timer_id = None

        # Main Layout Box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(main_box)

        # 1. Adw.HeaderBar with ViewSwitcher Title
        header = Adw.HeaderBar()
        main_box.append(header)

        # Stack Navigation
        self.stack = Adw.ViewStack()
        self.switcher_title = Adw.ViewSwitcherTitle(stack=self.stack, title="ArchTask")
        header.set_title_widget(self.switcher_title)

        # HeaderBar Left Buttons
        kill_win_btn = Gtk.Button(icon_name="crosshair-symbolic", tooltip_text="Kill by Window Click (Click target desktop window)")
        kill_win_btn.connect("clicked", self._on_kill_by_window)
        header.pack_start(kill_win_btn)

        export_btn = Gtk.Button(icon_name="document-save-symbolic", tooltip_text="Export Current System Snapshot (JSON / CSV)")
        export_btn.connect("clicked", self._on_export_snapshot)
        header.pack_start(export_btn)

        # HeaderBar Right Controls (Refresh Interval Menu)
        menu_btn = Gtk.MenuButton(icon_name="open-menu-symbolic")
        header.pack_end(menu_btn)

        app_menu = Gio.Menu()
        interval_section = Gio.Menu()
        interval_section.append("Refresh: 1s", "app.refresh_1s")
        interval_section.append("Refresh: 2s", "app.refresh_2s")
        interval_section.append("Refresh: 5s", "app.refresh_5s")
        app_menu.append_section("Update Rate", interval_section)

        misc_section = Gio.Menu()
        misc_section.append("About ArchTask", "app.about")
        app_menu.append_section(None, misc_section)

        menu_btn.set_menu_model(app_menu)

        # 2. Add Tab Pages to ViewStack
        self.process_view = ProcessView(self)
        self.stack.add_titled_with_icon(self.process_view, "processes", "Processes", "system-run-symbolic")

        self.performance_view = PerformanceView(self)
        self.stack.add_titled_with_icon(self.performance_view, "performance", "Performance", "utilities-system-monitor-symbolic")

        self.network_view = NetworkView(self)
        self.stack.add_titled_with_icon(self.network_view, "network", "Network Sockets", "network-workgroup-symbolic")

        self.systemd_view = SystemdView(self)
        self.stack.add_titled_with_icon(self.systemd_view, "systemd", "Systemd Services", "system-component-application-symbolic")

        self.autostart_view = AutostartView(self)
        self.stack.add_titled_with_icon(self.autostart_view, "autostart", "Startup Apps", "system-log-out-symbolic")

        main_box.append(self.stack)

        # Bottom ViewSwitcherBar for narrower screens
        switcher_bar = Adw.ViewSwitcherBar(stack=self.stack)
        main_box.append(switcher_bar)

        # Connect Stack page switch event
        self.stack.connect("notify::visible-child", lambda s, p: self._trigger_refresh())

        # Setup Keyboard Shortcuts
        self._setup_keyboard_shortcuts()

        # Start periodic data timer
        self._start_timer()
        self._trigger_refresh()

    def _setup_keyboard_shortcuts(self):
        controller = Gtk.EventControllerKey.new()
        controller.connect("key-pressed", self._on_key_pressed)
        self.add_controller(controller)

    def _on_key_pressed(self, controller, keyval, keycode, state):
        ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)

        if ctrl and keyval == Gdk.KEY_f: # Ctrl+F -> Focus Search Box
            page = self.stack.get_visible_child()
            if hasattr(page, "search_entry"):
                page.search_entry.grab_focus()
                return True
        elif ctrl and keyval == Gdk.KEY_r: # Ctrl+R -> Force Refresh
            self._trigger_refresh()
            return True
        elif keyval in (Gdk.KEY_Delete, Gdk.KEY_KP_Delete): # Delete -> Terminate selected process
            if self.stack.get_visible_child() == self.process_view:
                self.process_view.action_kill()
                return True
        return False

    def _start_timer(self):
        if self.timer_id:
            GLib.source_remove(self.timer_id)
        self.timer_id = GLib.timeout_add(self.refresh_interval_ms, self._on_timer_tick)

    def _on_timer_tick(self) -> bool:
        self._trigger_refresh()
        return True # Keep repeating

    def _trigger_refresh(self):
        visible = self.stack.get_visible_child()
        if hasattr(visible, "refresh_data"):
            try:
                visible.refresh_data()
            except Exception as e:
                print(f"Error refreshing tab {visible}: {e}")

    def set_refresh_interval(self, ms: int):
        self.refresh_interval_ms = ms
        self._start_timer()

    def _on_kill_by_window(self, btn):
        pid, msg = WindowPicker.pick_window_pid()
        if pid:
            self.stack.set_visible_child(self.process_view)
            self.process_view.search_entry.set_text(str(pid))
            self._trigger_refresh()

            # Show dialog confirming kill
            dialog = Adw.MessageDialog(
                transient_for=self,
                heading=f"Terminate Target Window (PID {pid})?",
                body=f"Identified owning window process PID {pid}.\nWould you like to send SIGTERM signal?"
            )
            dialog.add_response("cancel", "Cancel")
            dialog.add_response("kill", "Kill Process")
            dialog.set_response_appearance("kill", Adw.ResponseAppearance.DESTRUCTIVE)
            dialog.connect("response", lambda d, r: self.process_view.action_kill() if r == "kill" else None)
            dialog.present()
        else:
            toast = Adw.Toast.new(msg)
            # Find toast overlay or alert user
            print(f"Window picker: {msg}")

    def _on_export_snapshot(self, btn):
        file_dialog = Gtk.FileChooserNative.new(
            title="Export System Snapshot",
            parent=self,
            action=Gtk.FileChooserAction.SAVE,
            accept_label="Export",
            cancel_label="Cancel"
        )

        filter_json = Gtk.FileFilter()
        filter_json.set_name("JSON Files (*.json)")
        filter_json.add_pattern("*.json")
        file_dialog.add_filter(filter_json)

        filter_csv = Gtk.FileFilter()
        filter_csv.set_name("CSV Files (*.csv)")
        filter_csv.add_pattern("*.csv")
        file_dialog.add_filter(filter_csv)

        def on_response(dialog, response_id):
            if response_id == Gtk.ResponseType.ACCEPT:
                gfile = file_dialog.get_file()
                if gfile:
                    path = gfile.get_path()
                    procs = self.process_view.monitor.update()
                    cpu = self.performance_view.cpu_mon.update()
                    mem = self.performance_view.mem_mon.update()

                    if path.endswith(".csv"):
                        ok = SnapshotExporter.export_to_csv(path, procs)
                    else:
                        if not path.endswith(".json"):
                            path += ".json"
                        ok = SnapshotExporter.export_to_json(path, procs, cpu, mem)
                    print(f"Export snapshot to {path}: {'Success' if ok else 'Failed'}")

        file_dialog.connect("response", on_response)
        file_dialog.present()
