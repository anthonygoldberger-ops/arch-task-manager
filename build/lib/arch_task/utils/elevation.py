import os
import signal
import subprocess
from typing import Tuple

class PrivilegeElevator:
    """Manages process signal killing and renicing with Polkit pkexec fallback for privileged operations."""
    @staticmethod
    def send_signal(pid: int, sig: int) -> Tuple[bool, str]:
        """
        Sends a signal (SIGTERM, SIGKILL, SIGSTOP, SIGCONT) to a PID.
        Falls back to pkexec kill -<sig> <pid> if unprivileged.
        """
        try:
            os.kill(pid, sig)
            return True, f"Signal {sig} sent to PID {pid}"
        except PermissionError:
            # Requires elevated privileges
            sig_num = int(sig)
            cmd = ["pkexec", "kill", f"-{sig_num}", str(pid)]
            try:
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if res.returncode == 0:
                    return True, f"Successfully sent signal {sig} to PID {pid} via pkexec"
                else:
                    return False, res.stderr or "Polkit authorization failed or command rejected"
            except Exception as e:
                return False, f"Failed to execute pkexec: {e}"
        except ProcessLookupError:
            return False, f"Process {pid} no longer exists"
        except Exception as e:
            return False, str(e)

    @staticmethod
    def renice_process(pid: int, new_nice: int) -> Tuple[bool, str]:
        """
        Changes nice value for a process.
        Falls back to pkexec renice if decreasing nice value or unprivileged.
        """
        try:
            os.setpriority(os.PRIO_PROCESS, pid, new_nice)
            return True, f"Reniced PID {pid} to {new_nice}"
        except PermissionError:
            cmd = ["pkexec", "renice", "-n", str(new_nice), "-p", str(pid)]
            try:
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if res.returncode == 0:
                    return True, f"Successfully reniced PID {pid} to {new_nice} via pkexec"
                else:
                    return False, res.stderr or "Polkit authorization failed"
            except Exception as e:
                return False, f"Failed to execute pkexec renice: {e}"
        except Exception as e:
            return False, str(e)
