"""Flatpak backend — manage Flatpak applications."""

import re
import subprocess
from dataclasses import dataclass
from typing import Optional
from dnf_gui.core.paths import system_binary


@dataclass
class FlatpakApp:
    """Represents a Flatpak application."""
    name: str
    application_id: str
    version: str = ""
    branch: str = ""
    origin: str = ""
    size: str = ""
    description: str = ""
    is_runtime: bool = False


# An app id or branch as flatpak prints them; never an option ("-x").
_FLATPAK_NAME = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]*")


def pick_remote(remotes: str) -> str:
    """The remote to install from: Flathub when the app is there, else
    the first remote search listed it in."""
    names = [r.strip() for r in (remotes or "").split(",")]
    names = [r for r in names if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", r)]
    if not names or "flathub" in names:
        return "flathub"
    return names[0]


class FlatpakBackend:
    """Interface to Flatpak CLI for managing Flatpak applications."""

    def __init__(self):
        self._flatpak = system_binary("flatpak")

    @property
    def available(self) -> bool:
        """Check if Flatpak is installed."""
        try:
            result = subprocess.run(
                [self._flatpak, "--version"],
                capture_output=True, text=True, timeout=5,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def list_installed(self) -> list[FlatpakApp]:
        """List installed Flatpak applications (not runtimes)."""
        result = self._run([
            self._flatpak, "list", "--app",
            "--columns=name,application,version,branch,origin,size",
        ])
        if result is None:
            return []
        return self._parse_list(result)


    def check_updates(self) -> list[FlatpakApp]:
        """Check for Flatpak updates."""
        result = self._run([
            self._flatpak, "remote-ls", "--updates",
            "--columns=name,application,version,branch,origin",
        ])
        if result is None:
            return []
        return self._parse_list(result)

    def search(self, query: str) -> list[FlatpakApp]:
        """Search for Flatpak applications on Flathub."""
        if not query or len(query) < 2:
            return []
        result = self._run([
            self._flatpak, "search", query,
            "--columns=name,application,version,branch,remotes,description",
        ])
        if result is None:
            return []
        return self._parse_search(result)

    # ─── Commands (for CommandWorker) ───────────────────────────────

    def build_install_command(self, app_id: str, remotes: str = "") -> list[str]:
        """Build command to install a Flatpak app from one of ``remotes``
        (search's comma-separated remotes column)."""
        return [self._flatpak, "install", "-y", pick_remote(remotes), app_id]

    def build_remove_command(self, app_id: str) -> list[str]:
        """Build command to remove a Flatpak app."""
        return [self._flatpak, "uninstall", "-y", app_id]

    def build_update_all_command(self) -> list[str]:
        """Build command to update all Flatpak apps."""
        return [self._flatpak, "update", "-y"]

    def build_update_command(self, app_id: str, branch: str = "") -> list[str]:
        """Build command to update one Flatpak app (``app_id//branch`` when
        the branch is known, so only that installed branch updates)."""
        if not _FLATPAK_NAME.fullmatch(app_id) or (branch and not _FLATPAK_NAME.fullmatch(branch)):
            raise ValueError(f"not a Flatpak app id: {app_id!r} {branch!r}")
        return [self._flatpak, "update", "-y", f"{app_id}//{branch}" if branch else app_id]

    def build_repair_command(self) -> list[str]:
        """Build command to repair Flatpak installation."""
        return [self._flatpak, "repair"]

    def build_remove_unused_command(self) -> list[str]:
        """Build command to remove unused runtimes."""
        return [self._flatpak, "uninstall", "--unused", "-y"]

    # ─── Private ────────────────────────────────────────────────────

    def _run(self, cmd: list[str]) -> Optional[str]:
        """Run a command and return stdout."""
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=60,
            )
            return result.stdout if result.returncode == 0 else None
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return None

    def _parse_list(self, output: str) -> list[FlatpakApp]:
        """Parse Flatpak list output."""
        apps = []
        for line in output.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) >= 2:
                apps.append(FlatpakApp(
                    name=parts[0].strip() if len(parts) > 0 else "",
                    application_id=parts[1].strip() if len(parts) > 1 else "",
                    version=parts[2].strip() if len(parts) > 2 else "",
                    branch=parts[3].strip() if len(parts) > 3 else "",
                    origin=parts[4].strip() if len(parts) > 4 else "",
                    size=parts[5].strip() if len(parts) > 5 else "",
                ))
        return apps

    def _parse_search(self, output: str) -> list[FlatpakApp]:
        """Parse Flatpak search output."""
        apps = []
        for line in output.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) >= 2:
                apps.append(FlatpakApp(
                    name=parts[0].strip() if len(parts) > 0 else "",
                    application_id=parts[1].strip() if len(parts) > 1 else "",
                    version=parts[2].strip() if len(parts) > 2 else "",
                    branch=parts[3].strip() if len(parts) > 3 else "",
                    origin=parts[4].strip() if len(parts) > 4 else "",
                    description=parts[5].strip() if len(parts) > 5 else "",
                ))
        return apps
