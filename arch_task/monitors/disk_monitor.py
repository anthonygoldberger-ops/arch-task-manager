import os
import time
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional

@dataclass
class DiskPartitionStats:
    device: str
    mountpoint: str
    fstype: str
    total_bytes: int = 0
    used_bytes: int = 0
    free_bytes: int = 0
    used_percent: float = 0.0

@dataclass
class DiskDriveStats:
    disk_name: str # e.g. sda, nvme0n1
    read_bytes_sec: float = 0.0
    write_bytes_sec: float = 0.0
    smart_status: str = "N/A"
    partitions: List[DiskPartitionStats] = field(default_factory=list)

class DiskMonitor:
    """Monitors disk drives, partitions, I/O rates (/proc/diskstats), and SMART health."""
    def __init__(self):
        self._prev_io: Dict[str, Tuple[int, int, float]] = {} # disk -> (read_bytes, write_bytes, timestamp)
        self._smartctl_cmd = self._find_smartctl()

    def _find_smartctl(self) -> Optional[str]:
        for path in ["/usr/bin/smartctl", "/bin/smartctl", "/usr/sbin/smartctl"]:
            if os.path.exists(path) and os.access(path, os.X_OK):
                return path
        return None

    def _get_mounts(self) -> List[DiskPartitionStats]:
        """Parses /proc/mounts and returns real physical filesystem partitions."""
        partitions = []
        skip_types = {
            'proc', 'sysfs', 'devtmpfs', 'devpts', 'tmpfs', 'overlay', 'squashfs',
            'cgroup', 'cgroup2', 'pstore', 'bpf', 'tracefs', 'hugetlbfs', 'mqueue',
            'configfs', 'ramfs', 'autofs', 'securityfs', 'efivarfs'
        }
        try:
            with open("/proc/mounts", "r") as f:
                lines = f.readlines()

            seen_mounts = set()
            for line in lines:
                parts = line.split()
                if len(parts) < 3:
                    continue
                dev, mp, fstype = parts[0], parts[1], parts[2]
                if fstype in skip_types or dev.startswith("nodev"):
                    continue
                if mp in seen_mounts:
                    continue
                seen_mounts.add(mp)

                try:
                    usage = shutil.disk_usage(mp)
                    p_stat = DiskPartitionStats(
                        device=dev,
                        mountpoint=mp,
                        fstype=fstype,
                        total_bytes=usage.total,
                        used_bytes=usage.used,
                        free_bytes=usage.free,
                        used_percent=round((usage.used / usage.total) * 100.0, 1) if usage.total > 0 else 0.0
                    )
                    partitions.append(p_stat)
                except Exception:
                    continue
        except Exception:
            pass
        return partitions

    def _check_smart(self, disk_name: str) -> str:
        """Queries smartctl -H /dev/<disk_name> if binary exists."""
        if not self._smartctl_cmd:
            return "smartctl not installed"
        try:
            dev_path = f"/dev/{disk_name}"
            cmd = [self._smartctl_cmd, "-H", dev_path]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
            out = res.stdout.upper()
            if "PASSED" in out or "OK" in out:
                return "PASSED"
            elif "FAILED" in out:
                return "CRITICAL FAILURE"
            else:
                return "UNKNOWN / NEED ROOT"
        except Exception:
            return "N/A"

    def update(self) -> List[DiskDriveStats]:
        """Reads /proc/diskstats and correlates disk I/O rates with partition mounts."""
        now = time.time()
        partitions = self._get_mounts()
        drives: Dict[str, DiskDriveStats] = {}

        try:
            with open("/proc/diskstats", "r") as f:
                lines = f.readlines()

            for line in lines:
                parts = line.split()
                if len(parts) < 14:
                    continue
                dev_name = parts[2]
                # Filter out loop devices and ramdisks
                if dev_name.startswith("loop") or dev_name.startswith("ram"):
                    continue

                # Only include major drive devices (sda, sdb, nvme0n1, mmcblk0)
                is_main_disk = False
                if (dev_name.startswith("sd") or dev_name.startswith("vd")) and dev_name[-1].isalpha():
                    is_main_disk = True
                elif ("nvme" in dev_name or "mmcblk" in dev_name) and "p" not in dev_name:
                    is_main_disk = True

                if is_main_disk:
                    sectors_read = int(parts[5])
                    sectors_written = int(parts[9])
                    read_bytes = sectors_read * 512
                    write_bytes = sectors_written * 512

                    r_rate = 0.0
                    w_rate = 0.0
                    if dev_name in self._prev_io:
                        pr_bytes, pw_bytes, p_time = self._prev_io[dev_name]
                        dt = now - p_time
                        if dt > 0.05:
                            r_rate = max(0.0, (read_bytes - pr_bytes) / dt)
                            w_rate = max(0.0, (write_bytes - pw_bytes) / dt)

                    self._prev_io[dev_name] = (read_bytes, write_bytes, now)

                    smart_status = self._check_smart(dev_name)
                    drive = DiskDriveStats(
                        disk_name=dev_name,
                        read_bytes_sec=r_rate,
                        write_bytes_sec=w_rate,
                        smart_status=smart_status
                    )
                    drives[dev_name] = drive

            # Match partitions to parent drives
            for part in partitions:
                matched = False
                for d_name, d_stat in drives.items():
                    if d_name in part.device:
                        d_stat.partitions.append(part)
                        matched = True
                        break
                if not matched and drives:
                    # fallback add to first drive
                    list(drives.values())[0].partitions.append(part)

        except Exception:
            pass

        return list(drives.values())
