import os
import time
import socket
import struct
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional

@dataclass
class NetworkInterfaceStats:
    iface: str
    rx_bytes_sec: float = 0.0
    tx_bytes_sec: float = 0.0
    rx_total_bytes: int = 0
    tx_total_bytes: int = 0

@dataclass
class ActiveSocketInfo:
    protocol: str
    local_addr: str
    remote_addr: str
    status: str
    pid: Optional[int] = None
    process_name: str = "Unknown"

class NetworkMonitor:
    """Monitors network interfaces (/proc/net/dev) and active TCP/UDP socket connections."""
    def __init__(self):
        self._prev_iface_io: Dict[str, Tuple[int, int, float]] = {} # iface -> (rx_bytes, tx_bytes, timestamp)

    def update_interfaces(self) -> List[NetworkInterfaceStats]:
        """Parses /proc/net/dev for per-interface bandwidth rates and cumulative transfer totals."""
        now = time.time()
        results: List[NetworkInterfaceStats] = []

        try:
            with open("/proc/net/dev", "r") as f:
                lines = f.readlines()

            for line in lines[2:]: # Skip header lines
                if ":" not in line:
                    continue
                iface, rest = line.split(":", 1)
                iface = iface.strip()

                # Ignore loopback interface
                if iface == "lo":
                    continue

                parts = rest.split()
                if len(parts) < 16:
                    continue

                rx_bytes = int(parts[0])
                tx_bytes = int(parts[8])

                rx_rate = 0.0
                tx_rate = 0.0
                if iface in self._prev_iface_io:
                    pr_bytes, pt_bytes, p_time = self._prev_iface_io[iface]
                    dt = now - p_time
                    if dt > 0.05:
                        rx_rate = max(0.0, (rx_bytes - pr_bytes) / dt)
                        tx_rate = max(0.0, (tx_bytes - pt_bytes) / dt)

                self._prev_iface_io[iface] = (rx_bytes, tx_bytes, now)

                results.append(NetworkInterfaceStats(
                    iface=iface,
                    rx_bytes_sec=rx_rate,
                    tx_bytes_sec=tx_rate,
                    rx_total_bytes=rx_bytes,
                    tx_total_bytes=tx_bytes
                ))
        except Exception:
            pass

        return results

    def _hex_to_ip_port(self, hex_addr: str) -> Tuple[str, int]:
        """Converts hex address string in /proc/net/tcp to IP address and port number."""
        try:
            ip_hex, port_hex = hex_addr.split(":")
            port = int(port_hex, 16)
            if len(ip_hex) == 8: # IPv4
                ip_bytes = bytes.fromhex(ip_hex)
                ip = socket.inet_ntop(socket.AF_INET, ip_bytes[::-1])
            else: # IPv6
                ip_bytes = bytes.fromhex(ip_hex)
                ip = socket.inet_ntop(socket.AF_INET6, ip_bytes)
            return ip, port
        except Exception:
            return "0.0.0.0", 0

    def get_active_sockets(self) -> List[ActiveSocketInfo]:
        """Parses active TCP/UDP connections from /proc/net/tcp and /proc/net/udp."""
        sockets: List[ActiveSocketInfo] = []

        # Map inode -> pid
        inode_to_pid: Dict[str, Tuple[int, str]] = {}
        try:
            for entry in os.listdir('/proc'):
                if entry.isdigit():
                    pid = int(entry)
                    fd_dir = f"/proc/{pid}/fd"
                    try:
                        if os.path.exists(fd_dir):
                            # Try reading proc comm
                            name = "unknown"
                            try:
                                with open(f"/proc/{pid}/comm", "r") as fc:
                                    name = fc.read().strip()
                            except Exception:
                                pass

                            for fd in os.listdir(fd_dir):
                                try:
                                    target = os.readlink(os.path.join(fd_dir, fd))
                                    if target.startswith("socket:["):
                                        inode = target[8:-1]
                                        inode_to_pid[inode] = (pid, name)
                                except Exception:
                                    continue
                    except Exception:
                        continue
        except Exception:
            pass

        tcp_states = {
            "01": "ESTABLISHED", "02": "SYN_SENT", "03": "SYN_RECV", "04": "FIN_WAIT1",
            "05": "FIN_WAIT2", "06": "TIME_WAIT", "07": "CLOSE", "08": "CLOSE_WAIT",
            "09": "LAST_ACK", "0A": "LISTEN", "0B": "CLOSING"
        }

        files = [
            ("/proc/net/tcp", "TCP"),
            ("/proc/net/tcp6", "TCP6"),
            ("/proc/net/udp", "UDP"),
            ("/proc/net/udp6", "UDP6")
        ]

        for file_path, proto in files:
            if not os.path.exists(file_path):
                continue
            try:
                with open(file_path, "r") as f:
                    lines = f.readlines()

                for line in lines[1:]: # skip header
                    parts = line.split()
                    if len(parts) < 10:
                        continue

                    local_hex = parts[1]
                    remote_hex = parts[2]
                    state_hex = parts[3]
                    inode = parts[9]

                    l_ip, l_port = self._hex_to_ip_port(local_hex)
                    r_ip, r_port = self._hex_to_ip_port(remote_hex)
                    state = tcp_states.get(state_hex, "UNKNOWN") if "TCP" in proto else "UNCONN"

                    # Filter out purely internal/idle sockets if needed
                    pid, pname = inode_to_pid.get(inode, (None, "Unknown"))

                    sockets.append(ActiveSocketInfo(
                        protocol=proto,
                        local_addr=f"{l_ip}:{l_port}",
                        remote_addr=f"{r_ip}:{r_port}",
                        status=state,
                        pid=pid,
                        process_name=pname
                    ))
            except Exception:
                continue

        return sockets
