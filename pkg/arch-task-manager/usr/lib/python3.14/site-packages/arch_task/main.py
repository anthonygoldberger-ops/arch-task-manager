import sys
import signal
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gio, GLib

from .ui.window import MainWindow
from . import __version__, __app_id__

class ArchTaskApplication(Adw.Application):
    """ArchTask GTK4/Libadwaita Application entry point."""
    def __init__(self):
        super().__init__(
            application_id=__app_id__,
            flags=Gio.ApplicationFlags.FLAGS_NONE
        )
        GLib.set_application_name("ArchTask")

    def do_startup(self):
        Adw.Application.do_startup(self)

        # Automatically follow system dark/light color scheme preference
        style_mgr = Adw.StyleManager.get_default()
        style_mgr.set_color_scheme(Adw.ColorScheme.PREFER_DARK)

        # Setup Simple Actions
        self._add_action("proc_kill", lambda a, p: self.window.process_view.action_kill(signal.SIGTERM))
        self._add_action("proc_force_kill", lambda a, p: self.window.process_view.action_kill(signal.SIGKILL))
        self._add_action("proc_suspend", lambda a, p: self.window.process_view.action_kill(signal.SIGSTOP))
        self._add_action("proc_resume", lambda a, p: self.window.process_view.action_kill(signal.SIGCONT))
        self._add_action("proc_renice", lambda a, p: self.window.process_view.action_renice())
        self._add_action("proc_open_loc", lambda a, p: self.window.process_view.action_open_loc())
        self._add_action("proc_copy_pid", lambda a, p: self.window.process_view.action_copy_pid())
        self._add_action("proc_view_fds", lambda a, p: self.window.process_view.action_view_fds())
        self._add_action("proc_view_env", lambda a, p: self.window.process_view.action_view_env())

        self._add_action("refresh_1s", lambda a, p: self.window.set_refresh_interval(1000))
        self._add_action("refresh_2s", lambda a, p: self.window.set_refresh_interval(2000))
        self._add_action("refresh_5s", lambda a, p: self.window.set_refresh_interval(5000))

        self._add_action("about", self._on_about)

    def _add_action(self, name, callback):
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", callback)
        self.add_action(action)

    def do_activate(self):
        if not hasattr(self, "window") or self.window is None:
            self.window = MainWindow(self)
        self.window.present()

    def _on_about(self, action, param):
        about = Adw.AboutWindow(
            transient_for=self.window,
            application_name="ArchTask",
            application_icon=__app_id__,
            developer_name="Arch Linux Systems Engineering",
            version=__version__,
            comments="Native, high-performance system and task manager designed specifically for Arch Linux.",
            website="https://archlinux.org",
            issue_tracker="https://github.com/archlinux/arch-task",
            copyright="© 2026 Arch Linux Community"
        )
        about.present()

def main():
    app = ArchTaskApplication()
    return app.run(sys.argv)

if __name__ == "__main__":
    sys.exit(main())
