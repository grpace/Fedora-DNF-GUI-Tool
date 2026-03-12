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
    update_version: str = ""

    @property
    def full_version(self) -> str:
        """Return version-release string."""
        if self.release:
            return f"{self.version}-{self.release}"
        return self.version

    @property
    def nevra(self) -> str:
        """Return name-epoch:version-release.arch identifier."""
        parts = [self.name]
        if self.version:
            parts.append(f"-{self.full_version}")
        if self.arch:
            parts.append(f".{self.arch}")
        return "".join(parts)

    @property
    def display_name(self) -> str:
        """Return a clean display name for the package."""
        return self.name.replace("-", " ").title()

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
    security_updates: int = 0
    bug_fixes: int = 0
    enhancements: int = 0
    packages: list = field(default_factory=list)
    last_checked: str = ""
