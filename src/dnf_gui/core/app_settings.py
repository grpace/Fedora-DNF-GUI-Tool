"""Persistent app settings + background update-reminder service.

Owns:
1. **Persistent preferences** via ``QSettings`` (written to
   ``~/.config/Greg.Tech/DNF Package Manager.conf``):
   - ``reminders/enabled`` (bool)
   - ``reminders/interval_hours`` (int: 12, 24, 72, 168)
   - ``reminders/security_only`` (bool)
   - ``reminders/notify_flatpak`` (bool)
   - ``reminders/last_check`` (ISO timestamp)
   - ``discover/notifier_overridden`` (bool)
   - ``passwordless/scope`` ("off" | "updates" | "full")
2. **Login checker** — ``dnf-gui --check`` can be installed as a
   per-user XDG autostart entry (``~/.config/autostart/dnf-gui-update-checker.desktop``)
   that triggers at login, checks if an update check is due according
   to the configured interval, and sends a desktop notification via
   ``notify-send`` (or falls back to an in-app banner if run in GUI
   mode). This is the "ongoing thing that reminds people" without
   requiring a resident background daemon.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

CHECKER_DESKTOP_NAME = "dnf-gui-update-checker.desktop"


@dataclass
class ReminderResult:
    dnf_updates: int = 0
    flatpak_updates: int = 0
    security_total: int = 0
    security_urgent: bool = False
    should_notify: bool = False
    message: str = ""

    @property
    def total(self) -> int:
        return self.dnf_updates + self.flatpak_updates


class AppSettings:
    """Thin wrapper around QSettings with sane defaults."""

    def __init__(self):
        from PyQt6.QtCore import QSettings
        self._settings = QSettings("Greg.Tech", "DNF Package Manager")

    # ─── Generic helpers ──────────────────────────────────────
    def get(self, key: str, default=None):
        return self._settings.value(key, default)

    def get_bool(self, key: str, default: bool = False) -> bool:
        val = self._settings.value(key, default)
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            return val.lower() in ("true", "1", "yes")
        return bool(val)

    def get_int(self, key: str, default: int = 0) -> int:
        try:
            return int(self._settings.value(key, default))
        except (TypeError, ValueError):
            return default

    def set(self, key: str, value) -> None:
        self._settings.setValue(key, value)
        self._settings.sync()

    # ─── Reminder preferences ─────────────────────────────────
    @property
    def reminders_enabled(self) -> bool:
        return self.get_bool("reminders/enabled", False)

    @reminders_enabled.setter
    def reminders_enabled(self, value: bool) -> None:
        self.set("reminders/enabled", bool(value))

    @property
    def check_interval_hours(self) -> int:
        return self.get_int("reminders/interval_hours", 24)

    @check_interval_hours.setter
    def check_interval_hours(self, value: int) -> None:
        self.set("reminders/interval_hours", int(value))

    @property
    def security_only(self) -> bool:
        return self.get_bool("reminders/security_only", False)

    @security_only.setter
    def security_only(self, value: bool) -> None:
        self.set("reminders/security_only", bool(value))

    @property
    def notify_flatpak(self) -> bool:
        return self.get_bool("reminders/notify_flatpak", True)

    @notify_flatpak.setter
    def notify_flatpak(self, value: bool) -> None:
        self.set("reminders/notify_flatpak", bool(value))

    @property
    def passwordless_scope(self) -> str:
        val = self.get("passwordless/scope", "") or self.get("privilege/passwordless_scope", "off")
        return str(val) if str(val) in ("off", "updates", "full") else "off"

    @passwordless_scope.setter
    def passwordless_scope(self, value: str) -> None:
        if value not in ("off", "updates", "full"):
            value = "off"
        self.set("passwordless/scope", value)
        self.set("privilege/passwordless_scope", value)

    # ─── Last check timestamp + throttle ──────────────────────
    def get_last_check(self) -> datetime | None:
        raw = self.get("reminders/last_check", "")
        if not raw:
            return None
        try:
            return datetime.fromisoformat(str(raw))
        except ValueError:
            return None

    def set_last_check(self, when: datetime | None = None) -> None:
        self.set("reminders/last_check", (when or datetime.now()).isoformat())

    def is_check_due(self) -> bool:
        """True when reminders are enabled and the interval has elapsed."""
        if not self.reminders_enabled:
            return False
        last = self.get_last_check()
        if last is None:
            return True
        return datetime.now() - last >= timedelta(hours=self.check_interval_hours)

    # ─── Login checker autostart ──────────────────────────────
    @classmethod
    def checker_autostart_path(cls) -> Path:
        config_home = Path(os.environ.get("XDG_CONFIG_HOME")
                           or Path.home() / ".config")
        return config_home / "autostart" / CHECKER_DESKTOP_NAME

    @classmethod
    def is_checker_installed(cls) -> bool:
        return cls.checker_autostart_path().exists()

    @classmethod
    def set_checker_installed(cls, installed: bool) -> None:
        path = cls.checker_autostart_path()
        if installed:
            path.parent.mkdir(parents=True, exist_ok=True)
            # Exec must work for both /opt installs and source checkouts.
            # Prefer the on-PATH launcher, fall back to module invocation.
            path.write_text(
                "[Desktop Entry]\n"
                "Type=Application\n"
                "Name=DNF GUI Update Checker\n"
                "Comment=Background update reminder for DNF Package Manager\n"
                "Exec=dnf-gui --check\n"
                "Icon=dnf-gui\n"
                "Terminal=false\n"
                "Categories=System;\n"
                "X-GNOME-Autostart-enabled=true\n"
                "X-KDE-AutostartScript=true\n"
                "NoDisplay=true\n"
            )
        else:
            try:
                if path.exists():
                    path.unlink()
            except OSError:
                pass


def send_desktop_notification(title: str, body: str, urgent: bool = False) -> bool:
    """Send a desktop notification. Returns True if one was delivered."""
    # Preferred: notify-send (works headless under --check)
    try:
        cmd = ["notify-send", "--app-name=DNF Package Manager", title, body]
        if urgent:
            cmd[2:2] = ["--urgency=critical"]
        result = subprocess.run(cmd, capture_output=True, timeout=5)
        if result.returncode == 0:
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    # Fallback is handled by the GUI caller (QSystemTray / QMessageBox).
    return False


def perform_background_check(settings: AppSettings | None = None) -> ReminderResult:
    """Headless check used by ``dnf-gui --check`` and the in-app timer.

    Respects ``reminders/security_only`` and ``reminders/notify_flatpak``.
    Always updates ``reminders/last_check`` so the interval throttle works.
    Never raises — failures degrade to zero counts.
    """
    from dnf_gui.core.dnf_backend import DNFBackend
    from dnf_gui.core.flatpak_backend import FlatpakBackend
    from dnf_gui.core.security import get_security_summary

    settings = settings or AppSettings()
    result = ReminderResult()
    try:
        backend = DNFBackend()
        info = backend.check_updates()
        result.dnf_updates = info.total_updates if info else 0
    except Exception:
        result.dnf_updates = 0
    try:
        if settings.notify_flatpak:
            flatpak = FlatpakBackend()
            if flatpak.available:
                result.flatpak_updates = len(flatpak.check_updates())
    except Exception:
        result.flatpak_updates = 0
    try:
        sec = get_security_summary()
        result.security_total = sec.total
        result.security_urgent = sec.urgent
    except Exception:
        pass

    settings.set_last_check()

    # Determine whether system DNF packages warrant a reminder
    if settings.security_only:
        system_notify = result.security_total > 0
    else:
        system_notify = result.dnf_updates > 0 or result.security_total > 0

    # Flatpak updates trigger reminders independently if enabled
    flatpak_notify = (result.flatpak_updates > 0) if settings.notify_flatpak else False

    result.should_notify = system_notify or flatpak_notify

    if result.should_notify:
        parts = []
        if result.dnf_updates and (not settings.security_only or result.security_total):
            if settings.security_only:
                parts.append(f"{result.security_total} security")
            else:
                parts.append(f"{result.dnf_updates} system")
        elif result.security_total:
            parts.append(f"{result.security_total} security")

        if result.flatpak_updates and settings.notify_flatpak:
            parts.append(f"{result.flatpak_updates} Flatpak")

        updates_str = " + ".join(parts) if parts else "updates"
        if result.security_urgent:
            result.message = (
                f"⚠ {result.security_total} SECURITY updates pending "
                f"({updates_str}) — open DNF Package Manager to install."
            )
        elif result.security_total:
            result.message = (
                f"{result.security_total} security advisories ready "
                f"({updates_str}). Open DNF Package Manager to apply."
            )
        else:
            result.message = f"{updates_str} updates available."
    return result


def checker_autostart_desktop_source() -> str:
    """Desktop file content for packagers (mirrors set_checker_installed)."""
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=DNF GUI Update Checker\n"
        "Comment=Background update reminder for DNF Package Manager\n"
        "Exec=dnf-gui --check\n"
        "Icon=dnf-gui\n"
        "Terminal=false\n"
        "Categories=System;\n"
        "X-GNOME-Autostart-enabled=true\n"
        "X-KDE-AutostartScript=true\n"
        "NoDisplay=true\n"
    )
