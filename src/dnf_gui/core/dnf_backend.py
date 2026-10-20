"""DNF backend — handles all interaction with the DNF package manager via subprocess."""

import fnmatch
import os
import platform
import re
import subprocess
import shutil
from typing import Iterable, Optional

# COPR format: user/project or @group/project (alphanumeric, dots, hyphens)
_COPR_PATTERN = re.compile(r"^[@]?[\w][\w.-]*/[\w.-]+$")

# Packages "Update without Major" holds back by default: the kernel and its
# out-of-tree modules, GPU drivers + firmware, and the bootloader. These are
# the updates most likely to need a reboot or break graphics if they land
# half-tested, so they wait for a deliberate full upgrade.
DEFAULT_HELD_BACK_PATTERNS = (
    "kernel*",
    "linux-firmware*",
    "*-gpu-firmware",
    "*nvidia*",
    "akmod-*",
    "mesa-*",
    "grub2-*",
    "shim-*",
)

# Package-name globs only — these are passed to dnf as argv, never a shell,
# but rejecting anything else keeps typos from becoming dnf option syntax.
_HELD_BACK_PATTERN_RE = re.compile(r"^[A-Za-z0-9*?._+\-\[\]]+$")


def parse_held_back_patterns(text: str) -> tuple[list[str], list[str]]:
    """Split comma/whitespace-separated globs into (valid, invalid)."""
    valid, invalid = [], []
    for token in re.split(r"[,\s]+", text or ""):
        if not token:
            continue
        if _HELD_BACK_PATTERN_RE.match(token) and not token.startswith("-"):
            if token not in valid:
                valid.append(token)
        else:
            invalid.append(token)
    return valid, invalid


def build_exclude_arg(patterns: Iterable[str]) -> str:
    """``--exclude=a,b`` for valid globs, or '' if none survive."""
    valid = [p for p in patterns
             if _HELD_BACK_PATTERN_RE.match(p) and not p.startswith("-")]
    return f"--exclude={','.join(valid)}" if valid else ""


def is_held_back(name: str, patterns: Iterable[str]) -> bool:
    """True if a package name matches any held-back glob."""
    return any(fnmatch.fnmatchcase(name, p) for p in patterns)

from dnf_gui.core.package import Package, PackageStatus, UpdateInfo, UpgradePreview


