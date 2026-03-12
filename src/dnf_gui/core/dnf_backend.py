"""DNF backend — handles all interaction with the DNF package manager via subprocess."""

import subprocess
import shutil
from typing import Optional

from src.dnf_gui.core.package import Package, PackageStatus, UpdateInfo


class DNFBackend:
    """Interface to DNF package manager via CLI commands.
    
    All privileged operations (install, remove, upgrade) use pkexec
    for polkit-based authentication, which is standard on Fedora KDE.
    """

    def __init__(self):
        self._dnf_path = self._find_dnf()

    def _find_dnf(self) -> str:
        """Locate the dnf binary. Prefers dnf5 on Fedora 41+."""
        dnf5 = shutil.which("dnf5")
        if dnf5:
            return dnf5
        dnf = shutil.which("dnf")
        if dnf:
            return dnf
        return "dnf"

    # ─── Read-Only Operations (no root needed) ──────────────────────

    def list_installed(self) -> list[Package]:
        """List all installed packages."""
        result = self._run([self._dnf_path, "list", "--installed", "-q"])
        if result is None:
            return []
        return self._parse_package_list(result, PackageStatus.INSTALLED)

    def check_updates(self) -> UpdateInfo:
        """Check for available updates."""
        result = self._run(
            [self._dnf_path, "check-upgrade", "-q", "--refresh"],
            allow_nonzero=True,
        )
        
        info = UpdateInfo()
        if result is None:
            return info

        packages = self._parse_package_list(result, PackageStatus.UPDATE_AVAILABLE)
        info.packages = packages
        info.total_updates = len(packages)
        
        from datetime import datetime
        info.last_checked = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        return info

    def search(self, query: str) -> list[Package]:
        """Search for packages matching a query."""
        if not query or len(query) < 2:
            return []
        result = self._run([self._dnf_path, "search", "-q", query])
        if result is None:
            return []
        return self._parse_search_results(result)

    def package_info(self, package_name: str) -> Optional[Package]:
        """Get detailed info about a package."""
        result = self._run([self._dnf_path, "info", "-q", package_name])
        if result is None:
            return None
        return self._parse_package_info(result)

    # ─── Privileged Operations (root via pkexec) ────────────────────

    def build_upgrade_command(self, refresh: bool = True) -> list[str]:
        """Build the command for a full system upgrade."""
        cmd = ["pkexec", self._dnf_path, "upgrade", "-y"]
        if refresh:
            cmd.append("--refresh")
        return cmd

    def build_install_command(self, package_name: str) -> list[str]:
        """Build the command to install a package."""
        return ["pkexec", self._dnf_path, "install", "-y", package_name]

    def build_remove_command(self, package_name: str) -> list[str]:
        """Build the command to remove a package."""
        return ["pkexec", self._dnf_path, "remove", "-y", package_name]

    def build_autoremove_command(self) -> list[str]:
        """Build the command to autoremove unneeded dependencies."""
        return ["pkexec", self._dnf_path, "autoremove", "-y"]

    # ─── Repo Operations ────────────────────────────────────────────

    def list_repos(self) -> list[dict]:
        """List enabled repositories."""
        result = self._run([self._dnf_path, "repolist", "--enabled", "-q"])
        if result is None:
            return []
        
        repos = []
        for line in result.strip().split("\n"):
            parts = line.split(None, 1)
            if len(parts) >= 2:
                repos.append({
                    "id": parts[0],
                    "name": parts[1],
                })
        return repos

    # ─── Private Helpers ────────────────────────────────────────────

    def _run(self, cmd: list[str], allow_nonzero: bool = False) -> Optional[str]:
        """Run a command and return stdout, or None on failure."""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0 and not allow_nonzero:
                return None
            return result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return None

    def _parse_package_list(self, output: str, status: PackageStatus) -> list[Package]:
        """Parse DNF list output into Package objects."""
        packages = []
        for line in output.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("Last metadata") or line.startswith("="):
                continue
            pkg = Package.from_dnf_line(line, status)
            if pkg:
                packages.append(pkg)
        return packages

    def _parse_search_results(self, output: str) -> list[Package]:
        """Parse DNF search output into Package objects."""
        packages = []
        lines = output.strip().split("\n")
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line or line.startswith("=") or line.startswith("Last metadata"):
                i += 1
                continue

            # Search results format: "name.arch : summary"
            if " : " in line:
                parts = line.split(" : ", 1)
                name_arch = parts[0].strip()
                summary = parts[1].strip() if len(parts) > 1 else ""

                if "." in name_arch:
                    last_dot = name_arch.rfind(".")
                    name = name_arch[:last_dot]
                    arch = name_arch[last_dot + 1:]
                else:
                    name = name_arch
                    arch = ""

                pkg = Package(
                    name=name,
                    version="",
                    arch=arch,
                    summary=summary,
                    status=PackageStatus.AVAILABLE,
                )
                packages.append(pkg)
            
            i += 1

        return packages

    def _parse_package_info(self, output: str) -> Optional[Package]:
        """Parse dnf info output into a Package object."""
        info = {}
        current_key = None
        
        for line in output.strip().split("\n"):
            if " : " in line:
                key, value = line.split(" : ", 1)
                key = key.strip().lower()
                value = value.strip()
                info[key] = value
                current_key = key
            elif current_key and line.startswith("             :"):
                # Continuation line
                info[current_key] += " " + line.split(":", 1)[1].strip()

        if not info.get("name"):
            return None

        status = PackageStatus.INSTALLED if info.get("repo", "").startswith("@") else PackageStatus.AVAILABLE

        return Package(
            name=info.get("name", ""),
            version=info.get("version", ""),
            release=info.get("release", ""),
            arch=info.get("architecture", info.get("arch", "")),
            repo=info.get("repo", info.get("repository", "")),
            summary=info.get("summary", ""),
            description=info.get("description", ""),
            size=info.get("size", info.get("download size", "")),
            installed_size=info.get("installed size", ""),
            url=info.get("url", ""),
            license=info.get("license", ""),
            status=status,
        )
