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
_SEVERITY_RANK = {"critical": 4, "important": 3, "moderate": 2, "low": 1, "": 0}
_NEVRA_RE = re.compile(r"^(?P<name>.+)-[^-]+-[^-]+\.(x86_64|i686|noarch|aarch64|ppc64le|s390x)$")


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
    # package name -> most severe pending advisory ("critical", ..., or "")
    package_severity: dict[str, str] = field(default_factory=dict)
    raw_summary: str = ""

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


_ADVISORY_ID_RE = re.compile(r"^[A-Z][A-Za-z0-9]*(?:-[A-Za-z0-9:]+)+$")
# dnf4: "2 Critical Security notice(s)"   dnf5: "  Critical  : 3"
_SUMMARY_RES = (
    re.compile(r"(\d+)\s+(Critical|Important|Moderate|Low)\b", re.IGNORECASE),
    re.compile(r"^\s*(Critical|Important|Moderate|Low)\s*:\s*(\d+)", re.IGNORECASE),
)


def _add_severity(summary: SecuritySummary, severity: str, count: int = 1) -> None:
    severity = severity.lower()
    if severity in ("critical", "important", "moderate", "low"):
        setattr(summary, severity, getattr(summary, severity) + count)


def _parse_list(output: str, summary: SecuritySummary) -> None:
    """Parse ``updateinfo list`` rows (one row per *package*, not advisory)."""
    severities: dict[str, str] = {}
    for line in output.strip().split("\n"):
        parts = line.split()
        if len(parts) < 2 or not _ADVISORY_ID_RE.match(parts[0]):
            continue
        advisory = parts[0]
        if advisory not in severities:
            match = _SEVERITY_RE.search(line)
            severities[advisory] = match.group(1) if match else ""
            summary.advisories.append(advisory)
        # Package NEVRA is the token that ends in .<arch>
        for token in parts[1:]:
            if re.search(r"-\d.*\.(x86_64|i686|noarch|aarch64|ppc64le|s390x)$", token):
                if token not in summary.packages:
                    summary.packages.append(token)
                name_match = _NEVRA_RE.match(token)
                if name_match:
                    name = name_match.group("name")
                    severity = severities[advisory].lower()
                    current = summary.package_severity.get(name)
                    if current is None or _SEVERITY_RANK[severity] > _SEVERITY_RANK[current]:
                        summary.package_severity[name] = severity
                break
    summary.total = len(severities)
    for severity in severities.values():
        _add_severity(summary, severity)


def _parse_summary(raw: str, summary: SecuritySummary) -> None:
    """Fallback counts from ``updateinfo summary`` (security section only)."""
    in_security = False
    for line in raw.split("\n"):
        stripped = line.strip()
        if re.match(r"^(\d+\s+)?Security\b", stripped, re.IGNORECASE):
            in_security = True  # dnf5 "Security : N" section header
            continue
        if re.match(r"^(\d+\s+)?(Bugfix|Enhancement|Other)\b", stripped, re.IGNORECASE):
            in_security = False
        for pattern in _SUMMARY_RES:
            m = pattern.search(line)
            if not m:
                continue
            count, sev = ((int(m.group(1)), m.group(2)) if m.group(1).isdigit()
                          else (int(m.group(2)), m.group(1)))
            # dnf4 lines say "Security notice(s)"; dnf5 lines sit under the
            # Security header.
            if in_security or "security" in line.lower():
                summary.total += count
                _add_severity(summary, sev, count)
            break


def get_security_summary(refresh: bool = False) -> SecuritySummary:
    """Query pending security advisories. Never needs root."""
    summary = SecuritySummary()
    dnf = _dnf_binary()

    if refresh:
        # Best-effort metadata refresh so security counts aren't stale.
        # Failures are ignored — stale data is better than no data.
        _run([dnf, "makecache", "-q"], timeout=120)

    # 1. Detailed list — per-advisory severity + package names. Same flags
    #    work on dnf4 and dnf5 (dnf5 treats a bare "updates" as an advisory
    #    name and silently returns nothing).
    output = _run([dnf, "updateinfo", "list", "--updates", "--security"])
    if output:
        _parse_list(output, summary)

    # 2. Summary text — keep raw for display, and use as fallback counts.
    raw = _run([dnf, "updateinfo", "summary"])
    if raw:
        summary.raw_summary = raw
        if summary.total == 0:
            _parse_summary(raw, summary)

    return summary


def build_security_update_command() -> list[str]:
    """Upgrade security updates only (pkexec, DNF-compatible)."""
    dnf = _dnf_binary()
    return ["pkexec", dnf, "upgrade", "-y", "--security"]
