import os
import glob
import subprocess
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class GpuStats:
    name: str = "Unknown GPU"
    vendor: str = "Unknown"
    gpu_usage_percent: float = 0.0
    vram_used_bytes: int = 0
    vram_total_bytes: int = 0
    temperature_c: float = 0.0
    available: bool = False

class GpuMonitor:
    """Monitors GPU metrics across AMD, NVIDIA, and Intel GPUs natively."""
    def __init__(self):
        self._nvidia_smi_cmd = self._find_nvidia_smi()

    def _find_nvidia_smi(self) -> Optional[str]:
        for path in ["/usr/bin/nvidia-smi", "/bin/nvidia-smi"]:
            if os.path.exists(path) and os.access(path, os.X_OK):
                return path
        return None

    def update(self) -> List[GpuStats]:
        gpus: List[GpuStats] = []

        # 1. Try AMD sysfs
        amd_gpus = self._check_amd_sysfs()
        gpus.extend(amd_gpus)

        # 2. Try NVIDIA nvidia-smi
        if self._nvidia_smi_cmd and not gpus:
            nv_gpus = self._check_nvidia_smi()
            gpus.extend(nv_gpus)

        # 3. Try Intel sysfs
        if not gpus:
            intel_gpus = self._check_intel_sysfs()
            gpus.extend(intel_gpus)

        return gpus

    def _check_amd_sysfs(self) -> List[GpuStats]:
        gpus = []
        for card_device in glob.glob("/sys/class/drm/card*/device"):
            gpu_busy_file = os.path.join(card_device, "gpu_busy_percent")
            vram_used_file = os.path.join(card_device, "mem_info_vram_used")
            vram_total_file = os.path.join(card_device, "mem_info_vram_total")

            if os.path.exists(gpu_busy_file):
                gpu = GpuStats(name="AMD Radeon GPU", vendor="AMD", available=True)
                try:
                    with open(gpu_busy_file, "r") as f:
                        gpu.gpu_usage_percent = float(f.read().strip())
                except Exception:
                    pass

                try:
                    if os.path.exists(vram_used_file) and os.path.exists(vram_total_file):
                        with open(vram_used_file, "r") as f:
                            gpu.vram_used_bytes = int(f.read().strip())
                        with open(vram_total_file, "r") as f:
                            gpu.vram_total_bytes = int(f.read().strip())
                except Exception:
                    pass

                # Temp check in hwmon
                hwmon_pattern = os.path.join(card_device, "hwmon", "hwmon*", "temp1_input")
                for temp_file in glob.glob(hwmon_pattern):
                    try:
                        with open(temp_file, "r") as f:
                            gpu.temperature_c = float(f.read().strip()) / 1000.0
                            break
                    except Exception:
                        pass

                gpus.append(gpu)
        return gpus

    def _check_nvidia_smi(self) -> List[GpuStats]:
        gpus = []
        try:
            cmd = [
                self._nvidia_smi_cmd,
                "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu",
                "--format=csv,noheader,nounits"
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
            if res.returncode == 0:
                for line in res.stdout.strip().splitlines():
                    parts = [p.strip() for p in line.split(',')]
                    if len(parts) >= 5:
                        gpu = GpuStats(
                            name=parts[0],
                            vendor="NVIDIA",
                            gpu_usage_percent=float(parts[1]),
                            vram_used_bytes=int(parts[2]) * 1024 * 1024, # MiB to bytes
                            vram_total_bytes=int(parts[3]) * 1024 * 1024,
                            temperature_c=float(parts[4]),
                            available=True
                        )
                        gpus.append(gpu)
        except Exception:
            pass
        return gpus

    def _check_intel_sysfs(self) -> List[GpuStats]:
        gpus = []
        for card_device in glob.glob("/sys/class/drm/card*/device"):
            act_freq_file = os.path.join(card_device, "gt_act_freq_mhz")
            max_freq_file = os.path.join(card_device, "gt_max_freq_mhz")
            if os.path.exists(act_freq_file) and os.path.exists(max_freq_file):
                gpu = GpuStats(name="Intel Graphics", vendor="Intel", available=True)
                try:
                    with open(act_freq_file, "r") as f:
                        act_freq = float(f.read().strip())
                    with open(max_freq_file, "r") as f:
                        max_freq = float(f.read().strip())
                    if max_freq > 0:
                        gpu.gpu_usage_percent = round((act_freq / max_freq) * 100.0, 1)
                except Exception:
                    pass
                gpus.append(gpu)
                break
        return gpus
