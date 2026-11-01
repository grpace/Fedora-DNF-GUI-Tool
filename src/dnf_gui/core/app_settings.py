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
   - ``updates/held_back`` (comma-separated globs for "Update without Major")
   - ``updates/favorite`` (update mode on the main Updates button)
   - ``upgrade/dismissed_release`` (Fedora release the upgrade banner was dismissed for)
2. **Background checker** — ``dnf-gui --check --scheduled`` runs from a
   per-user systemd service, started by a timer whose schedule follows
   ``reminders/interval_hours`` and once at each login. The service only
   runs inside a graphical session, so nothing fires before login. Each
   run compares the last check with the interval and exits at once unless
   a check is due. A failed check (offline) is retried at most 3 times,
   15 minutes apart. Nothing stays resident and nothing polls.
   Without systemd, an XDG autostart entry runs the check at login instead.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

CHECKER_DESKTOP_NAME = "dnf-gui-update-checker.desktop"
CHECKER_SERVICE = "dnf-gui-update-checker.service"
CHECKER_TIMER = "dnf-gui-update-checker.timer"
# Update modes for the main Updates button; the first is the default.
UPDATE_MODE_KEYS = ("all", "everything", "minor", "security")


@dataclass
class ReminderResult:
    dnf_updates: int = 0
    flatpak_updates: int = 0
    security_total: int = 0
    security_urgent: bool = False
    # Advisories left out of security_total because they can't install yet.
    security_waiting: int = 0
    should_notify: bool = False
    message: str = ""
    # dnf couldn't check (e.g. offline): counts are unknown, and the
    # check doesn't count against the interval.
    check_failed: bool = False

    @property
    def total(self) -> int:
        return self.dnf_updates + self.flatpak_updates


def _checker_command(scheduled: bool = False) -> list[str]:
    """argv for the check: the RPM/install.sh launcher if present, else
    this interpreter + module (pip installs only ship fedora-dnf-gui)."""
    import shutil
    import sys
    launcher = shutil.which("dnf-gui")
    argv = [launcher] if launcher else [sys.executable, "-m", "dnf_gui"]
    return argv + (["--check", "--scheduled"] if scheduled else ["--check"])


def _quote_exec(argv: list[str]) -> str:
    """Join argv for a systemd ExecStart= or desktop-entry Exec= line."""
    return " ".join(f'"{a}"' if (" " in a or not a) else a for a in argv)


def _systemctl_user(*args: str) -> bool:
    """Run ``systemctl --user ARGS``. False if systemd isn't usable."""
    try:
        result = subprocess.run(["systemctl", "--user", *args],
                                capture_output=True, timeout=30)
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def network_online(timeout: int = 0) -> bool:
    """True when NetworkManager reports a connection, waiting up to
    ``timeout`` seconds for one. Assumes True if it can't tell."""
    try:
        result = subprocess.run(["nm-online", "-q", "-x", "-t", str(timeout)],
                                capture_output=True, timeout=timeout + 10)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return True
    return result.returncode == 0


def wait_for_desktop(timeout: float = 120, poll: float = 5) -> bool:
    """Wait up to ``timeout`` seconds for a notification server and a
    network connection, e.g. right after login or resume."""
    import time
    deadline = time.monotonic() + timeout
    while not notification_server_available():
        if time.monotonic() >= deadline:
            return False
        time.sleep(poll)
    return network_online(max(0, int(deadline - time.monotonic())))


