import json
import csv
import time
from typing import List, Dict, Any
from ..monitors.process_monitor import ProcessInfo
from ..monitors.cpu_monitor import CpuSystemStats
from ..monitors.memory_monitor import MemoryStats

class SnapshotExporter:
    """Exports process list and system performance statistics to JSON or CSV files."""
    @staticmethod
    def export_to_json(
        file_path: str,
        processes: List[ProcessInfo],
        cpu_stats: CpuSystemStats,
        mem_stats: MemoryStats
    ) -> bool:
        try:
            data = {
                "timestamp": time.time(),
                "timestamp_str": time.strftime("%Y-%m-%d %H:%M:%S"),
                "system": {
                    "cpu": {
                        "model": cpu_stats.model_name,
                        "usage_percent": cpu_stats.total_usage_percent,
                        "temperature_c": cpu_stats.temperature_c,
                        "load_avg": list(cpu_stats.load_avg),
                        "cores": [{"core_id": c.core_id, "usage_percent": c.usage_percent, "freq_mhz": c.freq_mhz} for c in cpu_stats.cores]
                    },
                    "memory": {
                        "total_bytes": mem_stats.total_bytes,
                        "used_bytes": mem_stats.used_bytes,
                        "free_bytes": mem_stats.free_bytes,
                        "used_percent": mem_stats.used_percent,
                        "swap_used_bytes": mem_stats.swap_used_bytes,
                        "swap_total_bytes": mem_stats.swap_total_bytes
                    }
                },
                "processes": [
                    {
                        "pid": p.pid,
                        "ppid": p.ppid,
                        "name": p.name,
                        "user": p.user,
                        "state": p.state,
                        "cpu_percent": p.cpu_percent,
                        "rss_bytes": p.rss_bytes,
                        "vsize_bytes": p.vsize_bytes,
                        "read_bytes_sec": p.read_bytes_sec,
                        "write_bytes_sec": p.write_bytes_sec,
                        "nice": p.nice,
                        "threads": p.threads,
                        "cmdline": p.cmdline
                    } for p in processes
                ]
            }
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return True
        except Exception:
            return False

    @staticmethod
    def export_to_csv(file_path: str, processes: List[ProcessInfo]) -> bool:
        try:
            fieldnames = [
                "pid", "ppid", "name", "user", "state", "cpu_percent",
                "rss_bytes", "vsize_bytes", "read_bytes_sec", "write_bytes_sec",
                "nice", "threads", "cmdline"
            ]
            with open(file_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for p in processes:
                    writer.writerow({
                        "pid": p.pid,
                        "ppid": p.ppid,
                        "name": p.name,
                        "user": p.user,
                        "state": p.state,
                        "cpu_percent": p.cpu_percent,
                        "rss_bytes": p.rss_bytes,
                        "vsize_bytes": p.vsize_bytes,
                        "read_bytes_sec": p.read_bytes_sec,
                        "write_bytes_sec": p.write_bytes_sec,
                        "nice": p.nice,
                        "threads": p.threads,
                        "cmdline": p.cmdline
                    })
            return True
        except Exception:
            return False
