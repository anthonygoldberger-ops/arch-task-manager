import os
import subprocess
from typing import Optional, Tuple

class WindowPicker:
    """Utility to interactively pick an on-screen window and locate its owning process PID."""
    @staticmethod
    def pick_window_pid() -> Tuple[Optional[int], str]:
        """
        Attempts to prompt the user to click a window on screen and extracts its PID.
        Supports X11 (via xprop/xwininfo) and Hyprland/Sway (via hyprctl/swaymsg).
        Returns (pid, status_message).
        """
        xdg_session = os.environ.get("XDG_SESSION_TYPE", "").lower()

        # Try X11 / xprop approach
        xprop_cmd = subprocess.run(["which", "xprop"], capture_output=True, text=True)
        if xprop_cmd.returncode == 0:
            try:
                res = subprocess.run(["xprop", "_NET_WM_PID"], capture_output=True, text=True, timeout=10)
                if res.returncode == 0 and "_NET_WM_PID" in res.stdout:
                    parts = res.stdout.strip().split("=")
                    if len(parts) >= 2:
                        pid = int(parts[1].strip())
                        return pid, f"Successfully targeted window PID {pid}"
            except Exception:
                pass

        # Try Hyprland (Wayland)
        hypr_cmd = subprocess.run(["which", "hyprctl"], capture_output=True, text=True)
        if hypr_cmd.returncode == 0:
            try:
                import json
                res = subprocess.run(["hyprctl", "activewindow", "-j"], capture_output=True, text=True, timeout=3)
                if res.returncode == 0 and res.stdout:
                    data = json.loads(res.stdout)
                    pid = data.get("pid")
                    if pid:
                        return int(pid), f"Active Hyprland window PID: {pid}"
            except Exception:
                pass

        # Try Sway (Wayland)
        sway_cmd = subprocess.run(["which", "swaymsg"], capture_output=True, text=True)
        if sway_cmd.returncode == 0:
            try:
                import json
                res = subprocess.run(["swaymsg", "-t", "get_tree"], capture_output=True, text=True, timeout=3)
                if res.returncode == 0 and res.stdout:
                    tree = json.loads(res.stdout)
                    pid = WindowPicker._find_focused_sway_node(tree)
                    if pid:
                        return pid, f"Active Sway window PID: {pid}"
            except Exception:
                pass

        if "wayland" in xdg_session:
            return None, "Click-to-kill under Wayland requires compositor window tools (e.g. hyprctl, swaymsg, or xprop under XWayland)."
        return None, "Click-to-kill requires 'xorg-xprop' package or compatible Wayland compositor tool."

    @staticmethod
    def _find_focused_sway_node(node: dict) -> Optional[int]:
        if node.get("focused") and node.get("pid"):
            return node.get("pid")
        for child in node.get("nodes", []) + node.get("floating_nodes", []):
            res = WindowPicker._find_focused_sway_node(child)
            if res:
                return res
        return None
