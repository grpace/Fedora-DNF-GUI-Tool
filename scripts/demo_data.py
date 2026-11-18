"""Sample data for ``scripts/screenshots.py --demo`` (and design QA).

Stubs every worker so nothing touches dnf, Flatpak, systemd or the network,
then fills the controllers with a realistic Fedora system's state.
"""

from __future__ import annotations

from dnf_gui.core.flatpak_backend import FlatpakApp
from dnf_gui.core.package import Package, PackageStatus, UpdateInfo, UpgradePreview
from dnf_gui.core.release_upgrade import ReleaseUpgrade
from dnf_gui.core.security import BlockedUpdates, SecuritySummary
from dnf_gui.core.system_info import SystemInfo

MiB = 1024 * 1024


def stub_workers() -> None:
    """Workers return the sample data instead of running anything."""
    from dnf_gui.core import app_settings, notifications, worker

    def emit(value_fn):
        return lambda self: self.finished.emit(value_fn())

    worker.CombinedUpdateCheckWorker.run = emit(scan_result)
    worker.PackageListWorker.run = emit(lambda: list(INSTALLED))
    worker.FlatpakListWorker.run = emit(lambda: list(FLATPAKS) + EXTRA_FLATPAKS)
    worker.RepoListWorker.run = emit(lambda: [dict(r) for r in REPOS])
    worker.HistoryWorker.run = emit(lambda: [dict(h) for h in HISTORY])
    worker.SystemInfoWorker.run = emit(lambda: SYSINFO)
    worker.ToolkitCheckWorker.run = emit(lambda: {"rpmfusion_free": True,
                                                  "rpmfusion_nonfree": True,
                                                  "add_flathub": True})
    worker.DiscoverStatusWorker.run = emit(lambda: _Discover())
    worker.RebootCheckWorker.run = emit(lambda: True)
    worker.PackageInfoWorker.run = emit(lambda: FIREFOX_INFO)
    worker.AppUpdateWorker.run = emit(lambda: None)
    for name in ("ReminderCheckWorker", "CallWorker", "FlatpakSearchWorker"):
        setattr(getattr(worker, name), "run", lambda self: None)
    app_settings._systemctl_user = lambda *a: True
    notifications.Notifier._dbus_notify = lambda self, n, replaces_id=0: 0
    notifications._notify_send = lambda n: False


def _pkg(name, old, new, repo="updates", arch="x86_64"):
    version, release = new.rsplit("-", 1)
    return Package(name=name, version=version, release=release, arch=arch, repo=repo,
                   status=PackageStatus.UPDATE_AVAILABLE, installed_version=old)


UPDATES = [
    _pkg("firefox", "145.0-1.fc45", "146.0.1-1.fc45"),
    _pkg("openssl-libs", "1:3.5.3-1.fc45", "1:3.5.4-2.fc45"),
    _pkg("libheif", "1.23.4-1.fc45", "1.23.6-1.fc45"),
    _pkg("kernel-core", "7.2.6-300.fc45", "7.2.8-300.fc45"),
    _pkg("kernel-modules", "7.2.6-300.fc45", "7.2.8-300.fc45"),
    _pkg("akmod-nvidia", "3:615.71.09-3.fc45", "3:615.78.08-1.fc45",
         repo="rpmfusion-nonfree-updates"),
    _pkg("mesa-dri-drivers", "26.0.1-1.fc45", "26.0.2-1.fc45"),
    _pkg("plasma-workspace", "6.8.2-1.fc45", "6.8.3-1.fc45"),
    _pkg("python3-requests", "2.32.3-4.fc45", "2.32.5-1.fc45", arch="noarch"),
    _pkg("vim-enhanced", "2:9.1.1800-1.fc45", "2:9.1.1850-1.fc45"),
]
SIZES = {"firefox": 68 * MiB, "openssl-libs": 2 * MiB, "libheif": 512 * 1024,
         "kernel-core": 19 * MiB, "kernel-modules": 64 * MiB, "akmod-nvidia": 41 * MiB,
         "mesa-dri-drivers": 27 * MiB, "plasma-workspace": 21 * MiB,
         "python3-requests": 164 * 1024, "vim-enhanced": 2 * MiB}
FLATPAKS = [
    FlatpakApp("Thunderbird", "org.mozilla.Thunderbird", "146.0", "stable", "flathub",
               "92.1 MB"),
    FlatpakApp("Kdenlive", "org.kde.kdenlive", "25.12.0", "stable", "flathub", "136 MB"),
    FlatpakApp("Spotify", "com.spotify.Client", "1.2.77", "stable", "flathub", "8.3 MB"),
]


