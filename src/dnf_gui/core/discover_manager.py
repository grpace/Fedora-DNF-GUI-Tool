"""Discover / PackageKit control — let DNF GUI take over updates from Discover.

Discover (plasma-discover) checks for updates via its own notifier:

  /etc/xdg/autostart/org.kde.discover.notifier.desktop
      Exec=/usr/libexec/DiscoverNotifier --check-delay 20

and stores its notification preferences in::

  ~/.config/PlasmaDiscoverUpdates  ([Global] RequiredNotificationInterval, UseUnattendedUpdates)

PackageKit offline updates are handled by systemd::

  packagekit-offline-update.service / packagekit.service

Why offer to disable it?
  * Discover uses PackageKit, which historically used the dnf4 backend and
    ignores things like ``dnf versionlock`` (PackageKit issue #444 /
    Fedora bug 2026184). Running both Discover and DNF GUI at the same
    time leads to double notifications, metadata refresh fights, and
    surprise offline updates on reboot.
  * This manager offers a *safe per-user* takeover (no root, reversible)
    plus an *optional system-wide* hardening (via pkexec, reversible).
"""

from __future__ import annotations

import configparser
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

SYSTEM_AUTOSTART = "/etc/xdg/autostart/org.kde.discover.notifier.desktop"
NOTIFIER_NAME = "org.kde.discover.notifier.desktop"
NOTIFIER_BINARY_NAMES = ("DiscoverNotifier", "discover-notifier")


def _user_autostart_path() -> Path:
    return Path.home() / ".config" / "autostart" / NOTIFIER_NAME


def _discover_updates_config() -> Path:
    return Path.home() / ".config" / "PlasmaDiscoverUpdates"


@dataclass
class DiscoverStatus:
    """Point-in-time view of Discover's update behaviour."""

    system_autostart_present: bool = False
    per_user_override_present: bool = False
    per_user_disabled: bool = False  # Hidden=true in ~/.config/autostart
    notifier_running: bool = False
    # PlasmaDiscoverUpdates values (None = key/file absent)
    notification_interval: Optional[str] = None
    unattended_updates: Optional[str] = None
    notifications_silenced: bool = False
    packagekit_offline_active: bool = False
    discover_installed: bool = False

    @property
    def effectively_quiet(self) -> bool:
        """True when Discover will not pop update notifications."""
        return self.per_user_disabled or self.notifications_silenced


