from dataclasses import dataclass

@dataclass
class MemoryStats:
    total_bytes: int = 0
    used_bytes: int = 0
    free_bytes: int = 0
    available_bytes: int = 0
    buffers_bytes: int = 0
    cached_bytes: int = 0
    used_percent: float = 0.0

    swap_total_bytes: int = 0
    swap_used_bytes: int = 0
    swap_free_bytes: int = 0
    swap_used_percent: float = 0.0

class MemoryMonitor:
    """Monitors system RAM and Swap usage via /proc/meminfo."""
    def update(self) -> MemoryStats:
        stats = MemoryStats()
        data = {}
        try:
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    parts = line.split(":")
                    if len(parts) == 2:
                        key = parts[0].strip()
                        val = parts[1].strip().split()[0]
                        if val.isdigit():
                            data[key] = int(val) * 1024 # convert kB to bytes

            stats.total_bytes = data.get("MemTotal", 0)
            stats.free_bytes = data.get("MemFree", 0)
            stats.available_bytes = data.get("MemAvailable", stats.free_bytes)
            stats.buffers_bytes = data.get("Buffers", 0)
            cached = data.get("Cached", 0)
            sreclaimable = data.get("SReclaimable", 0)
            stats.cached_bytes = cached + sreclaimable

            # Used = Total - Available
            stats.used_bytes = max(0, stats.total_bytes - stats.available_bytes)
            if stats.total_bytes > 0:
                stats.used_percent = round((stats.used_bytes / stats.total_bytes) * 100.0, 1)

            stats.swap_total_bytes = data.get("SwapTotal", 0)
            stats.swap_free_bytes = data.get("SwapFree", 0)
            stats.swap_used_bytes = max(0, stats.swap_total_bytes - stats.swap_free_bytes)
            if stats.swap_total_bytes > 0:
                stats.swap_used_percent = round((stats.swap_used_bytes / stats.swap_total_bytes) * 100.0, 1)
        except Exception:
            pass

        return stats
