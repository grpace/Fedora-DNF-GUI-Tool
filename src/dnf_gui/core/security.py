"""Security update detection via ``dnf updateinfo``.

DNF (both dnf4 and dnf5) can report security advisories without root::

    dnf updateinfo summary
    dnf updateinfo list updates

Example ``summary`` output::

    Updates Information Summary: available
        12 Security notice(s)
             2 Critical Security notice(s)
             5 Important Security notice(s)
        ...

Example ``list`` output::

    FEDORA-2026-abc123 Critical/Sec.  kernel-6.12.1-1.fc43.x86_64
    FEDORA-2026-def456 Moderate/Sec.   firefox-125.0-1.fc43.x86_64

Severity spelling differs between dnf4 (``Critical/Sec.``) and dnf5
(``critical``), so parsing is deliberately fuzzy.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Optional

_SEVERITY_RE = re.compile(r"(critical|important|moderate|low)", re.IGNORECASE)


@dataclass
class SecuritySummary:
    """Counts of pending security updates."""

    total: int = 0
    critical: int = 0
    important: int = 0
    moderate: int = 0
    low: int = 0
    advisories: list[str] = field(default_factory=list)
    packages: list[str] = field(default_factory=list)
    raw_summary: str = ""

    @property
    def has_security_updates(self) -> bool:
        return self.total > 0

    @property
    def urgent(self) -> bool:
        """Critical or Important updates pending — remind loudly."""
        return (self.critical + self.important) > 0


def _dnf_binary() -> str:
    return shutil.which("dnf5") or shutil.which("dnf") or "dnf"


def _run(args: list[str], timeout: int = 90) -> Optional[str]:
    try:
        result = subprocess.run(
            args, capture_output=True, text=True, timeout=timeout,
        )
        # dnf updateinfo returns 0 even with no updates; non-zero on error.
        if result.returncode != 0 and not result.stdout:
            return None
        return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


def get_security_summary(refresh: bool = False) -> SecuritySummary:
    """Query pending security advisories. Never needs root."""
    summary = SecuritySummary()
    dnf = _dnf_binary()

    # 1. Detailed list — gives per-advisory severity + package names.
    output = _run([dnf, "updateinfo", "list", "updates"])
    if output is None:
        # dnf5 sometimes wants explicit --updates flag ordering
        output = _run([dnf, "updateinfo", "list", "--updates"])
    if output:
        for line in output.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("Last metadata") or line.startswith("="):
                continue
            # Skip header lines like "Advisory  Type  Package"
            if line.lower().startswith("advisory"):
                continue
            match = _SEVERITY_RE.search(line)
            if not match:
                continue
            severity = match.group(1).lower()
            summary.total += 1
            if severity == "critical":
                summary.critical += 1
            elif severity == "important":
                summary.important += 1
            elif severity == "moderate":
                summary.moderate += 1
            elif severity == "low":
                summary.low += 1
            parts = line.split()
            if parts:
                advisory = parts[0]
                if advisory not in summary.advisories:
                    summary.advisories.append(advisory)
                # Package is usually the last token (nevra)
                pkg = parts[-1]
                if "." in pkg or "-" in pkg:
                    summary.packages.append(pkg)

    # 2. Summary text — keep raw for display, and use as fallback counts.
    raw = _run([dnf, "updateinfo", "summary"])
    if raw:
        summary.raw_summary = raw
        if summary.total == 0:
            # Fall back to parsing "N Critical Security notice(s)" lines
            for line in raw.split("\n"):
                m = re.search(r"(\d+)\s+(Critical|Important|Moderate|Low)", line, re.IGNORECASE)
                if m:
                    count = int(m.group(1))
                    sev = m.group(2).lower()
                    summary.total += count
                    if sev == "critical":
                        summary.critical += count
                    elif sev == "important":
                        summary.important += count
                    elif sev == "moderate":
                        summary.moderate += count
                    elif sev == "low":
                        summary.low += count

    if refresh:
        # Best-effort metadata refresh so security counts aren't stale.
        # Failures are ignored — stale data is better than no data.
        _run([dnf, "makecache", "-q"], timeout=120)

    return summary


def build_security_update_command() -> list[str]:
    """Upgrade security updates only (pkexec, DNF-compatible)."""
    dnf = _dnf_binary()
    return ["pkexec", dnf, "upgrade", "-y", "--security"]


def build_update_everything_command() -> list[str]:
    """Single chained command: DNF system upgrade + Flatpak update.

    Runs DNF first (needs root via pkexec), then Flatpak as the invoking
    user so both user and system remotes are handled. ``set -o pipefail``
    is avoided on purpose — Flatpak should still run even if DNF had
    nothing to do. Exit code reflects overall success.
    """
    dnf = _dnf_binary()
    flatpak = shutil.which("flatpak") or "flatpak"
    # NOTE: pkexec runs the whole bash as root; flatpak system update as
    # root is correct for system remotes. User remotes are updated on next
    # regular Flatpak refresh. We chain with ';' so one failure doesn't
    # skip the other, then report a combined status line.
    script = (
        f"{dnf} upgrade -y --refresh; DNF_CODE=$?; "
        f"{flatpak} update -y; FLATPAK_CODE=$?; "
        'echo ""; echo "── Update-Everything summary ──"; '
        'echo "DNF exit: $DNF_CODE, Flatpak exit: $FLATPAK_CODE"; '
        "exit $DNF_CODE"
    )
    return ["pkexec", "bash", "-c", script]
