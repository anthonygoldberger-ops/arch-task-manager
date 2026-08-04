import os
import glob
from dataclasses import dataclass, field
from typing import List, Dict, Optional

@dataclass
class BatteryStats:
    present: bool = False
    capacity_percent: float = 0.0
    status: str = "Unknown" # Charging, Discharging, Full
    power_watts: float = 0.0
    health_percent: float = 100.0
    time_remaining_str: str = "N/A"

@dataclass
class SensorReading:
    label: str
    value_str: str
    type_name: str # Temp, Fan, Voltage

@dataclass
class SensorGroup:
    chip_name: str
    readings: List[SensorReading] = field(default_factory=list)

class PowerMonitor:
    """Monitors Battery power supply status and hardware lm-sensors readings from sysfs."""
    def update_battery(self) -> BatteryStats:
        bat = BatteryStats()
        bat_dirs = glob.glob("/sys/class/power_supply/BAT*")
        if not bat_dirs:
            return bat

        bat_dir = bat_dirs[0]
        bat.present = True

        try:
            capacity_file = os.path.join(bat_dir, "capacity")
            if os.path.exists(capacity_file):
                with open(capacity_file, "r") as f:
                    bat.capacity_percent = float(f.read().strip())

            status_file = os.path.join(bat_dir, "status")
            if os.path.exists(status_file):
                with open(status_file, "r") as f:
                    bat.status = f.read().strip()

            # Power calculation in Watts
            power_now_file = os.path.join(bat_dir, "power_now")
            current_now_file = os.path.join(bat_dir, "current_now")
            voltage_now_file = os.path.join(bat_dir, "voltage_now")

            if os.path.exists(power_now_file):
                with open(power_now_file, "r") as f:
                    bat.power_watts = float(f.read().strip()) / 1e6 # uW to W
            elif os.path.exists(current_now_file) and os.path.exists(voltage_now_file):
                with open(current_now_file, "r") as f:
                    curr = float(f.read().strip()) # uA
                with open(voltage_now_file, "r") as f:
                    volt = float(f.read().strip()) # uV
                bat.power_watts = (curr * volt) / 1e12 # uA * uV -> W

            # Battery health calculation (energy_full / energy_full_design or charge_full / charge_full_design)
            ef_file = os.path.join(bat_dir, "energy_full")
            efd_file = os.path.join(bat_dir, "energy_full_design")
            cf_file = os.path.join(bat_dir, "charge_full")
            cfd_file = os.path.join(bat_dir, "charge_full_design")

            full, design = 0.0, 0.0
            if os.path.exists(ef_file) and os.path.exists(efd_file):
                with open(ef_file, "r") as f:
                    full = float(f.read().strip())
                with open(efd_file, "r") as f:
                    design = float(f.read().strip())
            elif os.path.exists(cf_file) and os.path.exists(cfd_file):
                with open(cf_file, "r") as f:
                    full = float(f.read().strip())
                with open(cfd_file, "r") as f:
                    design = float(f.read().strip())

            if design > 0:
                bat.health_percent = round(min(100.0, (full / design) * 100.0), 1)

            # Time remaining calculation
            if bat.power_watts > 0:
                now_val = 0.0
                en_file = os.path.join(bat_dir, "energy_now")
                cn_file = os.path.join(bat_dir, "charge_now")
                if os.path.exists(en_file):
                    with open(en_file, "r") as f:
                        now_val = float(f.read().strip()) / 1e6 # uWh to Wh
                elif os.path.exists(cn_file) and os.path.exists(voltage_now_file):
                    with open(cn_file, "r") as f:
                        cn = float(f.read().strip()) / 1e6
                    with open(voltage_now_file, "r") as f:
                        vn = float(f.read().strip()) / 1e6
                    now_val = cn * vn

                if bat.status == "Discharging" and now_val > 0:
                    hrs = now_val / bat.power_watts
                    h = int(hrs)
                    m = int((hrs - h) * 60)
                    bat.time_remaining_str = f"{h}h {m}m left"
                elif bat.status == "Charging" and full > 0 and now_val > 0:
                    needed = (full / 1e6) - now_val
                    if needed > 0:
                        hrs = needed / bat.power_watts
                        h = int(hrs)
                        m = int((hrs - h) * 60)
                        bat.time_remaining_str = f"{h}h {m}m until full"
                    else:
                        bat.time_remaining_str = "Full"
                else:
                    bat.time_remaining_str = "Charged"
        except Exception:
            pass

        return bat

    def update_sensors(self) -> List[SensorGroup]:
        """Collects temperature, fan speed, and voltage sensors from /sys/class/hwmon."""
        groups: List[SensorGroup] = []

        for hwmon_dir in sorted(glob.glob("/sys/class/hwmon/hwmon*")):
            try:
                name = "Unknown Device"
                name_file = os.path.join(hwmon_dir, "name")
                if os.path.exists(name_file):
                    with open(name_file, "r") as f:
                        name = f.read().strip()

                group = SensorGroup(chip_name=name)

                # Temperature sensors (temp*_input)
                for temp_file in sorted(glob.glob(f"{hwmon_dir}/temp*_input")):
                    prefix = temp_file[:-6] # remove _input
                    label_file = f"{prefix}_label"
                    label = "Temp"
                    if os.path.exists(label_file):
                        try:
                            with open(label_file, "r") as f:
                                label = f.read().strip()
                        except Exception:
                            pass
                    else:
                        idx = os.path.basename(prefix)[4:]
                        label = f"Temperature #{idx}"

                    try:
                        with open(temp_file, "r") as f:
                            val = float(f.read().strip()) / 1000.0
                            group.readings.append(SensorReading(label=label, value_str=f"{val:.1f} °C", type_name="Temp"))
                    except Exception:
                        pass

                # Fan sensors (fan*_input)
                for fan_file in sorted(glob.glob(f"{hwmon_dir}/fan*_input")):
                    prefix = fan_file[:-6]
                    label_file = f"{prefix}_label"
                    label = "Fan"
                    if os.path.exists(label_file):
                        try:
                            with open(label_file, "r") as f:
                                label = f.read().strip()
                        except Exception:
                            pass
                    else:
                        idx = os.path.basename(prefix)[3:]
                        label = f"Fan #{idx}"

                    try:
                        with open(fan_file, "r") as f:
                            val = int(f.read().strip())
                            group.readings.append(SensorReading(label=label, value_str=f"{val} RPM", type_name="Fan"))
                    except Exception:
                        pass

                if group.readings:
                    groups.append(group)
            except Exception:
                continue

        return groups
