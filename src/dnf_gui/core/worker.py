"""Background worker threads for non-blocking DNF operations."""

import os
import signal
import subprocess
import tempfile
import urllib.request
import urllib.parse
from PyQt6.QtCore import QThread, QTimer, pyqtSignal

from dnf_gui.core.dnf_backend import DNFBackend


class CallWorker(QThread):
    """Run one callable off the UI thread and emit its return value."""

    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, fn, *args, parent=None):
        super().__init__(parent)
        self._fn = fn
        self._args = args

    def run(self):
        try:
            self.finished.emit(self._fn(*self._args))
        except Exception as e:
            self.error.emit(str(e))


class PackageListWorker(QThread):
    """Worker thread to fetch the installed package list."""
    
    finished = pyqtSignal(list)   # list[Package]
    error = pyqtSignal(str)
    progress = pyqtSignal(str)    # status message

    def __init__(self, backend: DNFBackend, parent=None):
        super().__init__(parent)
        self._backend = backend

    def run(self):
        try:
            self.progress.emit("Loading installed packages...")
            packages = self._backend.list_installed()
            self.finished.emit(packages)
        except Exception as e:
            self.error.emit(str(e))


class PackageInfoWorker(QThread):
    """Worker thread to fetch detailed package info."""
    
    finished = pyqtSignal(object)  # Package or None
    error = pyqtSignal(str)

    def __init__(self, backend: DNFBackend, package_name: str, parent=None):
        super().__init__(parent)
        self._backend = backend
        self._package_name = package_name

    def run(self):
        try:
            info = self._backend.package_info(self._package_name)
            self.finished.emit(info)
        except Exception as e:
            self.error.emit(str(e))


class CommandWorker(QThread):
    """Worker thread that runs a privileged DNF command and streams output.
    
    This is used for install, remove, upgrade operations that require
    root privileges via pkexec.
    """

    output_line = pyqtSignal(str)   # individual line of output
    finished = pyqtSignal(int)      # exit code
    error = pyqtSignal(str)
    started_signal = pyqtSignal()

    def __init__(self, command: list[str], parent=None):
        super().__init__(parent)
        self._command = command
        self._process = None

    def run(self):
        try:
            self.started_signal.emit()
            self.output_line.emit(f"$ {' '.join(self._command)}")
            self.output_line.emit("")

            # stdin is /dev/null: there is no input box, so a command that
            # asks a question must fail fast instead of hanging forever.
            self._process = subprocess.Popen(
                self._command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                start_new_session=True,
            )

            with self._process.stdout:
                for line in iter(self._process.stdout.readline, ""):
                    self.output_line.emit(line.rstrip())

            self._process.wait()
            exit_code = self._process.returncode

            self.output_line.emit("")
            if exit_code == 0:
                self.output_line.emit("✓ Operation completed successfully.")
            elif exit_code in (-15, 143, -9, 137):
                self.output_line.emit("⚠ Operation was cancelled by user.")
            else:
                self.output_line.emit(f"✗ Operation finished with exit code {exit_code}")

            self.finished.emit(exit_code)

        except FileNotFoundError:
            self.error.emit("DNF binary not found. Is DNF installed?")
        except Exception as e:
            self.error.emit(str(e))

    def cancel(self):
        """Terminate the process group, escalating to SIGKILL if needed.

        Escalation runs on QTimers owned by this worker (in the GUI thread),
        so it's cancelled automatically if the worker is destroyed. A
        plain background thread would emit on a deleted object and crash.
        """
        if not self._process_running():
            return
        self._signal_group(signal.SIGTERM)
        self._after(600, self._escalate_kill)

    def _process_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def _signal_group(self, sig) -> None:
        try:
            os.killpg(os.getpgid(self._process.pid), sig)
        except Exception:
            try:
                self._process.send_signal(sig)
            except Exception:
                pass

    def _after(self, msec: int, slot) -> None:
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(slot)
        timer.timeout.connect(timer.deleteLater)
        timer.start(msec)

    def _escalate_kill(self) -> None:
        if self._process_running():
            self._signal_group(signal.SIGKILL)
            self._after(1500, self._report_if_unstoppable)

    def _report_if_unstoppable(self) -> None:
        if self._process_running():
            # Once pkexec has authenticated, dnf runs as root and a normal
            # user can't signal it. Say so instead of pretending it worked.
            self.output_line.emit(
                "⚠ Could not stop this operation: it is running as "
                "root. It will finish on its own (interrupting a DNF "
                "transaction midway is unsafe anyway).")


