"""App update checker — fetches latest release from GitHub and compares versions."""

import json
import urllib.request
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

GITHUB_API_URL = "https://api.github.com/repos/gregtech/fedora-dnf-gui/releases/latest"
RELEASES_PAGE_URL = "https://github.com/gregtech/fedora-dnf-gui/releases"

# Allowed hosts for update downloads (GitHub CDN domains)
_ALLOWED_DOWNLOAD_HOSTS = (
    "github.com",
    "objects.githubusercontent.com",
    "github-releases.githubusercontent.com",
)


def _is_safe_download_url(url: str) -> bool:
    """Validate that a download URL is from a trusted GitHub host."""
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url)
        if parsed.scheme != "https":
            return False
        netloc = parsed.netloc.lower()
        return any(
            netloc == h or netloc.endswith("." + h)
            for h in _ALLOWED_DOWNLOAD_HOSTS
        )
    except Exception:
        return False


@dataclass
class UpdateInfo:
    """Information about an available app update."""

    latest_version: str
    download_url: str
    release_url: str
    release_notes: str = ""


def _parse_version(version_str: str) -> list[int]:
    """Parse version string (e.g. '1.2.0' or 'v1.2.0') into comparable parts."""
    # Strip 'v' prefix
    s = version_str.lstrip("vV")
    parts = []
    for part in s.split("."):
        try:
            parts.append(int(part))
        except ValueError:
            parts.append(0)
    return parts


def _version_compare(current: str, latest: str) -> int:
    """
    Compare two version strings.
    Returns: -1 if current < latest, 0 if equal, 1 if current > latest
    """
    cur_parts = _parse_version(current)
    lat_parts = _parse_version(latest)
    for i in range(max(len(cur_parts), len(lat_parts))):
        c = cur_parts[i] if i < len(cur_parts) else 0
        l = lat_parts[i] if i < len(lat_parts) else 0
        if c < l:
            return -1
        if c > l:
            return 1
    return 0


def check_for_update(current_version: str) -> Optional[UpdateInfo]:
    """
    Check GitHub for the latest release. Returns UpdateInfo if a newer version
    exists, otherwise None. Returns None on any error (network, parse, etc.).
    """
    try:
        req = urllib.request.Request(
            GITHUB_API_URL,
            headers={"Accept": "application/vnd.github.v3+json", "User-Agent": "dnf-gui"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return None

    tag_name = data.get("tag_name", "")
    if not tag_name:
        return None

    # Extract version from tag (e.g. "v1.2.0" -> "1.2.0")
    latest_version = tag_name.lstrip("vV")

    if _version_compare(current_version, latest_version) >= 0:
        return None

    # Find the .noarch.rpm asset (validate URL is from trusted GitHub hosts)
    download_url = ""
    assets = data.get("assets", [])
    for asset in assets:
        name = asset.get("name", "")
        if name.endswith(".noarch.rpm"):
            candidate = asset.get("browser_download_url", "")
            if _is_safe_download_url(candidate):
                download_url = candidate
            break

    # Fallback: use first .rpm asset if no noarch
    if not download_url:
        for asset in assets:
            name = asset.get("name", "")
            if name.endswith(".rpm"):
                candidate = asset.get("browser_download_url", "")
                if _is_safe_download_url(candidate):
                    download_url = candidate
                break

    release_url = data.get("html_url", RELEASES_PAGE_URL)
    body = data.get("body", "")

    return UpdateInfo(
        latest_version=latest_version,
        download_url=download_url,
        release_url=release_url,
        release_notes=body[:500] + "..." if len(body) > 500 else body,
    )
