import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib
from typing import List, Dict

from .graph_widget import RollingGraphWidget
from ..monitors.cpu_monitor import CpuMonitor, CpuSystemStats
from ..monitors.memory_monitor import MemoryMonitor, MemoryStats
from ..monitors.gpu_monitor import GpuMonitor, GpuStats
from ..monitors.disk_monitor import DiskMonitor, DiskDriveStats
from ..monitors.net_monitor import NetworkMonitor, NetworkInterfaceStats
from ..monitors.power_monitor import PowerMonitor, BatteryStats, SensorGroup
from .process_view import format_bytes

class PerformanceView(Gtk.ScrolledWindow):
    """Performance tab displaying live hardware statistics and rolling history graphs."""
    def __init__(self, main_window: Gtk.Window):
        super().__init__(vexpand=True)
        self.main_window = main_window

        # System Monitors
        self.cpu_mon = CpuMonitor()
        self.mem_mon = MemoryMonitor()
        self.gpu_mon = GpuMonitor()
        self.disk_mon = DiskMonitor()
        self.net_mon = NetworkMonitor()
        self.power_mon = PowerMonitor()

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        main_box.set_margin_start(16)
        main_box.set_margin_end(16)
        main_box.set_margin_top(16)
        main_box.set_margin_bottom(16)
        self.set_child(main_box)

        # 1. CPU Section
        cpu_clamp = Adw.Clamp(maximum_size=1000)
        main_box.append(cpu_clamp)

        cpu_group = Adw.PreferencesGroup(title="Processor (CPU)", description="Per-core usage, frequency, load averages and thermals")
        cpu_clamp.set_child(cpu_group)

        self.cpu_graph = RollingGraphWidget(max_points=60, title="CPU Total Usage (%)", unit_suffix="%")
        self.cpu_graph.set_content_height(140)
        cpu_group.add(self.cpu_graph)

        self.cpu_info_row = Adw.ActionRow(title="Model", subtitle="Loading...")
        cpu_group.add(self.cpu_info_row)

        self.cpu_detail_row = Adw.ActionRow(title="Status", subtitle="Loading cores...")
        cpu_group.add(self.cpu_detail_row)

        # 2. Memory Section
        mem_clamp = Adw.Clamp(maximum_size=1000)
        main_box.append(mem_clamp)

        mem_group = Adw.PreferencesGroup(title="System Memory (RAM)", description="Used, free, cached memory and swap allocation")
        mem_clamp.set_child(mem_group)

        self.mem_graph = RollingGraphWidget(max_points=60, title="RAM Usage (%)", unit_suffix="%")
        self.mem_graph.set_content_height(140)
        mem_group.add(self.mem_graph)

        self.mem_info_row = Adw.ActionRow(title="Breakdown", subtitle="Loading...")
        mem_group.add(self.mem_info_row)

        # 3. GPU Section
        gpu_clamp = Adw.Clamp(maximum_size=1000)
        main_box.append(gpu_clamp)

        self.gpu_group = Adw.PreferencesGroup(title="Graphics Processing Unit (GPU)", description="GPU core load and VRAM metrics")
        gpu_clamp.set_child(self.gpu_group)

        self.gpu_graph = RollingGraphWidget(max_points=60, title="GPU Usage (%)", unit_suffix="%")
        self.gpu_graph.set_content_height(140)
        self.gpu_group.add(self.gpu_graph)

        self.gpu_info_row = Adw.ActionRow(title="GPU", subtitle="Scanning hardware...")
        self.gpu_group.add(self.gpu_info_row)

        # 4. Disk Drives Section
        disk_clamp = Adw.Clamp(maximum_size=1000)
        main_box.append(disk_clamp)

        self.disk_group = Adw.PreferencesGroup(title="Storage (Disks)", description="Read/Write throughput rates and filesystem partitions")
        disk_clamp.set_child(self.disk_group)

        self.disk_graph = RollingGraphWidget(max_points=60, title="Disk I/O Rate", unit_suffix=" B/s", auto_scale=True)
        self.disk_graph.set_content_height(140)
        self.disk_group.add(self.disk_graph)

        self.disk_info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.disk_group.add(self.disk_info_box)

        # 5. Network Interfaces Section
        net_clamp = Adw.Clamp(maximum_size=1000)
        main_box.append(net_clamp)

        net_group = Adw.PreferencesGroup(title="Network Interfaces", description="Upload/Download throughput and transfer totals")
        net_clamp.set_child(net_group)

        self.net_graph = RollingGraphWidget(
            max_points=60,
            title="Network Throughput (Rx / Tx)",
            unit_suffix=" B/s",
            auto_scale=True,
            colors=[(0.1, 0.8, 0.4), (0.9, 0.3, 0.2)]
        )
        self.net_graph.set_content_height(140)
        net_group.add(self.net_graph)

        self.net_info_row = Adw.ActionRow(title="Interfaces", subtitle="Scanning...")
        net_group.add(self.net_info_row)

        # 6. Battery Section (if present)
        bat_clamp = Adw.Clamp(maximum_size=1000)
        main_box.append(bat_clamp)

        self.bat_group = Adw.PreferencesGroup(title="Power &amp; Battery", description="Battery state, health, and power consumption")
        bat_clamp.set_child(self.bat_group)

        self.bat_info_row = Adw.ActionRow(title="Battery Status", subtitle="Checking power supply...")
        self.bat_group.add(self.bat_info_row)

        # 7. Hardware Sensors (Collapsible Expander)
        sensor_clamp = Adw.Clamp(maximum_size=1000)
        main_box.append(sensor_clamp)

        self.sensor_expander = Gtk.Expander(label="Hardware Sensors & Fan Speeds (lm-sensors)")
        sensor_clamp.set_child(self.sensor_expander)

        self.sensor_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.sensor_box.set_margin_start(12)
        self.sensor_box.set_margin_end(12)
        self.sensor_box.set_margin_top(8)
        self.sensor_expander.set_child(self.sensor_box)

    def refresh_data(self):
        """Polls data monitors and updates graphs and UI labels."""
        # 1. Update CPU
        cpu = self.cpu_mon.update()
        self.cpu_graph.add_point(cpu.total_usage_percent)
        self.cpu_info_row.set_subtitle(f"{cpu.model_name} ({cpu.num_cores} Cores)")

        freq_str = f"Avg Freq: {cpu.cores[0].freq_mhz:.0f} MHz" if cpu.cores else ""
        load_str = f"Load Avg: {cpu.load_avg[0]:.2f}, {cpu.load_avg[1]:.2f}, {cpu.load_avg[2]:.2f}"
        temp_str = f"Temp: {cpu.temperature_c:.1f} °C" if cpu.temperature_c > 0 else ""
        self.cpu_detail_row.set_subtitle(f"{temp_str} | {load_str} | {freq_str}")

        # 2. Update Memory
        mem = self.mem_mon.update()
        self.mem_graph.add_point(mem.used_percent)
        self.mem_info_row.set_subtitle(
            f"RAM Used: {format_bytes(mem.used_bytes)} / {format_bytes(mem.total_bytes)} ({mem.used_percent}%)\n"
            f"Cached: {format_bytes(mem.cached_bytes)} | Buffers: {format_bytes(mem.buffers_bytes)} | Free: {format_bytes(mem.free_bytes)}\n"
            f"Swap Used: {format_bytes(mem.swap_used_bytes)} / {format_bytes(mem.swap_total_bytes)} ({mem.swap_used_percent}%)"
        )

        # 3. Update GPU
        gpus = self.gpu_mon.update()
        if gpus and gpus[0].available:
            self.gpu_group.set_visible(True)
            g = gpus[0]
            self.gpu_graph.add_point(g.gpu_usage_percent)
            vram_str = f"VRAM: {format_bytes(g.vram_used_bytes)} / {format_bytes(g.vram_total_bytes)}" if g.vram_total_bytes > 0 else ""
            temp_str = f"Temp: {g.temperature_c:.1f} °C" if g.temperature_c > 0 else ""
            self.gpu_info_row.set_subtitle(f"{g.name} ({g.vendor}) | Load: {g.gpu_usage_percent}% | {vram_str} {temp_str}")
        else:
            self.gpu_group.set_visible(False)

        # 4. Update Disks
        drives = self.disk_mon.update()
        total_r = sum(d.read_bytes_sec for d in drives)
        total_w = sum(d.write_bytes_sec for d in drives)
        self.disk_graph.add_point(total_r + total_w)

        # Rebuild drive rows
        child = self.disk_info_box.get_first_child()
        while child:
            next_c = child.get_next_sibling()
            self.disk_info_box.remove(child)
            child = next_c

        for d in drives:
            d_row = Adw.ActionRow(
                title=f"Drive /{d.disk_name} — SMART: {d.smart_status}",
                subtitle=f"Read: {format_bytes(d.read_bytes_sec)}/s | Write: {format_bytes(d.write_bytes_sec)}/s"
            )
            self.disk_info_box.append(d_row)

            for p in d.partitions:
                p_row = Adw.ActionRow(
                    title=f"  Mount: {p.mountpoint} ({p.fstype} - {p.device})",
                    subtitle=f"  Used: {format_bytes(p.used_bytes)} / {format_bytes(p.total_bytes)} ({p.used_percent}%)"
                )
                self.disk_info_box.append(p_row)

        # 5. Update Network
        ifaces = self.net_mon.update_interfaces()
        tot_rx = sum(i.rx_bytes_sec for i in ifaces)
        tot_tx = sum(i.tx_bytes_sec for i in ifaces)
        self.net_graph.add_multi_points([tot_rx, tot_tx])

        summary_lines = [f"{i.iface}: ↓ {format_bytes(i.rx_bytes_sec)}/s | ↑ {format_bytes(i.tx_bytes_sec)}/s (Total ↓ {format_bytes(i.rx_total_bytes)} | ↑ {format_bytes(i.tx_total_bytes)})" for i in ifaces]
        self.net_info_row.set_subtitle("\n".join(summary_lines) if summary_lines else "No active network interfaces detected")

        # 6. Update Battery
        bat = self.power_mon.update_battery()
        if bat.present:
            self.bat_group.set_visible(True)
            self.bat_info_row.set_subtitle(
                f"Charge: {bat.capacity_percent}% ({bat.status}) | Power Draw: {bat.power_watts:.2f} W | "
                f"Health: {bat.health_percent}% | {bat.time_remaining_str}"
            )
        else:
            self.bat_group.set_visible(False)

        # 7. Update Sensors
        sensor_groups = self.power_mon.update_sensors()
        schild = self.sensor_box.get_first_child()
        while schild:
            snext = schild.get_next_sibling()
            self.sensor_box.remove(schild)
            schild = snext

        for sg in sensor_groups:
            sgroup_row = Adw.PreferencesGroup(title=sg.chip_name)
            for r in sg.readings:
                srow = Adw.ActionRow(title=r.label, subtitle=f"{r.value_str} ({r.type_name})")
                sgroup_row.add(srow)
            self.sensor_box.append(sgroup_row)