class SystemInfoWorker(QThread):
    """Worker thread to collect system information."""

    finished = pyqtSignal(object)  # SystemInfo
    error = pyqtSignal(str)

    def run(self):
        try:
            from dnf_gui.core.system_info import get_system_info
            info = get_system_info()
            self.finished.emit(info)
        except Exception as e:
            self.error.emit(str(e))


class FlatpakListWorker(QThread):
    """Worker thread to list installed Flatpak apps."""

    finished = pyqtSignal(list)  # list[FlatpakApp]
    error = pyqtSignal(str)

    def __init__(self, flatpak_backend, parent=None):
        super().__init__(parent)
        self._backend = flatpak_backend

    def run(self):
        try:
            apps = self._backend.list_installed()
            self.finished.emit(apps)
        except Exception as e:
            self.error.emit(str(e))


class FlatpakSearchWorker(QThread):
    """Worker thread to search Flatpak repos."""

    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, flatpak_backend, query: str, parent=None):
        super().__init__(parent)
        self._backend = flatpak_backend
        self._query = query

    def run(self):
        try:
            apps = self._backend.search(self._query)
            self.finished.emit(apps)
        except Exception as e:
            self.error.emit(str(e))


class HistoryWorker(QThread):
    """Worker thread to fetch DNF transaction history."""

    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, backend: DNFBackend, parent=None):
        super().__init__(parent)
        self._backend = backend

    def run(self):
        try:
            history = self._backend.history()
            self.finished.emit(history)
        except Exception as e:
            self.error.emit(str(e))


class RepoListWorker(QThread):
    """Worker thread to list repositories."""

    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, backend: DNFBackend, show_all: bool = True, parent=None):
        super().__init__(parent)
        self._backend = backend
        self._show_all = show_all

    def run(self):
        try:
            repos = self._backend.list_repos(self._show_all)
            self.finished.emit(repos)
        except Exception as e:
            self.error.emit(str(e))


class AppUpdateWorker(QThread):
    """Worker thread to check for app updates from GitHub releases."""

    finished = pyqtSignal(object)  # UpdateInfo or None
    error = pyqtSignal(str)

    def __init__(self, current_version: str, parent=None):
        super().__init__(parent)
        self._current_version = current_version

    def run(self):
        try:
            from dnf_gui.core.updater import check_for_update
            info = check_for_update(self._current_version)
            self.finished.emit(info)
        except Exception as e:
            self.error.emit(str(e))