class DiscoverManager:
    """Inspect and toggle Discover's automatic update behaviour."""

    # ─── Status ───────────────────────────────────────────────────

    def get_status(self) -> DiscoverStatus:
        status = DiscoverStatus()
        status.system_autostart_present = os.path.exists(SYSTEM_AUTOSTART)
        user_path = _user_autostart_path()
        status.per_user_override_present = user_path.exists()
        if user_path.exists():
            try:
                text = user_path.read_text(errors="replace")
                status.per_user_disabled = "Hidden=true" in text
            except OSError:
                pass
        status.notifier_running = self.is_notifier_running()
        interval, unattended = self._read_discover_config()
        status.notification_interval = interval
        status.unattended_updates = unattended
        status.notifications_silenced = (interval is not None and interval.strip() == "-1")
        status.packagekit_offline_active = self._is_packagekit_offline_active()
        status.discover_installed = bool(
            shutil.which("plasma-discover") or shutil.which("plasma-discover-notifier")
            or os.path.exists("/usr/bin/plasma-discover")
        )
        return status

    def _read_discover_config(self) -> tuple[Optional[str], Optional[str]]:
        cfg_path = _discover_updates_config()
        if not cfg_path.exists():
            return None, None
        parser = configparser.ConfigParser()
        try:
            parser.read(cfg_path)
            interval = None
            unattended = None
            if parser.has_section("Global"):
                if parser.has_option("Global", "RequiredNotificationInterval"):
                    interval = parser.get("Global", "RequiredNotificationInterval")
                if parser.has_option("Global", "UseUnattendedUpdates"):
                    unattended = parser.get("Global", "UseUnattendedUpdates")
            return interval, unattended
        except (configparser.Error, OSError):
            return None, None

    def is_notifier_running(self) -> bool:
        for binary in NOTIFIER_BINARY_NAMES:
            try:
                result = subprocess.run(
                    ["pgrep", "-x", binary],
                    capture_output=True, text=True, timeout=5,
                )
                if result.returncode == 0 and result.stdout.strip():
                    # pgrep -x matches exact process name — our python
                    # process is named "python3", so any hit is real.
                    return True
            except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
                continue
        return False

    def _is_packagekit_offline_active(self) -> bool:
        try:
            result = subprocess.run(
                ["systemctl", "is-active", "packagekit-offline-update.service"],
                capture_output=True, text=True, timeout=5,
            )
            return result.stdout.strip() == "active"
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return False

    # ─── Per-user takeover (no root, reversible) ──────────────────

    def set_per_user_enabled(self, enabled: bool) -> None:
        """Enable/disable Discover's notifier for the current user only.

        Disabled = write ``~/.config/autostart/org.kde.discover.notifier.desktop``
        with ``Hidden=true`` (freedesktop autostart spec) and silence
        ``PlasmaDiscoverUpdates`` notifications. Enabling removes the
        override and restores a daily notification interval.
        """
        user_path = _user_autostart_path()
        if enabled:
            # Re-enable: remove override + restore notification interval
            try:
                if user_path.exists():
                    user_path.unlink()
            except OSError:
                pass
            self._write_discover_config(notification_interval="86400",
                                        unattended_updates="false")
        else:
            user_path.parent.mkdir(parents=True, exist_ok=True)
            # Prefer copying the system desktop file so "Hidden=true"
            # override stays valid; fall back to a minimal entry.
            content: Optional[str] = None
            if os.path.exists(SYSTEM_AUTOSTART):
                try:
                    content = Path(SYSTEM_AUTOSTART).read_text(errors="replace")
                except OSError:
                    content = None
            if not content or "[Desktop Entry]" not in content:
                content = (
                    "[Desktop Entry]\n"
                    "Name=Discover Notifier\n"
                    "Exec=/usr/libexec/DiscoverNotifier\n"
                    "Type=Application\n"
                    "X-KDE-AutostartScript=true\n"
                )
            if "Hidden=" in content:
                lines = [l for l in content.splitlines()
                         if not l.strip().startswith("Hidden=")]
                content = "\n".join(lines) + "\n"
            if not content.endswith("\n"):
                content += "\n"
            content += "Hidden=true\n"
            user_path.write_text(content)
            self._write_discover_config(notification_interval="-1",
                                        unattended_updates="false")

    def _write_discover_config(self, notification_interval: str,
                               unattended_updates: str) -> None:
        cfg_path = _discover_updates_config()
        parser = configparser.ConfigParser()
        # Preserve existing keys where possible
        try:
            if cfg_path.exists():
                parser.read(cfg_path)
        except (configparser.Error, OSError):
            parser = configparser.ConfigParser()
        if not parser.has_section("Global"):
            parser.add_section("Global")
        parser.set("Global", "RequiredNotificationInterval", notification_interval)
        parser.set("Global", "UseUnattendedUpdates", unattended_updates)
        try:
            cfg_path.parent.mkdir(parents=True, exist_ok=True)
            with cfg_path.open("w") as f:
                parser.write(f)
        except OSError:
            pass

    def build_kill_notifier_command(self) -> list[str]:
        """Build command to stop a running DiscoverNotifier (no root)."""
        return ["pkill", "-x", "DiscoverNotifier"]

    # ─── System-wide hardening (needs root via pkexec) ────────────

    def build_system_disable_commands(self) -> list[list[str]]:
        """Commands (run with pkexec) to stop Discover/PackageKit system-wide.

        1. Remove the system autostart entry so the notifier never starts.
        2. Mask packagekit-offline-update so no surprise offline updates run
           on reboot/shutdown. ``packagekit.service`` itself is left alone
           so manual pkcon use still works.
        """
        return [
            ["pkexec", "bash", "-c",
             f"rm -f {SYSTEM_AUTOSTART} && "
             "systemctl mask --now packagekit-offline-update.service || "
             "systemctl mask packagekit-offline-update.service"],
        ]

    def build_system_enable_commands(self) -> list[list[str]]:
        """Re-enable what :meth:`build_system_disable_commands` turned off."""
        return [
            ["pkexec", "bash", "-c",
             "systemctl unmask packagekit-offline-update.service; "
             "systemctl unmask packagekit.service || true"],
        ]

    def build_remove_notifier_package_command(self) -> list[str]:
        """Offer to remove plasma-discover-notifier but keep Discover itself."""
        dnf = shutil.which("dnf5") or shutil.which("dnf") or "dnf"
        return ["pkexec", dnf, "remove", "-y", "plasma-discover-notifier"]