class DNFBackend:
    """Interface to DNF package manager via CLI commands.
    
    All privileged operations (install, remove, upgrade) use pkexec
    for polkit-based authentication, which is standard on Fedora KDE.
    """

    def __init__(self):
        self._dnf_path = self._find_dnf()

    @property
    def dnf_path(self) -> str:
        return self._dnf_path

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
        installed = self._installed_versions([p.name for p in packages])
        for pkg in packages:
            pkg.installed_version = installed.get(pkg.name, "")
        info.packages = packages
        info.total_updates = len(packages)

        from datetime import datetime
        info.last_checked = datetime.now().strftime("%Y-%m-%d")
        
        return info


    def package_info(self, package_name: str) -> Optional[Package]:
        """Get detailed info about a package."""
        result = self._run([self._dnf_path, "info", "-q", package_name])
        if result is None:
            return None
        return self._parse_package_info(result)

    def search(self, query: str, limit: int = 100) -> list[Package]:
        """Search enabled repositories by name and summary (no root).

        Keeps dnf's relevance order (exact name, then name, then summary
        matches), only this machine's architectures, and no debug packages.
        """
        query = (query or "").strip()
        if len(query) < 2 or query.startswith("-"):
            return []
        output = self._run([self._dnf_path, "search", "-q", query], allow_nonzero=True)
        if not output:
            return []
        native = {platform.machine(), "noarch"}
        installed = self._installed_versions()
        results: list[Package] = []
        seen: set[str] = set()
        for line in output.split("\n"):
            stripped = line.strip()
            if not stripped or stripped.startswith(("Matched fields", "=", "Last metadata")):
                continue
            # dnf5: "name.arch<TAB>summary"   dnf4: "name.arch : summary"
            if "\t" in stripped:
                name_arch, summary = stripped.split("\t", 1)
            elif " : " in stripped:
                name_arch, summary = stripped.split(" : ", 1)
            else:
                continue
            name, _, arch = name_arch.strip().rpartition(".")
            if (not name or arch not in native or name in seen
                    or name.endswith(("-debuginfo", "-debugsource"))):
                continue
            seen.add(name)
            results.append(Package(
                name=name, version=installed.get(name, ""), arch=arch,
                summary=summary.strip(),
                status=(PackageStatus.INSTALLED if name in installed
                        else PackageStatus.AVAILABLE),
            ))
            if len(results) >= limit:
                break
        available = self._available_versions(
            [p.name for p in results if p.status == PackageStatus.AVAILABLE], native)
        for pkg in results:
            if pkg.name in available:
                pkg.version, pkg.repo = available[pkg.name]
        return results

    def _available_versions(self, names: list[str],
                            arches: set[str]) -> dict[str, tuple[str, str]]:
        """name -> (latest available EVR, repo id) for not-installed packages."""
        if not names:
            return {}
        output = self._run(
            [self._dnf_path, "repoquery", "-q", "--available", "--latest-limit=1",
             f"--arch={','.join(sorted(arches))}",
             "--queryformat", "%{name} %{evr} %{repoid}\n", *names],
            allow_nonzero=True,
        )
        versions: dict[str, tuple[str, str]] = {}
        for line in (output or "").split("\n"):
            parts = line.split()
            if len(parts) == 3:
                versions.setdefault(parts[0], (parts[1], parts[2]))
        return versions

    def unneeded_packages(self) -> list[str]:
        """Packages ``dnf autoremove`` would remove, as "name-evr" (no root)."""
        output = self._run(
            [self._dnf_path, "repoquery", "-q", "--unneeded",
             "--queryformat", "%{name}-%{evr}\n"],
            allow_nonzero=True,
        )
        if not output:
            return []
        return sorted({line.strip() for line in output.split("\n")
                       if line.strip() and not line.startswith("Last metadata")})

    def _installed_versions(self, names: list[str] | None = None) -> dict[str, str]:
        """name -> installed EVR (newest when several, e.g. kernels)."""
        cmd = ["rpm", "-q" if names else "-qa", "--qf", "%{NAME} %{EVR}\n"]
        if names:
            cmd += sorted(set(names))
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return {}
        versions: dict[str, str] = {}
        for line in result.stdout.split("\n"):
            parts = line.split()
            # "package foo is not installed" lines have more than 2 words
            if len(parts) == 2:
                versions[parts[0]] = parts[1]  # rpm lists oldest first
        return versions

    def get_upgrade_preview(self, security_only: bool = False) -> UpgradePreview:
        """Preview an upgrade: package count + total download size.

        Uses ``repoquery --upgrades`` (read-only, no root). Never raises —
        on any failure returns an empty preview so callers can omit the
        size line instead of blocking the upgrade flow.
        """
        preview = UpgradePreview()
        cmd = [
            self._dnf_path, "repoquery", "--upgrades",
            "--queryformat", "%{name} %{evr} %{arch} %{downloadsize}",
        ]
        if security_only:
            cmd.insert(2, "--security")
        result = self._run(cmd, allow_nonzero=True)
        if not result:
            return preview
        for line in result.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("Last metadata") or line.startswith("="):
                continue
            parts = line.split()
            if len(parts) < 4:
                continue
            preview.count += 1
            try:
                size = int(parts[-1])
                preview.total_bytes += size
                preview.sizes_known = True
            except ValueError:
                # Unknown query tag echoed literally (older dnf) — count it,
                # but don't claim a size.
                size = None
            preview.entries.append((parts[0], size))
        return preview

    def reboot_required(self) -> bool:
        """True if the system should be rebooted to finish updates.

        Checks, in order: ``needs-restarting -r`` (dnf-utils-core, exit 1
        means reboot needed), the ``/run/reboot-required`` sentinel some
        stacks create, then kernel drift (running kernel is no longer the
        newest installed one). Never raises.
        """
        try:
            result = subprocess.run(
                ["needs-restarting", "-r"],
                capture_output=True, timeout=60,
            )
            if result.returncode == 1:
                return True
            if result.returncode == 0:
                return False
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass
        except Exception:
            pass

        try:
            if os.path.exists("/run/reboot-required"):
                return True
        except Exception:
            pass

        try:
            running = platform.release()
            for pkg in ("kernel-core", "kernel"):
                result = subprocess.run(
                    ["rpm", "-q", pkg, "--queryformat",
                     "%{INSTALLTIME} %{VERSION}-%{RELEASE}.%{ARCH}\n"],
                    capture_output=True, text=True, timeout=15,
                )
                if result.returncode != 0 or not result.stdout.strip():
                    continue
                installed = []
                for line in result.stdout.split("\n"):
                    parts = line.split()
                    if len(parts) == 2 and parts[0].isdigit():
                        installed.append((int(parts[0]), parts[1]))
                if not installed:
                    continue
                # Reboot needed when a newer kernel was installed after the
                # one we're running (or ours was removed entirely).
                return max(installed)[1] != running
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass
        except Exception:
            pass
        return False

    # ─── Privileged Operations (root via pkexec) ────────────────────

    def build_upgrade_command(self, refresh: bool = True) -> list[str]:
        """Build the command for a full system upgrade."""
        cmd = ["pkexec", self._dnf_path, "upgrade", "-y"]
        if refresh:
            cmd.append("--refresh")
        return cmd

    def build_upgrade_without_major_command(
            self, held_back: Iterable[str], refresh: bool = True) -> list[str]:
        """Upgrade everything except held-back core packages.

        Stays a literal ``dnf upgrade`` (no shell) so the passwordless
        "updates" sudoers rule still covers it.
        """
        cmd = self.build_upgrade_command(refresh=refresh)
        exclude = build_exclude_arg(held_back)
        if exclude:
            cmd.append(exclude)
        return cmd

    def build_upgrade_package_command(self, package_name: str) -> list[str]:
        """Upgrade one installed package (``install`` may not upgrade)."""
        return ["pkexec", self._dnf_path, "upgrade", "-y", package_name]

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
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) >= 2:
                repo_id = parts[0]
                # Skip header line (e.g. "repo id  repo name  status")
                if repo_id.lower() in ("repo", "id"):
                    continue

                last = parts[-1].lower()
                if last in ("enabled", "disabled"):
                    is_enabled = (last == "enabled")
                    after_id = line[len(repo_id):].strip()
                    if after_id.lower().endswith(last):
                        repo_name = after_id[:-len(last)].strip()
                    else:
                        repo_name = " ".join(parts[1:-1])
                else:
                    is_enabled = not repo_id.startswith("!")
                    repo_name = line[len(repo_id):].strip()

                if not repo_name:
                    repo_name = repo_id

                repos.append({
                    "id": repo_id,
                    "name": repo_name,
                    "enabled": is_enabled,
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
        cleaned = (copr_repo or "").strip()
        if not cleaned or not _COPR_PATTERN.match(cleaned):
            raise ValueError(
                "Invalid COPR format. Use user/project or @group/project "
                "(e.g. user/my-project)"
            )
        return ["pkexec", self._dnf_path, "copr", "enable", "-y", cleaned]


    def history(self, limit: int = 30) -> list[dict]:
        """Get DNF transaction history."""
        result = self._run([self._dnf_path, "history", "list", "--reverse"])
        if result is None:
            return []

        def _format_date(date_str: str) -> str:
            from datetime import datetime
            try:
                for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
                    try:
                        dt = datetime.strptime(date_str, fmt)
                        return dt.strftime("%Y-%m-%d %I:%M %p")
                    except ValueError:
                        pass
                return date_str
            except Exception:
                return date_str

        import re
        date_re = re.compile(r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}(?::\d{2})?)")

        transactions = []
        for line in result.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("ID") or line.startswith("=") or line.startswith("-"):
                continue

            if "|" in line:
                parts = line.split("|")
                if len(parts) >= 3:
                    txn = {
                        "id": parts[0].strip(),
                        "command": parts[1].strip() if len(parts) > 1 else "System / PackageKit",
                        "date": _format_date(parts[2].strip()) if len(parts) > 2 else "",
                        "action": parts[3].strip() if len(parts) > 3 else "",
                        "altered": parts[4].strip() if len(parts) > 4 else "",
                    }
                    if not txn["command"]:
                        txn["command"] = "System / PackageKit"
                    transactions.append(txn)
            else:
                m = date_re.search(line)
                if m:
                    date_str = m.group(1)
                    before_date = line[:m.start()].strip()
                    after_date = line[m.end():].strip()

                    parts_before = before_date.split(None, 1)
                    tid = parts_before[0]
                    cmd = parts_before[1].strip() if len(parts_before) > 1 else "System / PackageKit"
                    if not cmd:
                        cmd = "System / PackageKit"

                    parts_after = after_date.split()
                    altered = parts_after[-1] if parts_after else ""
                    action = " ".join(parts_after[:-1]) if len(parts_after) > 1 else ""

                    transactions.append({
                        "id": tid,
                        "command": cmd,
                        "date": _format_date(date_str),
                        "action": action,
                        "altered": altered,
                    })

        return transactions[-limit:]
    def history_info(self, transaction_id: str) -> str:
        """Get detailed info about a specific transaction."""
        tid = (transaction_id or "").strip()
        if not tid or not tid.isdigit():
            return "Invalid transaction ID"
        result = self._run([self._dnf_path, "history", "info", tid])
        return result or "No information available"

    def build_history_undo_command(self, transaction_id: str) -> list[str]:
        """Build command to undo a transaction."""
        tid = (transaction_id or "").strip()
        if not tid or not tid.isdigit():
            raise ValueError("Invalid transaction ID")
        return ["pkexec", self._dnf_path, "history", "undo", "-y", tid]

    # ─── Group Operations ───────────────────────────────────────────


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

    def build_firmware_update_check_command(self) -> list[str]:
        """Build command to check for firmware updates."""
        # fwupdmgr exits 2 for "no updates available" — treat that as success.
        return ["bash", "-c", "fwupdmgr get-updates; rc=$?; [ $rc -eq 2 ] && exit 0; exit $rc"]

    def build_firmware_update_apply_command(self) -> list[str]:
        """Build command to apply firmware updates."""
        return ["pkexec", "fwupdmgr", "update", "-y"]

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
