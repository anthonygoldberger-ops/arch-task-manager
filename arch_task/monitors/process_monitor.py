import os
import time
import pwd
import glob
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# Get system clock ticks per second (usually 100 on Linux)
CLK_TCK = os.sysconf(os.sysconf_names.get('SC_CLK_TCK', 100))
PAGE_SIZE = os.sysconf(os.sysconf_names.get('SC_PAGE_SIZE', 4096))
SYSTEM_UPTIME_FILE = '/proc/uptime'

def get_system_uptime() -> float:
    """Reads system uptime in seconds from /proc/uptime."""
    try:
        with open(SYSTEM_UPTIME_FILE, 'r') as f:
            return float(f.read().split()[0])
    except Exception:
        return time.time()

@dataclass
class ProcessInfo:
    pid: int
    ppid: int
    name: str
    user: str
    state: str
    cpu_percent: float = 0.0
    rss_bytes: int = 0
    vsize_bytes: int = 0
    read_bytes_sec: float = 0.0
    write_bytes_sec: float = 0.0
    nice: int = 0
    threads: int = 1
    start_time_str: str = ""
    cmdline: str = ""
    binary_path: str = ""

    # Internal metrics state for delta calculations
    _utime: float = 0.0
    _stime: float = 0.0
    _timestamp: float = 0.0
    _read_bytes: int = 0
    _write_bytes: int = 0