def notification_server_available() -> bool:
    """True when something owns org.freedesktop.Notifications.

    The timer also fires before login (e.g. with lingering enabled), when
    a notification would be lost. Assumes True if it can't tell.
    """
    try:
        result = subprocess.run(
            ["busctl", "--user", "call", "org.freedesktop.DBus",
             "/org/freedesktop/DBus", "org.freedesktop.DBus",
             "NameHasOwner", "s", "org.freedesktop.Notifications"],
            capture_output=True, text=True, timeout=5)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return True
    if result.returncode != 0:
        return False  # no session bus reachable
    return result.stdout.strip() != "b false"


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

    @property
    def dismissed_release(self) -> int:
        """Highest Fedora release the user said "Not now" to."""
        return self.get_int("upgrade/dismissed_release", 0)

    @dismissed_release.setter
    def dismissed_release(self, value: int) -> None:
        self.set("upgrade/dismissed_release", int(value))

    @property
    def update_favorite(self) -> str:
        value = str(self.get("updates/favorite", UPDATE_MODE_KEYS[0]))
        return value if value in UPDATE_MODE_KEYS else UPDATE_MODE_KEYS[0]

    @update_favorite.setter
    def update_favorite(self, key: str) -> None:
        self.set("updates/favorite", key)

    @property
    def held_back_patterns(self) -> list[str]:
        from dnf_gui.core.dnf_backend import (
            DEFAULT_HELD_BACK_PATTERNS, parse_held_back_patterns,
        )
        raw = self.get("updates/held_back", None)
        if raw is None or str(raw).strip() == "":
            return list(DEFAULT_HELD_BACK_PATTERNS)
        if isinstance(raw, (list, tuple)):  # QSettings may hand back a list
            raw = ",".join(str(r) for r in raw)
        valid, _invalid = parse_held_back_patterns(str(raw))
        return valid or list(DEFAULT_HELD_BACK_PATTERNS)

    @held_back_patterns.setter
    def held_back_patterns(self, patterns) -> None:
        self.set("updates/held_back", ", ".join(patterns or []))

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

    def is_check_due(self, fraction: float = 1.0) -> bool:
        """True when reminders are enabled and ``fraction`` of the interval
        has elapsed since the last check."""
        if not self.reminders_enabled:
            return False
        last = self.get_last_check()
        if last is None:
            return True
        return datetime.now() - last >= timedelta(
            hours=self.check_interval_hours * fraction)

    # ─── Background checker (systemd timer + login trigger) ───
    @classmethod
    def checker_autostart_path(cls) -> Path:
        return _config_home() / "autostart" / CHECKER_DESKTOP_NAME

    @classmethod
    def checker_unit_dir(cls) -> Path:
        return _config_home() / "systemd" / "user"

    @classmethod
    def is_checker_installed(cls) -> bool:
        return (cls.checker_autostart_path().exists()
                or (cls.checker_unit_dir() / CHECKER_TIMER).exists())

    @classmethod
    def checker_needs_refresh(cls, interval_hours: int) -> bool:
        """True when the timer is missing, out of date or on the wrong
        schedule (e.g. the login-only entry older versions installed)."""
        if cls.checker_autostart_path().exists():
            return True
        unit_dir = cls.checker_unit_dir()
        wanted = {
            unit_dir / CHECKER_SERVICE: _service_unit(),
            unit_dir / CHECKER_TIMER: _timer_unit(interval_hours),
        }
        for path, content in wanted.items():
            try:
                if path.read_text() != content:
                    return True
            except OSError:
                return True
        return False

    @classmethod
    def set_checker_installed(cls, installed: bool,
                              interval_hours: int = 24) -> bool:
        """Install or remove the background checker.

        Returns True when the systemd timer is active (or was removed).
        False on install means only the login check is in place.
        """
        unit_dir = cls.checker_unit_dir()
        service = unit_dir / CHECKER_SERVICE
        timer = unit_dir / CHECKER_TIMER
        autostart = cls.checker_autostart_path()
        if not installed:
            if timer.exists() or service.exists():
                _systemctl_user("disable", "--now", CHECKER_TIMER, CHECKER_SERVICE)
            for path in (timer, service, autostart):
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass
            _systemctl_user("daemon-reload")
            return True

        unit_dir.mkdir(parents=True, exist_ok=True)
        service.write_text(_service_unit())
        timer.write_text(_timer_unit(interval_hours))
        # Enabling the service hooks it to login; restart re-arms the timer
        # if its schedule changed.
        use_systemd = (_systemctl_user("daemon-reload")
                       and _systemctl_user("enable", CHECKER_TIMER, CHECKER_SERVICE)
                       and _systemctl_user("restart", CHECKER_TIMER))
        if use_systemd:
            try:
                autostart.unlink(missing_ok=True)  # pre-1.3 login-only checker
            except OSError:
                pass
        else:
            for path in (timer, service):
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass
            autostart.parent.mkdir(parents=True, exist_ok=True)
            autostart.write_text(_autostart_entry())
        return use_systemd


def _config_home() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")


def _installed_condition() -> str:
    """Unit lines that skip the run (no failure, no retries) once the app
    is uninstalled, since its per-user units outlive the package."""
    argv = _checker_command()
    if argv[1:2] == ["-m"]:  # pip/source install: the interpreter stays
        return f"ExecCondition={_quote_exec([argv[0], '-c', 'import dnf_gui'])}\n"
    return f"ConditionPathExists={argv[0]}\n"


