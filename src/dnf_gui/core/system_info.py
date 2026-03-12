"""System info backend — gathers system information without root."""

import subprocess
import os
import platform
from dataclasses import dataclass
from typing import Optional


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
    # Optional / conditional fields (None = not applicable)
    architecture: Optional[str] = None
    swap_total: Optional[str] = None
    swap_used: Optional[str] = None
    swap_percent: float = 0.0
    selinux_status: Optional[str] = None
    boot_mode: Optional[str] = None
    virtualization: Optional[str] = None
    battery_percent: Optional[int] = None
    battery_status: Optional[str] = None
    battery_time: Optional[str] = None
    audio_server: Optional[str] = None
    cpu_temp: Optional[str] = None
    primary_ip: Optional[str] = None


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

    # Architecture
    info.architecture = platform.machine()

    # Swap (only if swap exists)
    try:
        with open("/proc/meminfo") as f:
            meminfo = {}
            for line in f:
                parts = line.split(":")
                if len(parts) == 2:
                    key = parts[0].strip()
                    val = parts[1].strip().split()[0]
                    meminfo[key] = int(val)
            swap_total_kb = meminfo.get("SwapTotal", 0)
            swap_free_kb = meminfo.get("SwapFree", 0)
            if swap_total_kb > 0:
                swap_used_kb = swap_total_kb - swap_free_kb
                info.swap_total = _format_kb(swap_total_kb)
                info.swap_used = _format_kb(swap_used_kb)
                info.swap_percent = (swap_used_kb / swap_total_kb * 100) if swap_total_kb else 0
    except Exception:
        pass

    # SELinux (Fedora-relevant)
    try:
        result = subprocess.run(
            ["getenforce"],
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode == 0 and result.stdout.strip():
            info.selinux_status = result.stdout.strip()
    except Exception:
        pass

    # Boot mode (UEFI vs BIOS)
    if os.path.exists("/sys/firmware/efi"):
        info.boot_mode = "UEFI"
    else:
        info.boot_mode = "BIOS (Legacy)"

    # Virtualization (only if in VM)
    try:
        result = subprocess.run(
            ["systemd-detect-virt"],
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode == 0 and result.stdout.strip():
            virt = result.stdout.strip()
            if virt != "none":
                virt_map = {"kvm": "KVM", "qemu": "QEMU", "vmware": "VMware", "oracle": "VirtualBox", "xen": "Xen", "microsoft": "Hyper-V"}
                info.virtualization = virt_map.get(virt, virt.capitalize())
    except Exception:
        info.virtualization = _detect_virt_from_cpuinfo()

    # Battery (laptops only)
    bat = _get_battery_info()
    if bat:
        info.battery_percent = bat.get("percent")
        info.battery_status = bat.get("status")
        info.battery_time = bat.get("time")

    # Audio server
    info.audio_server = _get_audio_server()

    # CPU temperature (if lm_sensors available)
    info.cpu_temp = _get_cpu_temp()

    # Primary IP address
    info.primary_ip = _get_primary_ip()

    return info


def _detect_virt_from_cpuinfo() -> Optional[str]:
    """Fallback: detect virtualization from /proc/cpuinfo."""
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if "hypervisor" in line.lower():
                    return "Virtual machine"
    except Exception:
        pass
    return None


def _get_battery_info() -> Optional[dict]:
    """Get battery info if available (laptops). Returns dict with percent, status, time."""
    try:
        base = "/sys/class/power_supply"
        for name in os.listdir(base):
            path = os.path.join(base, name)
            if not os.path.isdir(path):
                continue
            try:
                with open(os.path.join(path, "type")) as f:
                    if f.read().strip() != "Battery":
                        continue
            except Exception:
                continue
            data = {}
            # Capacity/percent
            for fname in ("capacity", "charge_now"):  # charge_now needs energy_full for %
                fpath = os.path.join(path, fname)
                if os.path.exists(fpath):
                    try:
                        with open(fpath) as f:
                            val = f.read().strip()
                        if val.isdigit():
                            data["percent"] = int(val)
                            break
                    except Exception:
                        pass
            # Status: Charging, Discharging, Full
            fpath = os.path.join(path, "status")
            if os.path.exists(fpath):
                try:
                    with open(fpath) as f:
                        data["status"] = f.read().strip()
                except Exception:
                    pass
            # Time remaining (minutes)
            for fname in ("time_to_empty_now", "time_to_empty_sec", "time_to_full_now"):
                fpath = os.path.join(path, fname)
                if os.path.exists(fpath):
                    try:
                        with open(fpath) as f:
                            val = f.read().strip()
                        if val.isdigit():
                            mins = int(val) // 60
                            data["time"] = f"{mins // 60}h {mins % 60}m" if mins else "—"
                            break
                    except Exception:
                        pass
            if data:
                return data
    except Exception:
        pass
    return None


def _get_audio_server() -> Optional[str]:
    """Detect audio server (PipeWire, PulseAudio)."""
    if os.environ.get("PIPEWIRE_RUNTIME_DIR"):
        return "PipeWire"
    try:
        result = subprocess.run(
            ["pactl", "info"],
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode == 0:
            for line in result.stdout.split("\n"):
                if "Server Name" in line and "PipeWire" in line:
                    return "PipeWire"
                if "Server Name" in line:
                    return "PulseAudio"
    except Exception:
        pass
    return None


def _get_cpu_temp() -> Optional[str]:
    """Get CPU temperature if lm_sensors available."""
    try:
        result = subprocess.run(
            ["sensors"],
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode != 0:
            return None
        for line in result.stdout.split("\n"):
            # Match Core 0, Package id 0, Tctl, Tdie, etc.
            if "Core 0" in line or "Package id" in line or "Tctl" in line or "Tdie" in line:
                parts = line.split("+")
                if len(parts) >= 2:
                    temp = parts[1].split("°")[0].strip().split(".")[0]
                    if temp.replace(".", "").replace("-", "").isdigit():
                        return f"{temp}°C"
    except Exception:
        pass
    return None


def _get_primary_ip() -> Optional[str]:
    """Get primary (default route) IP address."""
    try:
        result = subprocess.run(
            ["ip", "-4", "route", "get", "1"],
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode == 0:
            parts = result.stdout.split()
            if "src" in parts:
                idx = parts.index("src")
                if idx + 1 < len(parts):
                    return parts[idx + 1]
        # Fallback: hostname -I
        result = subprocess.run(
            ["hostname", "-I"],
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().split()[0]
    except Exception:
        pass
    return None


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