def scan_result(blocked: bool = True, release: bool = True, reboot: bool = True) -> dict:
    info = UpdateInfo(total_updates=len(UPDATES), packages=list(UPDATES),
                      last_checked="")
    preview = UpgradePreview(count=len(UPDATES), total_bytes=sum(SIZES.values()),
                             sizes_known=True, entries=list(SIZES.items()))
    security = SecuritySummary(
        total=3, critical=1, important=2,
        advisories=["FEDORA-2026-7c41e2a9d3", "FEDORA-2026-1a9f03be77",
                    "FEDORA-2026-e0d5c18f42"],
        packages=["firefox", "openssl-libs", "libheif"],
        package_severity={"firefox": "critical", "openssl-libs": "important",
                          "libheif": "important"},
        advisory_severity={"FEDORA-2026-7c41e2a9d3": "critical",
                           "FEDORA-2026-1a9f03be77": "important",
                           "FEDORA-2026-e0d5c18f42": "important"},
        advisory_packages={"FEDORA-2026-7c41e2a9d3": {"firefox"},
                           "FEDORA-2026-1a9f03be77": {"openssl-libs"},
                           "FEDORA-2026-e0d5c18f42": {"libheif"}})
    if blocked:
        security.blocked = BlockedUpdates(
            packages=["libheif"],
            blockers={"libheif-freeworld": "rpmfusion-free-updates"}, removals=["libheif-freeworld"])
    return {"dnf": info, "flatpak": list(FLATPAKS), "security": security,
            "preview": preview, "security_preview": None, "reboot": reboot,
            "release_upgrade": ReleaseUpgrade(45, 46, "2027-06-02") if release else None}


INSTALLED = [Package(n, v, r, a, repo, s, status=PackageStatus.INSTALLED)
             for n, v, r, a, repo, s in (
                 ("bash", "5.3.3", "1.fc45", "x86_64", "fedora", "The GNU Bourne Again shell"),
                 ("firefox", "145.0", "1.fc45", "x86_64", "updates", "Mozilla Firefox Web browser"),
                 ("git", "2.52.0", "1.fc45", "x86_64", "updates", "Fast version control system"),
                 ("htop", "3.4.1", "2.fc45", "x86_64", "fedora", "Interactive process viewer"),
                 ("kernel-core", "7.2.6", "300.fc45", "x86_64", "updates", "The Linux kernel"),
                 ("plasma-workspace", "6.8.2", "1.fc45", "x86_64", "updates", "Plasma workspace"),
                 ("python3", "3.14.1", "1.fc45", "x86_64", "fedora", "Version 3 of the Python language"),
                 ("vim-enhanced", "9.1.1800", "1.fc45", "x86_64", "updates", "A version of the VIM editor"),
                 ("zsh", "5.9", "15.fc45", "x86_64", "fedora", "Powerful interactive shell"),
             )]
