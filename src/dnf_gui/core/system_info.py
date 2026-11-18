"""System info backend — gathers system information without root."""

import subprocess
import os
import platform
import re
from dataclasses import dataclass
from typing import Callable, Optional

from dnf_gui.core.paths import system_binary


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
    device: Optional[str] = None        # "ASUS ROG Zephyrus G14" (DMI vendor + model)
    firmware: Optional[str] = None      # "03.05 (2024-08-12)" (BIOS/UEFI version + date)
    desktop: Optional[str] = None       # "KDE Plasma 6.8.2 (Wayland)"
    root_fs: Optional[str] = None       # "btrfs" (the root filesystem's type)
    last_update: Optional[str] = None   # when the newest dnf transaction ran


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
            lines = [line for line in result.stdout.strip().split("\n") if line.strip()]
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

    # This computer, its firmware, the desktop, the root filesystem and
    # the last dnf transaction (all read-only and quick).
    info.device = _get_device()
    info.firmware = _get_firmware()
    info.desktop = _get_desktop(info.desktop_env, info.display_server)
    info.root_fs = _get_root_fs()
    info.last_update = _get_last_update()

    return info


DMI_DIR = "/sys/class/dmi/id"
# What firmware vendors leave in DMI fields they never filled in.
_DMI_PLACEHOLDERS = {
    "", "to be filled by o.e.m.", "default string", "system product name",
    "system manufacturer", "system version", "o.e.m.", "oem", "not applicable",
    "not specified", "none", "unknown", "invalid", "undefined", "type1productconfigid",
    "123456789", "0123456789",
}


def _read_text(path: str) -> str:
    """A small text file's stripped contents, or "" (missing, unreadable)."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read(256).strip()
    except Exception:
        return ""


def _dmi(field: str, base: str = DMI_DIR) -> str:
    """A DMI field, or "" when it's a placeholder."""
    value = " ".join(_read_text(os.path.join(base, field)).split())
    return "" if value.lower() in _DMI_PLACEHOLDERS else value


def _get_device(base: str = DMI_DIR) -> Optional[str]:
    """Vendor and model ("LENOVO ThinkPad X1 Carbon Gen 11"); a desktop
    without a product name falls back to its family, then its board."""
    vendor = _dmi("sys_vendor", base) or _dmi("board_vendor", base)
    model = _dmi("product_name", base) or _dmi("product_family", base) or _dmi("board_name", base)
    if model and vendor and model.lower().startswith(vendor.lower()):
        vendor = ""  # "Framework" + "Framework Laptop 13"
    return " ".join(x for x in (vendor, model) if x) or None


def _get_firmware(base: str = DMI_DIR) -> Optional[str]:
    """BIOS/UEFI version and date: "03.05 (2024-08-12)"."""
    version = _dmi("bios_version", base)
    date = _dmi("bios_date", base)
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", date)
    if m:
        date = f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    if version and date:
        return f"{version} ({date})"
    return version or date or None


def _run_quick(cmd: list[str], timeout: float = 3) -> Optional[str]:
    """stdout of a quick read-only command, or None (missing, failed, slow)."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except Exception:
        return None
    return result.stdout if result.returncode == 0 else None


def _get_desktop(desktop_env: str, display_server: str,
                 run: Callable[[list[str]], Optional[str]] = _run_quick) -> Optional[str]:
    """The desktop and session, e.g. "KDE Plasma 6.8.2 (Wayland)": the
    installed Plasma version on a KDE session, else the session's own name."""
    name = desktop_env if desktop_env and desktop_env != "Unknown" else ""
    if "KDE" in os.environ.get("XDG_CURRENT_DESKTOP", "") or name.startswith("KDE"):
        version = (run([system_binary("rpm"), "-q", "--qf", "%{VERSION}", "plasma-workspace"]) or "").strip()
        if re.fullmatch(r"\d+(\.\d+)*", version):
            name = f"KDE Plasma {version}"
    if not name:
        return None
    session = display_server if display_server and display_server.lower() != "unknown" else ""
    return f"{name} ({session})" if session else name


def _get_root_fs(mounts: str = "/proc/mounts") -> Optional[str]:
    """The root filesystem's type ("btrfs"); the last mount on / wins."""
    fstype = None
    try:
        with open(mounts, encoding="utf-8", errors="replace") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 3 and parts[1] == "/" and parts[2] != "rootfs":
                    fstype = parts[2]
    except Exception:
        return None
    return fstype


def _get_last_update(run: Callable[[list[str]], Optional[str]] = _run_quick) -> Optional[str]:
    """When the newest dnf transaction ran, read from ``dnf history list``
    (parsed by DNFBackend.history, with a short timeout)."""
    try:
        from dnf_gui.core.dnf_backend import DNFBackend
        backend = DNFBackend()
        backend._run = lambda cmd, allow_nonzero=False: run(cmd)
        newest = backend.history(limit=1)
        return (newest[0].get("date") or None) if newest else None
    except Exception:
        return None


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
