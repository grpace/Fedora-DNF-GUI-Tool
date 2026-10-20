"""Package data model for representing DNF packages."""

from dataclasses import dataclass, field
from enum import Enum, auto


class PackageStatus(Enum):
    """Status of a package in the system."""
    INSTALLED = auto()
    AVAILABLE = auto()
    UPDATE_AVAILABLE = auto()
    INSTALLING = auto()
    REMOVING = auto()
    UPDATING = auto()


@dataclass
class Package:
    """Represents a DNF package with metadata."""
    name: str
    version: str
    release: str = ""
    arch: str = ""
    repo: str = ""
    summary: str = ""
    description: str = ""
    size: str = ""
    installed_size: str = ""
    url: str = ""
    license: str = ""
    status: PackageStatus = PackageStatus.AVAILABLE
    installed_version: str = ""  # for updates: the EVR being replaced

    @property
    def full_version(self) -> str:
        """Return version-release string."""
        if self.release:
            return f"{self.version}-{self.release}"
        return self.version

    @classmethod
    def from_dnf_line(cls, line: str, status: PackageStatus = PackageStatus.INSTALLED) -> "Package":
        """Parse a package from a DNF list output line.
        
        Expected format: name.arch  version-release  repo
        """
        parts = line.split()
        if len(parts) < 2:
            return None

        name_arch = parts[0]
        version_release = parts[1] if len(parts) > 1 else ""
        repo = parts[2] if len(parts) > 2 else ""

        # Split name.arch
        if "." in name_arch:
            last_dot = name_arch.rfind(".")
            name = name_arch[:last_dot]
            arch = name_arch[last_dot + 1:]
        else:
            name = name_arch
            arch = ""

        # Split version-release
        if "-" in version_release:
            last_dash = version_release.rfind("-")
            version = version_release[:last_dash]
            release = version_release[last_dash + 1:]
        else:
            version = version_release
            release = ""

        return cls(
            name=name,
            version=version,
            release=release,
            arch=arch,
            repo=repo,
            status=status,
        )


@dataclass
class UpdateInfo:
    """Summary of available system updates."""
    total_updates: int = 0
    packages: list = field(default_factory=list)
    last_checked: str = ""


@dataclass
class UpgradePreview:
    """What an upgrade would download — for confirmation dialogs.

    Built from ``dnf repoquery --upgrades`` (no root needed).
    ``total_bytes`` is the download size; 0 with count > 0 means sizes
    were unavailable (older repo metadata), not that it's free.
    """
    count: int = 0
    total_bytes: int = 0
    sizes_known: bool = False
    entries: list = field(default_factory=list)  # [(name, bytes | None)]

    @property
    def has_preview(self) -> bool:
        return self.count > 0

    def excluding(self, patterns) -> "UpgradePreview":
        """Preview with packages matching any held-back glob removed."""
        from dnf_gui.core.dnf_backend import is_held_back
        kept = UpgradePreview()
        for name, size in self.entries:
            if is_held_back(name, patterns):
                continue
            kept.entries.append((name, size))
            kept.count += 1
            if size is not None:
                kept.total_bytes += size
                kept.sizes_known = True
        return kept