class AppUpdateDownloadWorker(QThread):
    """Download a release RPM and verify it against its published SHA-256."""

    finished = pyqtSignal(str)  # path to downloaded file
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    MAX_BYTES = 100 * 1024 * 1024

    def __init__(self, url: str, sha256: str = "", parent=None):
        super().__init__(parent)
        self._url = url
        self._sha256 = (sha256 or "").lower()

    def run(self):
        try:
            import hashlib
            from dnf_gui.core.updater import _is_safe_download_url
            if not _is_safe_download_url(self._url):
                self.error.emit("Invalid or untrusted download URL")
                return
            if not self._sha256:
                self.error.emit(
                    "This release has no published SHA-256 checksum, so it "
                    "can't be verified for automatic install.")
                return
            self.progress.emit("Downloading update...")
            req = urllib.request.Request(
                self._url,
                headers={"User-Agent": "dnf-gui"},
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                # Redirects must also land on a trusted GitHub host.
                if not _is_safe_download_url(resp.geturl()):
                    self.error.emit("Download redirected to an untrusted host")
                    return
                data = resp.read(self.MAX_BYTES + 1)
            if len(data) > self.MAX_BYTES:
                self.error.emit("Download is unexpectedly large; aborting")
                return
            actual = hashlib.sha256(data).hexdigest()
            if actual != self._sha256:
                self.error.emit(
                    f"Checksum mismatch: expected {self._sha256}, got {actual}")
                return
            self.progress.emit("SHA-256 checksum verified.")
            # Fresh private directory: no predictable /tmp path to race.
            url_name = os.path.basename(urllib.parse.urlparse(self._url).path)
            if not url_name.endswith(".rpm") or url_name.startswith("."):
                url_name = "dnf-gui-update.noarch.rpm"
            path = os.path.join(tempfile.mkdtemp(prefix="dnf-gui-update-"), url_name)
            with open(path, "wb") as f:
                f.write(data)
            self.finished.emit(path)
        except Exception as e:
            self.error.emit(str(e))


class ToolkitCheckWorker(QThread):
    """Worker to check if quick tools and repositories are already installed/enabled."""

    finished = pyqtSignal(dict)  # dict mapped tool_id -> bool
    error = pyqtSignal(str)

    def run(self):
        status = {}
        try:
            # 1. Check repos
            repos = subprocess.check_output(['dnf', 'repolist', '--enabled'], text=True)
            status['rpmfusion_free'] = 'rpmfusion-free' in repos
            status['rpmfusion_nonfree'] = 'rpmfusion-nonfree' in repos
        except Exception:
            pass

        try:
            # 2. Check flatpak remotes
            remotes = subprocess.check_output(['flatpak', 'remotes'], text=True)
            status['add_flathub'] = 'flathub' in remotes
        except Exception:
            pass

        self.finished.emit(status)


class CombinedUpdateCheckWorker(QThread):
    """Check DNF + Flatpak + security in one pass for the Updates page."""

    finished = pyqtSignal(dict)  # dnf, flatpak, security, preview, security_preview, reboot, release_upgrade
    error = pyqtSignal(str)

    def __init__(self, dnf_backend, flatpak_backend, parent=None):
        super().__init__(parent)
        self._dnf_backend = dnf_backend
        self._flatpak_backend = flatpak_backend

    def run(self):
        try:
            from dnf_gui.core.security import get_security_summary
            dnf_info = self._dnf_backend.check_updates()
            flatpak_updates: list = []
            try:
                if self._flatpak_backend.available:
                    flatpak_updates = self._flatpak_backend.check_updates()
            except Exception:
                flatpak_updates = []
            try:
                security = get_security_summary()
            except Exception:
                security = None
            try:
                preview = self._dnf_backend.get_upgrade_preview()
            except Exception:
                preview = None
            try:
                security_preview = self._dnf_backend.get_upgrade_preview(
                    security_only=True)
            except Exception:
                security_preview = None
            try:
                reboot = self._dnf_backend.reboot_required()
            except Exception:
                reboot = False
            try:
                from dnf_gui.core.release_upgrade import check_release_upgrade
                release_upgrade = check_release_upgrade()
            except Exception:
                release_upgrade = None
            self.finished.emit(
                {"dnf": dnf_info, "flatpak": flatpak_updates,
                 "security": security, "preview": preview,
                 "security_preview": security_preview, "reboot": reboot,
                 "release_upgrade": release_upgrade}
            )
        except Exception as e:
            self.error.emit(str(e))


class ReminderCheckWorker(QThread):
    """Run the periodic update-reminder check off the UI thread."""

    finished = pyqtSignal(object)  # ReminderResult
    error = pyqtSignal(str)

    def run(self):
        try:
            from dnf_gui.core.app_settings import (
                AppSettings, perform_background_check,
            )
            # Own QSettings instance: never share one across threads.
            self.finished.emit(perform_background_check(AppSettings()))
        except Exception as e:
            self.error.emit(str(e))


class RebootCheckWorker(QThread):
    """Check whether a reboot is needed (fast, no root)."""

    finished = pyqtSignal(bool)
    error = pyqtSignal(str)

    def __init__(self, dnf_backend, parent=None):
        super().__init__(parent)
        self._backend = dnf_backend

    def run(self):
        try:
            self.finished.emit(bool(self._backend.reboot_required()))
        except Exception as e:
            self.error.emit(str(e))


class DiscoverStatusWorker(QThread):
    """Worker thread to inspect Discover/PackageKit state (no root)."""

    finished = pyqtSignal(object)  # DiscoverStatus
    error = pyqtSignal(str)

    def run(self):
        try:
            from dnf_gui.core.discover_manager import DiscoverManager
            status = DiscoverManager().get_status()
            self.finished.emit(status)
        except Exception as e:
            self.error.emit(str(e))