REPOS = [
    {"id": "fedora", "name": "Fedora 45 - x86_64", "enabled": True},
    {"id": "updates", "name": "Fedora 45 - x86_64 - Updates", "enabled": True},
    {"id": "updates-testing", "name": "Fedora 45 - x86_64 - Test Updates", "enabled": False},
    {"id": "rpmfusion-free", "name": "RPM Fusion for Fedora 45 - Free", "enabled": True},
    {"id": "rpmfusion-nonfree", "name": "RPM Fusion for Fedora 45 - Nonfree", "enabled": True},
    {"id": "copr:copr.fedorainfracloud.org:atim:starship", "name": "Copr repo for starship",
     "enabled": True},
    {"id": "fedora-cisco-openh264", "name": "Fedora 45 openh264 (From Cisco)", "enabled": False},
]
HISTORY = [
    {"id": "214", "command": "upgrade -y --refresh", "date": "2026-11-16 09:12 PM",
     "action": "Upgrade", "altered": "38"},
    {"id": "213", "command": "install -y htop", "date": "2026-11-14 10:03 AM",
     "action": "Install", "altered": "1"},
    {"id": "212", "command": "upgrade -y --security", "date": "2026-11-12 08:40 PM",
     "action": "Upgrade", "altered": "6"},
    {"id": "211", "command": "System / PackageKit", "date": "2026-11-09 07:55 AM",
     "action": "Upgrade", "altered": "112"},
    {"id": "210", "command": "remove -y gnome-tour", "date": "2026-11-02 03:21 PM",
     "action": "Removed", "altered": "1"},
]
SYSINFO = SystemInfo(
    hostname="fedora-desktop", fedora_version="Fedora Linux 45 (KDE Plasma Desktop Edition)",
    kernel="7.2.6-300.fc45.x86_64", desktop_env="KDE Plasma 6.8.2", display_server="Wayland",
    cpu_model="AMD Ryzen 7 7840U w/ Radeon 780M Graphics", cpu_cores=16,
    ram_total="30.6 GB", ram_used="11.2 GB", ram_percent=36.6, disk_total="952 GB",
    disk_used="412 GB", disk_free="540 GB", disk_percent=43.3, uptime="2 days, 4 hours",
    gpu="AMD Radeon 780M", shell="zsh", package_count=2417, flatpak_count=23,
    architecture="x86_64", swap_total="8.0 GB", swap_used="0.4 GB", swap_percent=5.0,
    selinux_status="Enforcing", boot_mode="UEFI (Secure Boot on)", virtualization="None",
    battery_percent=82, battery_status="Discharging", battery_time="5 h 10 min",
    audio_server="PipeWire 1.4.9", cpu_temp="48 °C", primary_ip="192.168.1.42",
    device="Framework Laptop 13 (AMD Ryzen 7040 Series)", firmware="03.05 (2024-08-12)",
    desktop="KDE Plasma 6.8.2 (Wayland)", root_fs="btrfs", last_update="2026-11-16 09:12 PM")


EXTRA_FLATPAKS = [
    FlatpakApp("Flatseal", "com.github.tchx84.Flatseal", "2.3.1", "stable", "flathub",
               "1.2 MB"),
    FlatpakApp("KDE Application Platform", "org.kde.Platform", "", "6.9", "flathub",
               "1.1 GB", is_runtime=True),
]
FIREFOX_INFO = Package(
    "firefox", "146.0.1", "1.fc45", "x86_64", "updates", "Mozilla Firefox Web browser",
    "Mozilla Firefox is an open-source web browser, designed for standards "
    "compliance, performance and portability.", "68.2 MB", "264 MB",
    "https://www.mozilla.org/firefox/", "MPL-2.0 AND MIT", PackageStatus.INSTALLED)


class _Discover:
    discover_installed = True
    system_autostart_present = True
    per_user_disabled = True
    system_disabled = False
    restart_update_scheduled = False
    notifier_running = False


def fill(controller) -> None:
    controller.updates.set_reboot_required(True)


def after_navigate(controller, page: str, window) -> None:
    """Page-specific state for a screenshot."""
    if page not in ("activity", "running") and controller.runner.busy:
        # The sample run is over: other pages show their idle, enabled look.
        controller.runner._set(busy=False, status="idle", statusText="", step="",
                               progress=-1.0, operation="")
        controller.closeActivity()
    if page == "updates-details":
        from PyQt6.QtCore import Q_ARG, QMetaObject, Qt
        QMetaObject.invokeMethod(window, "openPackageDetails",
                                 Qt.ConnectionType.DirectConnection,
                                 Q_ARG("QVariant", "firefox"))
    elif page in ("activity", "running"):
        runner = controller.runner
        runner._begin("System Upgrade", "  System Upgrade")
        for line in ("$ pkexec dnf5 upgrade -y --refresh", "Updating and loading repositories:",
                     "Repositories loaded.",
                     "[ 1/10] firefox-0:146.0.1-1.fc45.x86_64   100% |  52.3 MiB/s |  68.2 MiB |  00m01s",
                     "[ 2/10] openssl-libs-1:3.5.4-2.fc45.x86_64   100% |  20.1 MiB/s |   2.4 MiB |  00m00s",
                     "[ 3/10] libheif-0:1.23.6-1.fc45.x86_64   100% |   9.8 MiB/s | 512.0 KiB |  00m00s",
                     "[ 4/10] kernel-core-0:7.2.8-300.fc45.x86_64    46% |  31.4 MiB/s |   8.7 MiB |  00m01s"):
            runner.append(line)
        runner._set(status="running", step="kernel-core-0:7.2.8-300.fc45.x86_64 (4 of 10)",
                    progress=0.4)
        if page == "activity":
            controller.toggleActivity(True)
        else:
            controller._set(activityVisible=True)
    elif page == "prompt":
        controller.updates.forceSecurity()
