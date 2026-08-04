import os
import glob
import subprocess
from dataclasses import dataclass
from typing import List, Tuple

@dataclass
class AutostartItem:
    name: str
    entry_type: str # "XDG Autostart" or "Systemd User Service"
    file_path: str
    enabled: bool
    command_or_desc: str

class AutostartMonitor:
    """Monitors XDG desktop autostart entries and systemd user services."""
    def update(self) -> List[AutostartItem]:
        items: List[AutostartItem] = []

        # 1. Collect XDG Autostart desktop entries
        user_autostart = os.path.expanduser("~/.config/autostart")
        sys_autostart = "/etc/xdg/autostart"

        paths = []
        if os.path.exists(user_autostart):
            paths.extend(glob.glob(f"{user_autostart}/*.desktop"))
        if os.path.exists(sys_autostart):
            paths.extend(glob.glob(f"{sys_autostart}/*.desktop"))

        seen_names = set()
        for path in paths:
            try:
                name = os.path.basename(path)
                if name in seen_names:
                    continue
                seen_names.add(name)

                entry_name = name
                cmd = ""
                enabled = True

                with open(path, "r", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("Name="):
                            entry_name = line.split("=", 1)[1]
                        elif line.startswith("Exec="):
                            cmd = line.split("=", 1)[1]
                        elif line.startswith("X-GNOME-Autostart-enabled="):
                            val = line.split("=", 1)[1].lower()
                            if val in ("false", "0"):
                                enabled = False
                        elif line.startswith("Hidden="):
                            val = line.split("=", 1)[1].lower()
                            if val in ("true", "1"):
                                enabled = False

                items.append(AutostartItem(
                    name=entry_name,
                    entry_type="XDG Autostart",
                    file_path=path,
                    enabled=enabled,
                    command_or_desc=cmd
                ))
            except Exception:
                continue

        # 2. Collect Systemd User Services
        try:
            cmd = ["systemctl", "--user", "list-unit-files", "--type=service", "--no-legend", "--no-pager"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
            if res.returncode == 0:
                for line in res.stdout.strip().splitlines():
                    parts = line.split()
                    if len(parts) >= 2:
                        service_name = parts[0]
                        state = parts[1]
                        items.append(AutostartItem(
                            name=service_name,
                            entry_type="Systemd User Service",
                            file_path=service_name,
                            enabled=(state == "enabled"),
                            command_or_desc=f"Systemd User Unit ({state})"
                        ))
        except Exception:
            pass

        return items

    def toggle_item(self, item: AutostartItem) -> Tuple[bool, str]:
        """Toggles enabled status for XDG desktop file or systemd user service."""
        if item.entry_type == "XDG Autostart":
            try:
                new_state = not item.enabled
                user_autostart = os.path.expanduser("~/.config/autostart")
                os.makedirs(user_autostart, exist_ok=True)
                target_file = os.path.join(user_autostart, os.path.basename(item.file_path))

                content_lines = []
                if os.path.exists(target_file):
                    with open(target_file, "r") as f:
                        content_lines = f.readlines()
                elif os.path.exists(item.file_path):
                    with open(item.file_path, "r") as f:
                        content_lines = f.readlines()

                # Modify or append X-GNOME-Autostart-enabled
                updated = False
                new_lines = []
                for line in content_lines:
                    if line.startswith("X-GNOME-Autostart-enabled="):
                        new_lines.append(f"X-GNOME-Autostart-enabled={'true' if new_state else 'false'}\n")
                        updated = True
                    else:
                        new_lines.append(line)
                if not updated:
                    new_lines.append(f"X-GNOME-Autostart-enabled={'true' if new_state else 'false'}\n")

                with open(target_file, "w") as f:
                    f.writelines(new_lines)

                return True, f"Updated {item.name} autostart state"
            except Exception as e:
                return False, str(e)
        elif item.entry_type == "Systemd User Service":
            try:
                action = "disable" if item.enabled else "enable"
                cmd = ["systemctl", "--user", action, item.file_path]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                if res.returncode == 0:
                    return True, f"Successfully executed '{action}' on {item.file_path}"
                else:
                    return False, res.stderr or "Failed to change service state"
            except Exception as e:
                return False, str(e)
        return False, "Unknown item type"
