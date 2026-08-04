import os
import glob
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional

@dataclass
class CpuCoreStats:
    core_id: int
    usage_percent: float = 0.0
    freq_mhz: float = 0.0

@dataclass
class CpuSystemStats:
    model_name: str = "Unknown CPU"
    num_cores: int = 1
    total_usage_percent: float = 0.0
    load_avg: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    temperature_c: float = 0.0
    cache_info: Dict[str, str] = field(default_factory=dict)
    cores: List[CpuCoreStats] = field(default_factory=list)

class CpuMonitor:
    """Monitors CPU metrics via /proc/stat, /proc/cpuinfo, /proc/loadavg, and /sys/devices/system/cpu."""
    def __init__(self):
        self._prev_times: Dict[str, Tuple[float, float]] = {} # key -> (idle_time, total_time)
        self.model_name = self._parse_model_name()
        self.cache_info = self._parse_cache_info()

    def _parse_model_name(self) -> str:
        """Reads CPU model name from /proc/cpuinfo."""
        try:
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if line.startswith("model name"):
                        return line.split(":", 1)[1].strip()
        except Exception:
            pass
        return "Generic Linux Processor"

    def _parse_cache_info(self) -> Dict[str, str]:
        """Reads CPU L1, L2, L3 cache sizes from /sys/devices/system/cpu/cpu0/cache."""
        caches = {}
        try:
            base_dir = "/sys/devices/system/cpu/cpu0/cache"
            if os.path.exists(base_dir):
                for idx_dir in glob.glob(f"{base_dir}/index*"):
                    try:
                        with open(f"{idx_dir}/level", "r") as fl:
                            level = fl.read().strip()
                        with open(f"{idx_dir}/type", "r") as ft:
                            ctype = ft.read().strip()
                        with open(f"{idx_dir}/size", "r") as fs:
                            size = fs.read().strip()
                        key = f"L{level} {ctype}"
                        caches[key] = size
                    except Exception:
                        continue
        except Exception:
            pass
        return caches

    def _get_temperature(self) -> float:
        """Finds CPU package temperature in /sys/class/thermal or /sys/class/hwmon."""
        # 1. Check CPU thermal zones
        try:
            for tz in sorted(glob.glob("/sys/class/thermal/thermal_zone*")):
                try:
                    with open(f"{tz}/type", "r") as f:
                        ttype = f.read().strip().lower()
                    if "x86_pkg_temp" in ttype or "cpu" in ttype or "acpitz" in ttype or "k10temp" in ttype:
                        with open(f"{tz}/temp", "r") as f:
                            val = float(f.read().strip()) / 1000.0
                            if 0 < val < 130:
                                return val
                except Exception:
                    continue
        except Exception:
            pass

        # 2. Check hwmon CPU chip sensors (coretemp, k10temp, zenpower, cpu)
        fallback_temp = 0.0
        try:
            for hwmon in sorted(glob.glob("/sys/class/hwmon/hwmon*")):
                name_path = f"{hwmon}/name"
                name = ""
                try:
                    if os.path.exists(name_path):
                        with open(name_path, "r") as f:
                            name = f.read().strip().lower()

                    for temp_input in sorted(glob.glob(f"{hwmon}/temp*_input")):
                        try:
                            with open(temp_input, "r") as f:
                                val = float(f.read().strip()) / 1000.0
                                if 10.0 < val < 130.0:
                                    if "coretemp" in name or "k10temp" in name or "zenpower" in name or "cpu" in name:
                                        return val
                                    elif fallback_temp == 0.0:
                                        fallback_temp = val
                        except Exception:
                            continue
                except Exception:
                    continue
        except Exception:
            pass

        return fallback_temp

    def _get_freq_mhz(self, core_id: int) -> float:
        """Reads current frequency for given core from sysfs."""
        try:
            freq_path = f"/sys/devices/system/cpu/cpu{core_id}/cpufreq/scaling_cur_freq"
            if os.path.exists(freq_path):
                with open(freq_path, "r") as f:
                    return float(f.read().strip()) / 1000.0
        except Exception:
            pass

        try:
            with open("/proc/cpuinfo", "r") as f:
                core_count = 0
                for line in f:
                    if line.startswith("cpu MHz"):
                        if core_count == core_id:
                            return float(line.split(":", 1)[1].strip())
                        core_count += 1
        except Exception:
            pass

        return 0.0

    def _get_load_avg(self) -> Tuple[float, float, float]:
        """Reads 1, 5, 15 minute load averages from /proc/loadavg."""
        try:
            with open("/proc/loadavg", "r") as f:
                parts = f.read().split()
                return (float(parts[0]), float(parts[1]), float(parts[2]))
        except Exception:
            return (0.0, 0.0, 0.0)

    def update(self) -> CpuSystemStats:
        """Reads /proc/stat and updates CPU core metrics."""
        stats = CpuSystemStats(
            model_name=self.model_name,
            cache_info=self.cache_info,
            temperature_c=self._get_temperature(),
            load_avg=self._get_load_avg()
        )

        try:
            with open("/proc/stat", "r") as f:
                lines = f.readlines()

            for line in lines:
                if not line.startswith("cpu"):
                    continue

                parts = line.split()
                cpu_label = parts[0]
                values = [float(x) for x in parts[1:]]

                idle_time = values[3] + (values[4] if len(values) > 4 else 0.0)
                total_time = sum(values)

                usage_pct = 0.0
                if cpu_label in self._prev_times:
                    prev_idle, prev_total = self._prev_times[cpu_label]
                    d_idle = idle_time - prev_idle
                    d_total = total_time - prev_total
                    if d_total > 0:
                        usage_pct = round(max(0.0, min(100.0, ((d_total - d_idle) / d_total) * 100.0)), 1)

                self._prev_times[cpu_label] = (idle_time, total_time)

                if cpu_label == "cpu":
                    stats.total_usage_percent = usage_pct
                elif cpu_label.startswith("cpu") and cpu_label[3:].isdigit():
                    core_id = int(cpu_label[3:])
                    freq = self._get_freq_mhz(core_id)
                    stats.cores.append(CpuCoreStats(core_id=core_id, usage_percent=usage_pct, freq_mhz=freq))

            stats.num_cores = len(stats.cores)
        except Exception:
            pass

        return stats