class ProcessMonitor:
    """Monitors running Linux processes directly via /proc filesystem."""
    def __init__(self):
        self._prev_stats: Dict[int, ProcessInfo] = {}
        self._user_cache: Dict[int, str] = {}
        self.num_cpus = os.cpu_count() or 1

    def _get_username(self, uid: int) -> str:
        if uid not in self._user_cache:
            try:
                self._user_cache[uid] = pwd.getpwuid(uid).pw_name
            except Exception:
                self._user_cache[uid] = str(uid)
        return self._user_cache[uid]

    def _parse_proc_stat(self, pid: int) -> Optional[dict]:
        """
        Parses /proc/[pid]/stat.
        Format: pid (comm) state ppid pgrp session tty_nr tpgid flags minflt cminflt
        majflt cmajflt utime stime cutime cstime priority nice num_threads itrealvalue
        starttime vsize rss ...
        Note: comm can contain spaces and parentheses, so we parsecomm by finding
        the first '(' and the last ')'.
        """
        try:
            with open(f"/proc/{pid}/stat", "r") as f:
                content = f.read()

            lparen = content.find('(')
            rparen = content.rfind(')')
            if lparen == -1 or rparen == -1 or rparen <= lparen:
                return None

            name = content[lparen + 1:rparen]
            rest = content[rparen + 2:].split()

            state = rest[0]
            ppid = int(rest[1])
            utime = float(rest[11]) / CLK_TCK
            stime = float(rest[12]) / CLK_TCK
            priority = int(rest[15])
            nice = int(rest[16])
            num_threads = int(rest[17])
            starttime = float(rest[19]) / CLK_TCK
            vsize = int(rest[20])
            rss = int(rest[21]) * PAGE_SIZE

            return {
                "name": name,
                "state": state,
                "ppid": ppid,
                "utime": utime,
                "stime": stime,
                "nice": nice,
                "num_threads": num_threads,
                "starttime": starttime,
                "vsize": vsize,
                "rss": rss
            }
        except Exception:
            return None

    def _parse_proc_status_uid(self, pid: int) -> int:
        """Parses real UID from /proc/[pid]/status."""
        try:
            with open(f"/proc/{pid}/status", "r") as f:
                for line in f:
                    if line.startswith("Uid:"):
                        parts = line.split()
                        return int(parts[1])
        except Exception:
            pass
        return 0

    def _parse_proc_cmdline(self, pid: int) -> str:
        """Reads null-separated command line from /proc/[pid]/cmdline."""
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as f:
                raw = f.read()
                if not raw:
                    return ""
                parts = raw.split(b'\x00')
                return " ".join([p.decode('utf-8', errors='replace') for p in parts if p])
        except Exception:
            return ""

    def _parse_proc_io(self, pid: int) -> Tuple[int, int]:
        """Reads read_bytes and write_bytes from /proc/[pid]/io (requires same user or root)."""
        read_bytes = 0
        write_bytes = 0
        try:
            with open(f"/proc/{pid}/io", "r") as f:
                for line in f:
                    if line.startswith("read_bytes:"):
                        read_bytes = int(line.split()[1])
                    elif line.startswith("write_bytes:"):
                        write_bytes = int(line.split()[1])
        except Exception:
            pass
        return read_bytes, write_bytes

    def get_binary_path(self, pid: int) -> str:
        """Resolves target of /proc/[pid]/exe symbolic link."""
        try:
            return os.readlink(f"/proc/{pid}/exe")
        except Exception:
            return ""

    def get_file_descriptors(self, pid: int) -> List[Tuple[str, str]]:
        """Returns list of (fd_num, target_path) for given process."""
        fds = []
        fd_dir = f"/proc/{pid}/fd"
        try:
            if os.path.exists(fd_dir):
                for entry in os.listdir(fd_dir):
                    fd_path = os.path.join(fd_dir, entry)
                    try:
                        target = os.readlink(fd_path)
                        fds.append((entry, target))
                    except Exception:
                        fds.append((entry, "unknown"))
        except Exception as e:
            fds.append(("error", f"Permission denied or process exited: {e}"))
        fds.sort(key=lambda x: int(x[0]) if x[0].isdigit() else 999999)
        return fds

    def get_environment_vars(self, pid: int) -> Dict[str, str]:
        """Parses null-separated environment variables from /proc/[pid]/environ."""
        env = {}
        try:
            with open(f"/proc/{pid}/environ", "rb") as f:
                raw = f.read()
                entries = raw.split(b'\x00')
                for item in entries:
                    if not item:
                        continue
                    decoded = item.decode('utf-8', errors='replace')
                    if '=' in decoded:
                        k, v = decoded.split('=', 1)
                        env[k] = v
        except Exception as e:
            env["ERROR"] = f"Permission denied: {e}"
        return env

    def update(self) -> List[ProcessInfo]:
        """Scans /proc and computes updated process metrics."""
        now = time.time()
        uptime = get_system_uptime()
        current_stats: Dict[int, ProcessInfo] = {}
        pids = []

        for entry in os.listdir('/proc'):
            if entry.isdigit():
                pids.append(int(entry))

        results: List[ProcessInfo] = []

        for pid in pids:
            stat = self._parse_proc_stat(pid)
            if not stat:
                continue

            uid = self._parse_proc_status_uid(pid)
            user = self._get_username(uid)
            cmdline = self._parse_proc_cmdline(pid)
            read_bytes, write_bytes = self._parse_proc_io(pid)

            # Start time calculation
            process_start_sec = uptime - stat["starttime"]
            if process_start_sec > 86400:
                days = int(process_start_sec // 86400)
                start_str = f"{days}d ago"
            elif process_start_sec > 3600:
                hours = int(process_start_sec // 3600)
                start_str = f"{hours}h ago"
            else:
                mins = int(process_start_sec // 60)
                start_str = f"{mins}m ago"

            proc_info = ProcessInfo(
                pid=pid,
                ppid=stat["ppid"],
                name=stat["name"],
                user=user,
                state=stat["state"],
                rss_bytes=stat["rss"],
                vsize_bytes=stat["vsize"],
                nice=stat["nice"],
                threads=stat["num_threads"],
                start_time_str=start_str,
                cmdline=cmdline or stat["name"],
                _utime=stat["utime"],
                _stime=stat["stime"],
                _timestamp=now,
                _read_bytes=read_bytes,
                _write_bytes=write_bytes
            )

            # Calculate delta CPU % and Disk I/O rates if previous sample exists
            if pid in self._prev_stats:
                prev = self._prev_stats[pid]
                dt = now - prev._timestamp
                if dt > 0.05:
                    total_time = (proc_info._utime + proc_info._stime) - (prev._utime + prev._stime)
                    # Standard CPU % (scaled across all cores, max 100% * num_cpus)
                    proc_info.cpu_percent = round((total_time / dt) * 100.0, 1)

                    r_delta = proc_info._read_bytes - prev._read_bytes
                    w_delta = proc_info._write_bytes - prev._write_bytes
                    proc_info.read_bytes_sec = max(0.0, r_delta / dt)
                    proc_info.write_bytes_sec = max(0.0, w_delta / dt)

            current_stats[pid] = proc_info
            results.append(proc_info)

        self._prev_stats = current_stats
        return results
