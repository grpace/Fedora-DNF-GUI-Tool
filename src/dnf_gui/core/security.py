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
    advisory_severity: dict[str, str] = field(default_factory=dict)
    advisory_packages: dict[str, set[str]] = field(default_factory=dict)
    raw_summary: str = ""
    # Set by find_blocked_security(): updates dnf would skip right now.
    blocked: BlockedUpdates | None = None

    @property
    def urgent(self) -> bool:
        """Critical or Important updates pending — remind loudly."""
        return (self.critical + self.important) > 0

    @property
    def blocked_advisories(self) -> list[str]:
        """Advisories Security Only can't install any package from yet."""
        if not self.blocked:
            return []
        names = set(self.blocked.packages)
        return [a for a in self.advisories
                if self.advisory_packages.get(a)
                and self.advisory_packages[a] <= names]

    @property
    def installable_total(self) -> int:
        return self.total - len(self.blocked_advisories)

    @property
    def installable_urgent(self) -> bool:
        """Like ``urgent``, ignoring advisories that can't install yet."""
        if not self.blocked or not self.advisory_severity:
            return self.urgent
        waiting = set(self.blocked_advisories)
        return any(sev.lower() in ("critical", "important")
                   for adv, sev in self.advisory_severity.items()
                   if adv not in waiting)


@dataclass
class BlockedUpdates:
    """Updates dnf skips because a dependency isn't ready (typically a
    third-party package such as RPM Fusion's ``libheif-freeworld`` that
    still requires the old version)."""

    packages: list[str] = field(default_factory=list)
    # installed package holding them back -> repo id it comes from ("" unknown)
    blockers: dict[str, str] = field(default_factory=dict)
    # What forcing (``--allowerasing --best``) would remove.
    removals: list[str] = field(default_factory=list)

    @property
    def source(self) -> str:
        """Friendly name of where the blockers come from."""
        repos = {r for r in self.blockers.values() if r}
        if repos and all(r.startswith("rpmfusion") for r in repos):
            return "RPM Fusion"
        if repos and all(r.startswith("copr:") for r in repos):
            return "a COPR repository"
        if len(repos) == 1:
            return f"the {next(iter(repos))} repository"
        return ""

    def explanation(self) -> str:
        """One or two sentences on why these updates can't install."""
        pkgs = _join_names(self.packages)
        if not self.blockers:
            return (f"dnf skipped {pkgs} because of a dependency conflict. "
                    "This usually resolves itself when the repositories catch up.")
        blockers = _join_names(list(self.blockers))
        source = self.source
        from_source = f" from {source}" if source else ""
        verb = "requires" if len(self.blockers) == 1 else "require"
        return (f"{pkgs} can't update yet: {blockers}{from_source} still {verb} "
                f"the current version, and {source or 'its repository'} hasn't "
                "published a matching update. This usually clears up within a few days.")


def _join_names(names: list[str]) -> str:
    names = list(dict.fromkeys(names))
    if len(names) <= 2:
        return " and ".join(names)
    return ", ".join(names[:2]) + f" and {len(names) - 2} more"


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
            summary.advisory_severity[advisory] = severities[advisory]
        # Package NEVRA is the token that ends in .<arch>
        for token in parts[1:]:
            if re.search(r"-\d.*\.(x86_64|i686|noarch|aarch64|ppc64le|s390x)$", token):
                if token not in summary.packages:
                    summary.packages.append(token)
                name_match = _NEVRA_RE.match(token)
                if name_match:
                    name = name_match.group("name")
                    summary.advisory_packages.setdefault(advisory, set()).add(name)
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


def build_forced_security_update_command() -> list[str]:
    """Security updates, removing whatever blocks them.

    ``--allowerasing`` alone isn't enough: dnf still prefers skipping the
    blocked update, so ``--best`` makes it take the new version. Not in the
    passwordless "Updates only" rule on purpose, since it removes packages.
    """
    dnf = _dnf_binary()
    return ["pkexec", dnf, "upgrade", "-y", "--security", "--allowerasing", "--best"]


# ─── Blocked (skipped) updates ─────────────────────────────────────
#
# dnf5 prints, before its transaction table:
#
#   Problem: problem with installed package
#     - installed package libheif-freeworld-1.23.6-1.fc44.x86_64 requires
#       libheif(x86-64) = 1.23.6, but none of the providers can be installed
#     - package libheif-freeworld-1.23.6-1.fc44.x86_64 from rpmfusion-free-updates requires ...
#
# and in the table:
#
#   Skipping packages with conflicts:
#    libheif           x86_64 1.23.7-1.fc44 updates          2.4 MiB
#   Skipping packages with broken dependencies:
#    libheif-freeworld x86_64 1.21.2-3.fc44 rpmfusion-free 185.7 KiB
#
# dnf4 uses the same "Skipping packages with ..." headers.

