"""System info backend — gathers system information without root."""

import subprocess
import os
import platform
from dataclasses import dataclass, field


@dataclass
class SystemInfo:
    """Container for system information."""
    hostname: str = ""
    fedora_version: str = ""
    kernel: str = ""
    desktop_env: str = ""
    display_server: str = ""
    cpu_model: str = ""
    cpu_cores: int = 0
    ram_total: str = ""
    ram_used: str = ""
    ram_percent: float = 0.0
    disk_total: str = ""
    disk_used: str = ""
    disk_free: str = ""
    disk_percent: float = 0.0
    uptime: str = ""
    gpu: str = ""
    shell: str = ""
    package_count: int = 0
    flatpak_count: int = 0


def get_system_info() -> SystemInfo:
    """Collect comprehensive system information."""
    info = SystemInfo()

    # Hostname
    info.hostname = platform.node()

    # Fedora version
    try:
        with open("/etc/fedora-release") as f:
            info.fedora_version = f.read().strip()
    except FileNotFoundError:
        info.fedora_version = f"Linux {platform.release()}"

    # Kernel
    info.kernel = platform.release()

    # Desktop environment
    info.desktop_env = os.environ.get("XDG_CURRENT_DESKTOP", "Unknown")
    kde_version = os.environ.get("KDE_SESSION_VERSION", "")
    if kde_version:
        info.desktop_env += f" (Plasma {kde_version})"

    # Display server
    session_type = os.environ.get("XDG_SESSION_TYPE", "unknown")
    info.display_server = session_type.capitalize()

    # CPU info
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("model name"):
                    info.cpu_model = line.split(":")[1].strip()
                    break
        info.cpu_cores = os.cpu_count() or 0
    except Exception:
        info.cpu_model = platform.processor()

    # RAM info
    try:
        with open("/proc/meminfo") as f:
            meminfo = {}
            for line in f:
                parts = line.split(":")
                if len(parts) == 2:
                    key = parts[0].strip()
                    val = parts[1].strip().split()[0]
                    meminfo[key] = int(val)

            total_kb = meminfo.get("MemTotal", 0)
            available_kb = meminfo.get("MemAvailable", 0)
            used_kb = total_kb - available_kb

            info.ram_total = _format_kb(total_kb)
            info.ram_used = _format_kb(used_kb)
            info.ram_percent = (used_kb / total_kb * 100) if total_kb else 0
    except Exception:
        pass

    # Disk info (root partition)
    try:
        st = os.statvfs("/")
        total = st.f_blocks * st.f_frsize
        free = st.f_bavail * st.f_frsize
        used = total - free
        info.disk_total = _format_bytes(total)
        info.disk_used = _format_bytes(used)
        info.disk_free = _format_bytes(free)
        info.disk_percent = (used / total * 100) if total else 0
    except Exception:
        pass

    # Uptime
    try:
        with open("/proc/uptime") as f:
            seconds = float(f.read().split()[0])
            days = int(seconds // 86400)
            hours = int((seconds % 86400) // 3600)
            minutes = int((seconds % 3600) // 60)
            parts = []
            if days:
                parts.append(f"{days}d")
            if hours:
                parts.append(f"{hours}h")
            parts.append(f"{minutes}m")
            info.uptime = " ".join(parts)
    except Exception:
        pass

    # GPU
    try:
        result = subprocess.run(
            ["lspci"], capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.split("\n"):
            if "VGA" in line or "3D" in line:
                info.gpu = line.split(": ", 1)[-1].strip() if ": " in line else line.strip()
                break
    except Exception:
        pass

    # Shell
    info.shell = os.environ.get("SHELL", "").split("/")[-1]

    # Package count
    try:
        result = subprocess.run(
            ["rpm", "-qa", "--queryformat", "x"],
            capture_output=True, text=True, timeout=30
        )
        info.package_count = len(result.stdout)
    except Exception:
        pass

    # Flatpak count
    try:
        result = subprocess.run(
            ["flatpak", "list", "--app", "--columns=application"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            lines = [l for l in result.stdout.strip().split("\n") if l.strip()]
            info.flatpak_count = len(lines)
    except Exception:
        pass

    return info


def _format_kb(kb: int) -> str:
    """Format kilobytes to human-readable."""
    return _format_bytes(kb * 1024)


def _format_bytes(b: int) -> str:
    """Format bytes to human-readable."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"
