"""Fedora release upgrades (e.g. 44 → 45) via ``dnf system-upgrade``.

Availability comes from Fedora's Bodhi release list (the same source GNOME
Software uses): only releases in the "current" state count, so betas and
release candidates are never offered. Fedora supports upgrading up to two
releases at once, so the newest current release within that range wins.

The upgrade itself is the documented three-step flow:

1. ``dnf upgrade --refresh`` (bring the current release fully up to date)
2. ``dnf system-upgrade download --releasever=N`` (download; system usable)
3. ``dnf system-upgrade reboot`` (reboot into the offline install)
"""

from __future__ import annotations

import json
import subprocess
import tomllib
import urllib.request
from dataclasses import dataclass

BODHI_RELEASES_URL = (
    "https://bodhi.fedoraproject.org/releases/?exclude_archived=True&rows_per_page=100")
RELEASE_NOTES_URL = "https://docs.fedoraproject.org/en-US/fedora/latest/release-notes/"
UPGRADE_DOCS_URL = "https://docs.fedoraproject.org/en-US/quick-docs/upgrading-fedora-offline/"
# dnf5 writes this world-readable state file once a download is stored.
OFFLINE_STATE_FILE = "/usr/lib/sysimage/libdnf5/offline/offline-transaction-state.toml"
MAX_RELEASE_JUMP = 2


@dataclass
class ReleaseUpgrade:
    current: int
    target: int
    current_eol: str = ""  # YYYY-MM-DD, when known
    downloaded: bool = False


def current_release() -> int | None:
    try:
        out = subprocess.run(["rpm", "-E", "%fedora"], capture_output=True,
                             text=True, timeout=10).stdout.strip()
        return int(out)
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None


def fetch_releases(timeout: int = 10) -> list[dict]:
    """Fedora (not EPEL/ELN/containers) releases from Bodhi; [] on failure."""
    try:
        req = urllib.request.Request(BODHI_RELEASES_URL, headers={"User-Agent": "dnf-gui"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return []
    releases = []
    for rel in data.get("releases", []):
        name = str(rel.get("name", ""))
        if rel.get("id_prefix") == "FEDORA" and name[:1] == "F" and name[1:].isdigit():
            releases.append(rel)
    return releases


def pick_target(current: int, releases: list[dict]) -> tuple[int | None, str]:
    """(newest upgradable current release or None, current release's EOL)."""
    target = None
    current_eol = ""
    for rel in releases:
        try:
            version = int(rel.get("version"))
        except (TypeError, ValueError):
            continue
        if version == current:
            current_eol = str(rel.get("eol") or "")
        if (rel.get("state") == "current"
                and current < version <= current + MAX_RELEASE_JUMP
                and (target is None or version > target)):
            target = version
    return target, current_eol


def downloaded_release(path: str = OFFLINE_STATE_FILE) -> int | None:
    """Release whose system-upgrade download is stored and ready, if any."""
    try:
        with open(path, "rb") as f:
            state = tomllib.load(f).get("offline-transaction-state", {})
    except (OSError, tomllib.TOMLDecodeError):
        return None
    if (state.get("status") == "download-complete"
            and str(state.get("verb", "")).startswith("system-upgrade")):
        try:
            return int(state.get("target_releasever"))
        except (TypeError, ValueError):
            return None
    return None


def check_release_upgrade() -> ReleaseUpgrade | None:
    """What release upgrade to offer right now, if any. Never raises."""
    current = current_release()
    if current is None:
        return None
    downloaded = downloaded_release()
    releases = fetch_releases()
    target, current_eol = pick_target(current, releases)
    if downloaded and downloaded > current:
        return ReleaseUpgrade(current, downloaded, current_eol, downloaded=True)
    if target is None:
        return None
    return ReleaseUpgrade(current, target, current_eol)


def build_download_command(dnf: str, target: int,
                           allow_erasing: bool = False) -> list[str]:
    cmd = ["pkexec", dnf, "system-upgrade", "download", f"--releasever={int(target)}", "-y"]
    if allow_erasing:
        cmd.append("--allowerasing")
    return cmd


def build_reboot_command(dnf: str) -> list[str]:
    return ["pkexec", dnf, "system-upgrade", "reboot"]


def build_clean_command(dnf: str) -> list[str]:
    return ["pkexec", dnf, "system-upgrade", "clean"]
