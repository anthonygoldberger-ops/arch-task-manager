import subprocess
from dataclasses import dataclass
from typing import List, Tuple, Optional

@dataclass
class SystemdUnitInfo:
    unit_name: str
    load_state: str
    active_state: str
    sub_state: str
    description: str
    scope: str # "system" or "user"

class SystemdMonitor:
    """Monitors and manages Systemd units (system and user scope) and retrieves journal logs."""
    def list_units(self, scope: str = "system") -> List[SystemdUnitInfo]:
        """Runs systemctl list-units for specified scope."""
        units: List[SystemdUnitInfo] = []
        cmd = ["systemctl"]
        if scope == "user":
            cmd.append("--user")
        cmd.extend(["list-units", "--all", "--no-legend", "--no-pager"])

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                for line in res.stdout.strip().splitlines():
                    parts = line.split(maxsplit=4)
                    if len(parts) >= 4:
                        unit_name = parts[0]
                        load_state = parts[1]
                        active_state = parts[2]
                        sub_state = parts[3]
                        desc = parts[4] if len(parts) > 4 else ""
                        units.append(SystemdUnitInfo(
                            unit_name=unit_name,
                            load_state=load_state,
                            active_state=active_state,
                            sub_state=sub_state,
                            description=desc,
                            scope=scope
                        ))
        except Exception:
            pass
        return units

    def get_unit_logs(self, unit_name: str, scope: str = "system", lines: int = 100) -> str:
        """Retrieves recent journal logs for a unit via journalctl."""
        cmd = ["journalctl", "-u", unit_name, "-n", str(lines), "--no-pager"]
        if scope == "user":
            cmd.insert(1, "--user")
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
            return res.stdout if res.stdout else "No log records found for this unit."
        except Exception as e:
            return f"Failed to retrieve logs: {e}"

    def control_unit(self, unit_name: str, action: str, scope: str = "system") -> Tuple[bool, str]:
        """
        Executes action (start, stop, restart, enable, disable) on a systemd unit.
        For system scope, uses pkexec systemctl if not running as root.
        """
        valid_actions = {"start", "stop", "restart", "enable", "disable"}
        if action not in valid_actions:
            return False, "Invalid unit action"

        cmd = []
        if scope == "system":
            # Check if running as root or need pkexec
            import os
            if os.geteuid() != 0:
                cmd = ["pkexec", "systemctl", action, unit_name]
            else:
                cmd = ["systemctl", action, unit_name]
        else:
            cmd = ["systemctl", "--user", action, unit_name]

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if res.returncode == 0:
                return True, f"Successfully executed '{action}' on {unit_name}"
            else:
                return False, res.stderr or f"Command returned exit code {res.returncode}"
        except Exception as e:
            return False, str(e)
