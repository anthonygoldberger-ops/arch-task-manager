# ArchTask — Native Arch Linux System & Task Manager

**ArchTask** is a native, high-performance system and task manager built specifically for **Arch Linux** using **GTK4** and **Libadwaita**. It delivers deep system inspection capabilities directly from Linux kernel `/proc`, `/sys`, and DBus interfaces.

![ArchTask App Icon](data/org.arch.ArchTask.svg)

---

## Key Features

### 1. Processes Tab
- **Live Updating**: Monitored directly via `/proc` filesystem at ~0.2% CPU overhead.
- **Metrics**: PID, Process Name, User, CPU %, RAM RSS, Virtual Memory, Disk Read/Write rate, Process State, Threads, Nice priority, Start Time, Command Line.
- **Parent-Child Tree View**: Toggle between flat sortable view and hierarchical process tree (`Gtk.TreeListModel`).
- **Search-as-you-type**: Instant search across process names, PIDs, users, and command line flags.
- **Visual Highlighting**: Automatic visual cues for processes with unusually high CPU (>50%) or RAM (>1GB).
- **Multi-Select Context Menu**:
  - Kill (SIGTERM) & Force Kill (SIGKILL) with Polkit elevation fallback.
  - Renice priority (-20 to +19).
  - Suspend (SIGSTOP) / Resume (SIGCONT).
  - Open File Location (launches default file manager at binary location).
  - Copy PID.
  - View Open File Descriptors (modal inspector parsing `/proc/[pid]/fd`).
  - View Environment Variables (modal inspector parsing `/proc/[pid]/environ`).

### 2. Performance Tab
- **CPU**: Per-core live vector usage graphs, current per-core frequencies, package temperature, CPU model, cache hierarchy, and load averages (1/5/15m).
- **Memory**: Used, free, available, cached, buffers, and swap breakdown with rolling trend graphs.
- **GPU**: Native detection for AMD (`/sys/class/drm`), NVIDIA (`nvidia-smi`), and Intel GPUs. Displays GPU load %, VRAM used/total, and GPU core temp. Automatically hidden if no GPU is detected.
- **Disk Drives**: Per-drive read/write throughput rates (`/proc/diskstats`), mounted filesystems (`/proc/mounts`), and drive SMART health status via `smartctl`.
- **Network Interfaces**: Per-interface upload/download throughput rates (`/proc/net/dev`) and total transferred bytes since boot.
- **Network Sockets Sub-View**: Active TCP/UDP connection list showing local address:port, remote address:port, state, and owning PID/process name.
- **Battery & Sensors**: Battery capacity, charging state, power draw (Watts), health %, time remaining, and collapsible `lm-sensors` fan speeds & temperatures.

### 3. Systemd Integration Tab
- Manage both **System Scope** and **User Scope** systemd units.
- Filter by state (active, failed, inactive).
- Control actions: Start, Stop, Restart, Enable, Disable (using Polkit authorization for system units).
- Integrated journal viewer displaying recent `journalctl -u <unit> -n 100` log output.

### 4. Startup & Autostart Manager
- Manage XDG autostart `.desktop` entries and systemd user services launched at login.
- Clean toggle switches to enable or disable startup entries.

### 5. Extras & Power Features
- **Window Click Kill Tool**: Click on any open window on screen to immediately locate and terminate its owning PID.
- **Snapshot Export**: Export live process and performance statistics to formatted JSON or CSV files.
- **System Theme Integration**: Fully compliant with Libadwaita dark/light system preference switching.
- **Keyboard Shortcuts**: `Ctrl+F` (focus search), `Ctrl+R` (force refresh), `Delete` (kill process), `Ctrl+1`..`Ctrl+5` (switch tabs).

---

## Installation on Arch Linux

### Method 1: Build with `makepkg` (Recommended)

1. Clone or download the repository:
   ```bash
   git clone https://github.com/archlinux/arch-task-manager.git
   cd arch-task-manager
   ```

2. Build and install the Arch package:
   ```bash
   makepkg -si
   ```

3. Launch ArchTask:
   ```bash
   arch-task
   ```

### Method 2: Local Python Execution

You can run ArchTask directly from source:
```bash
python3 -m arch_task.main
```

---

## Dependencies

### Core Required Dependencies
- `python` (>= 3.10)
- `gtk4`
- `libadwaita`
- `python-gobject`
- `python-cairo`
- `systemd`

### Optional Dependencies (Automatically Detected at Runtime)
- `smartmontools` — For disk drive SMART health status checks.
- `nvidia-utils` — For NVIDIA GPU load and VRAM usage monitoring.
- `lm_sensors` — For motherboard hardware fan speeds and temperature sensors.
- `xorg-xprop` — For X11 window click-to-kill target identification.
- `polkit` — For elevated authentication prompts when modifying system services or root processes.

---

## License

GPLv3 License. Developed natively for Arch Linux.