_INSTALLED_REQUIRES_RE = re.compile(r"installed package (\S+) requires")
_FROM_REPO_RE = re.compile(r"package (\S+) from (\S+) requires")
_NEVRA_ANY_RE = re.compile(r"^(?P<name>.+)-(?:\d+:)?[^-]+-[^-]+\.[a-z0-9_]+$")
_TABLE_SECTIONS = {
    "upgrading": "install", "installing": "install", "downgrading": "install",
    "reinstalling": "install", "installing dependencies": "install",
    "installing weak dependencies": "install",
    "removing": "remove", "removing dependent packages": "remove",
    "removing unused dependencies": "remove",
    "skipping packages with conflicts": "conflict",
    "skipping packages with broken dependencies": "broken",
}


def _nevra_name(nevra: str) -> str:
    m = _NEVRA_ANY_RE.match(nevra)
    return m.group("name") if m else nevra


def _table_sections(output: str) -> dict[str, list[str]]:
    """Package names per transaction-table section kind."""
    sections: dict[str, list[str]] = {}
    current = None
    for line in output.splitlines():
        stripped = line.strip()
        header = stripped.rstrip(":").lower()
        if stripped.startswith("("):
            continue  # dnf4: "(add '--best --allowerasing' to ...):" note
        if stripped.endswith(":") and not line.startswith(" "):
            current = _TABLE_SECTIONS.get(header)
            continue
        if current is None or not stripped:
            if not stripped:
                current = None
            continue
        if stripped.startswith(("replacing ", "(")) or not line.startswith(" "):
            continue
        name = stripped.split()[0]
        names = sections.setdefault(current, [])
        if name not in names:
            names.append(name)
    return sections


def parse_blocked_updates(output: str) -> BlockedUpdates | None:
    """Read which updates dnf skipped, and why, from upgrade output."""
    sections = _table_sections(output)
    skipped = sections.get("conflict", [])
    if not skipped:
        return None
    blocked = BlockedUpdates(packages=list(skipped))
    for line in output.splitlines():
        m = _INSTALLED_REQUIRES_RE.search(line)
        if m:
            blocked.blockers.setdefault(_nevra_name(m.group(1)), "")
    for line in output.splitlines():
        m = _FROM_REPO_RE.search(line)
        if m:
            name = _nevra_name(m.group(1))
            if name in blocked.blockers and not blocked.blockers[name]:
                blocked.blockers[name] = m.group(2)
    for name in sections.get("broken", []):
        blocked.blockers.setdefault(name, "")
    for name in blocked.packages:
        blocked.blockers.pop(name, None)
    return blocked


def _dry_run(args: list[str]) -> str | None:
    """``dnf upgrade ... --assumeno`` output (no root needed on dnf5)."""
    import os
    try:
        result = subprocess.run(
            [_dnf_binary(), "upgrade", *args, "--assumeno"],
            capture_output=True, text=True, timeout=180,
            env={**os.environ, "LC_ALL": "C"},
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
    out = result.stdout + "\n" + result.stderr
    # dnf4 refuses without root; anything unparseable means "don't know".
    if "Nothing to do" not in out and "Transaction Summary" not in out:
        return None
    return out


def find_blocked_security(summary: SecuritySummary | None) -> BlockedUpdates | None:
    """Which pending security updates Security Only would skip right now.

    Runs a read-only ``dnf upgrade --security --assumeno``, and when some
    are blocked, a forced dry run to learn what forcing would remove.
    Sets and returns ``summary.blocked``. Never raises.
    """
    if not summary or not summary.package_severity:
        return None
    try:
        out = _dry_run(["--security"])
        if out is None:
            return None
        blocked = parse_blocked_updates(out) or BlockedUpdates()
        installing = set(_table_sections(out).get("install", []))
        # dnf only lists the package it tried; its siblings (other arches,
        # subpackages) are skipped silently. Anything with an advisory that
        # isn't being installed is waiting too.
        waiting = [n for n in summary.package_severity if n not in installing]
        if not waiting:
            return None
        blocked.packages = list(dict.fromkeys(
            [n for n in blocked.packages if n in summary.package_severity] + waiting))
        forced = _dry_run(["--security", "--allowerasing", "--best"])
        if forced:
            blocked.removals = _table_sections(forced).get("remove", [])
        summary.blocked = blocked
        return blocked
    except Exception:
        return None