def _service_unit() -> str:
    condition = _installed_condition()
    unit_condition = condition if condition.startswith("Condition") else ""
    exec_condition = "" if unit_condition else condition
    return (
        "[Unit]\n"
        "Description=DNF Package Manager update reminder\n"
        "Documentation=https://github.com/grpace/Fedora-DNF-GUI-Tool\n"
        "# Only inside a desktop session: before login there's nobody to\n"
        "# notify, and the login start below catches up.\n"
        "Requisite=graphical-session.target\n"
        "After=graphical-session.target\n"
        "# The first run plus at most 3 retries an hour.\n"
        "StartLimitIntervalSec=1h\n"
        "StartLimitBurst=4\n"
        "# Skip quietly once the app is uninstalled.\n"
        f"{unit_condition}"
        "\n"
        "[Service]\n"
        "Type=oneshot\n"
        f"{exec_condition}"
        f"ExecStart={_quote_exec(_checker_command(scheduled=True))}\n"
        "# Exit code 2 means updates are pending, not a failure.\n"
        "SuccessExitStatus=2\n"
        "# Exit code 1: still offline or undelivered after waiting.\n"
        "Restart=on-failure\n"
        "RestartSec=15min\n"
        "Nice=10\n"
        "IOSchedulingClass=idle\n"
        "TimeoutStartSec=15min\n"
        "\n"
        "[Install]\n"
        "# Also start at login; the run exits at once unless a check is due.\n"
        "WantedBy=graphical-session.target\n"
    )


# OnCalendar= for each "Check Every" choice. Every 3 Days alternates 3- and
# 4-day gaps, the closest a calendar schedule gets.
_TIMER_SCHEDULES = {
    12: "*-*-* 09,21:00:00",
    24: "*-*-* 09:00:00",
    72: "Mon,Thu *-*-* 09:00:00",
    168: "Mon *-*-* 09:00:00",
}


def _timer_unit(interval_hours: int) -> str:
    schedule = _TIMER_SCHEDULES.get(int(interval_hours), _TIMER_SCHEDULES[24])
    return (
        "[Unit]\n"
        "Description=Scheduled DNF Package Manager update reminder\n"
        "\n"
        "[Timer]\n"
        f"OnCalendar={schedule}\n"
        "# Run a missed check once the PC is back on or awake.\n"
        "Persistent=true\n"
        "RandomizedDelaySec=10min\n"
        "\n"
        "[Install]\n"
        "WantedBy=timers.target\n"
    )


def _autostart_entry() -> str:
    """Login check for systems without a systemd user session."""
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=DNF GUI Update Checker\n"
        "Comment=Background update reminder for DNF Package Manager\n"
        f"Exec={_quote_exec(_checker_command())}\n"
        # Ignored once the app is uninstalled.
        f"TryExec={_checker_command()[0]}\n"
        "Icon=dnf-gui\n"
        "Terminal=false\n"
        "Categories=System;\n"
        "X-GNOME-Autostart-enabled=true\n"
        "X-KDE-AutostartScript=true\n"
        "NoDisplay=true\n"
    )


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


def perform_background_check(settings: AppSettings | None = None,
                             security_only: bool | None = None) -> ReminderResult:
    """Headless check used by ``dnf-gui --check`` and the in-app timer.

    Respects ``reminders/security_only`` and ``reminders/notify_flatpak``.
    Updates ``reminders/last_check`` unless dnf failed, so an offline run
    is retried on the next wake-up instead of silencing a whole interval.
    Never raises — failures degrade to zero counts. ``security_only``
    overrides the saved preference for this run without persisting it.
    """
    from dnf_gui.core.dnf_backend import DNFBackend
    from dnf_gui.core.flatpak_backend import FlatpakBackend
    from dnf_gui.core.security import find_blocked_security, get_security_summary

    settings = settings or AppSettings()
    if security_only is None:
        security_only = settings.security_only
    result = ReminderResult()
    try:
        backend = DNFBackend()
        info = backend.check_updates()
        result.dnf_updates = info.total_updates if info else 0
        result.check_failed = bool(getattr(info, "check_failed", False))
    except Exception:
        result.dnf_updates = 0
        result.check_failed = True
    try:
        if settings.notify_flatpak:
            flatpak = FlatpakBackend()
            if flatpak.available:
                result.flatpak_updates = len(flatpak.check_updates())
    except Exception:
        result.flatpak_updates = 0
    try:
        sec = get_security_summary()
        # Don't remind about advisories nobody can install yet (e.g. waiting
        # on an RPM Fusion rebuild); they come back once installable.
        find_blocked_security(sec)
        result.security_total = sec.installable_total
        result.security_urgent = sec.installable_urgent
        result.security_waiting = len(sec.blocked_advisories)
    except Exception:
        pass

    if not result.check_failed:
        settings.set_last_check()

    # Determine whether system DNF packages warrant a reminder
    if security_only:
        system_notify = result.security_total > 0
    else:
        system_notify = result.dnf_updates > 0 or result.security_total > 0

    # Flatpak updates trigger reminders independently if enabled
    flatpak_notify = (result.flatpak_updates > 0) if settings.notify_flatpak else False

    result.should_notify = system_notify or flatpak_notify

    if result.should_notify:
        parts = []
        if result.dnf_updates and (not security_only or result.security_total):
            if security_only:
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
