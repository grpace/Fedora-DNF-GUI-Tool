"""DNF backend — handles all interaction with the DNF package manager via subprocess."""

import subprocess
import shutil
from typing import Optional

from dnf_gui.core.package import Package, PackageStatus, UpdateInfo


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
        info.last_checked = datetime.now().strftime("%Y-%m-%d %I:%M %p")
        
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

    def list_repos(self, show_all: bool = False) -> list[dict]:
        """List repositories. If show_all, includes disabled repos."""
        flag = "--all" if show_all else "--enabled"
        result = self._run([self._dnf_path, "repolist", flag, "-q"])
        if result is None:
            return []
        
        repos = []
        for line in result.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split(None, 1)
            if len(parts) >= 2:
                repo_id = parts[0]
                repo_name = parts[1] if len(parts) > 1 else repo_id
                repos.append({
                    "id": repo_id,
                    "name": repo_name,
                    "enabled": not show_all or not repo_id.startswith("!"),
                })
        return repos

    def build_enable_repo_command(self, repo_id: str) -> list[str]:
        """Build command to enable a repository."""
        return ["pkexec", self._dnf_path, "config-manager", "setopt", f"{repo_id}.enabled=1"]

    def build_disable_repo_command(self, repo_id: str) -> list[str]:
        """Build command to disable a repository."""
        return ["pkexec", self._dnf_path, "config-manager", "setopt", f"{repo_id}.enabled=0"]

    def build_add_copr_command(self, copr_repo: str) -> list[str]:
        """Build command to enable a COPR repository."""
        return ["pkexec", self._dnf_path, "copr", "enable", "-y", copr_repo]

    def build_remove_copr_command(self, copr_repo: str) -> list[str]:
        """Build command to remove a COPR repository."""
        return ["pkexec", self._dnf_path, "copr", "remove", "-y", copr_repo]

    # ─── History Operations ─────────────────────────────────────────

    def history(self, limit: int = 30) -> list[dict]:
        """Get DNF transaction history."""
        result = self._run([self._dnf_path, "history", "list", f"--reverse"])
        if result is None:
            return []

        def _format_date(date_str: str) -> str:
            from datetime import datetime
            try:
                for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
                    try:
                        dt = datetime.strptime(date_str, fmt)
                        return dt.strftime("%Y-%m-%d %I:%M %p")
                    except ValueError:
                        pass
                return date_str
            except Exception:
                return date_str

        transactions = []
        for line in result.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("ID") or line.startswith("=") or line.startswith("-"):
                continue
            # History format varies between dnf4/dnf5 but generally:
            # ID | Command line | Date and time | Action(s) | Altered
            parts = line.split("|") if "|" in line else line.split(None, 4)
            if len(parts) >= 3:
                txn = {
                    "id": parts[0].strip(),
                    "command": parts[1].strip() if len(parts) > 1 else "",
                    "date": _format_date(parts[2].strip()) if len(parts) > 2 else "",
                    "action": parts[3].strip() if len(parts) > 3 else "",
                    "altered": parts[4].strip() if len(parts) > 4 else "",
                }
                transactions.append(txn)

        return transactions[-limit:]

    def history_info(self, transaction_id: str) -> str:
        """Get detailed info about a specific transaction."""
        result = self._run([self._dnf_path, "history", "info", transaction_id])
        return result or "No information available"

    def build_history_undo_command(self, transaction_id: str) -> list[str]:
        """Build command to undo a transaction."""
        return ["pkexec", self._dnf_path, "history", "undo", "-y", transaction_id]

    # ─── Group Operations ───────────────────────────────────────────

    def list_groups(self) -> list[dict]:
        """List available package groups."""
        result = self._run([self._dnf_path, "group", "list", "-q"])
        if result is None:
            return []

        groups = []
        current_section = ""
        for line in result.strip().split("\n"):
            if not line.strip():
                continue
            if line.strip().endswith(":") or line.strip().endswith("Groups:"):
                current_section = line.strip().rstrip(":")
                continue
            name = line.strip()
            if name:
                groups.append({
                    "name": name,
                    "section": current_section,
                    "installed": "Installed" in current_section,
                })
        return groups

    def build_group_install_command(self, group_name: str) -> list[str]:
        """Build command to install a package group."""
        return ["pkexec", self._dnf_path, "group", "install", "-y", group_name]

    def build_group_remove_command(self, group_name: str) -> list[str]:
        """Build command to remove a package group."""
        return ["pkexec", self._dnf_path, "group", "remove", "-y", group_name]

    # ─── Cache & Maintenance ────────────────────────────────────────

    def build_clean_cache_command(self) -> list[str]:
        """Build command to clean DNF cache."""
        return ["pkexec", self._dnf_path, "clean", "all"]

    def build_makecache_command(self) -> list[str]:
        """Build command to rebuild DNF metadata cache."""
        return ["pkexec", self._dnf_path, "makecache"]

    def build_distro_sync_command(self) -> list[str]:
        """Build command for distribution sync."""
        return ["pkexec", self._dnf_path, "distro-sync", "-y"]

    # ─── Quick Toolkit Commands ─────────────────────────────────────

    def _get_fedora_release(self) -> str:
        try:
            return subprocess.check_output(["rpm", "-E", "%fedora"], text=True).strip()
        except Exception:
            return "40"

    def build_install_rpmfusion_free_command(self) -> list[str]:
        """Build command to install RPM Fusion Free repository."""
        return [
            "pkexec", self._dnf_path, "install", "-y",
            f"https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-{self._get_fedora_release()}.noarch.rpm",
        ]

    def build_install_rpmfusion_nonfree_command(self) -> list[str]:
        """Build command to install RPM Fusion Non-Free repository."""
        return [
            "pkexec", self._dnf_path, "install", "-y",
            f"https://mirrors.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-{self._get_fedora_release()}.noarch.rpm",
        ]

    def build_install_multimedia_codecs_command(self) -> list[str]:
        """Build command to install multimedia codecs (requires RPM Fusion)."""
        return [
            "pkexec", self._dnf_path, "install", "-y",
            "gstreamer1-plugins-bad-free", "gstreamer1-plugins-bad-free-extras",
            "gstreamer1-plugins-good", "gstreamer1-plugins-good-extras",
            "gstreamer1-plugins-ugly", "gstreamer1-plugin-openh264",
            "mozilla-openh264",
        ]

    def build_install_devtools_command(self) -> list[str]:
        """Build command to install development tools group."""
        return ["pkexec", self._dnf_path, "group", "install", "-y", "Development Tools"]

    def build_firmware_update_check_command(self) -> list[str]:
        """Build command to check for firmware updates."""
        return ["bash", "-c", "fwupdmgr get-updates; if [ $? -eq 2 ]; then exit 0; else exit $?; fi"]

    def build_firmware_update_apply_command(self) -> list[str]:
        """Build command to apply firmware updates."""
        return ["pkexec", "fwupdmgr", "update", "-y"]

    def build_install_vscode_command(self) -> list[str]:
        """Build command to install VS Code via Microsoft repo."""
        # This returns a shell script approach
        return [
            "pkexec", "bash", "-c",
            'rpm --import https://packages.microsoft.com/keys/microsoft.asc && '
            'echo -e "[code]\\nname=Visual Studio Code\\nbaseurl=https://packages.microsoft.com/yumrepos/vscode\\nenabled=1\\ngpgcheck=1\\ngpgkey=https://packages.microsoft.com/keys/microsoft.asc" > /etc/yum.repos.d/vscode.repo && '
            f'{self._dnf_path} install -y code'
        ]

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
