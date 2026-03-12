"""Background worker threads for non-blocking DNF operations."""

import os
import subprocess
import tempfile
import urllib.request
import urllib.parse
from PyQt6.QtCore import QThread, pyqtSignal

from dnf_gui.core.dnf_backend import DNFBackend
from dnf_gui.core.package import Package, UpdateInfo


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


class UpdateCheckWorker(QThread):
    """Worker thread to check for available updates."""
    
    finished = pyqtSignal(object)  # UpdateInfo
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, backend: DNFBackend, parent=None):
        super().__init__(parent)
        self._backend = backend

    def run(self):
        try:
            self.progress.emit("Checking for updates (refreshing metadata)...")
            info = self._backend.check_updates()
            self.finished.emit(info)
        except Exception as e:
            self.error.emit(str(e))


class SearchWorker(QThread):
    """Worker thread to search for packages."""
    
    finished = pyqtSignal(list)   # list[Package]
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, backend: DNFBackend, query: str, parent=None):
        super().__init__(parent)
        self._backend = backend
        self._query = query

    def run(self):
        try:
            self.progress.emit(f"Searching for '{self._query}'...")
            packages = self._backend.search(self._query)
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

            self._process = subprocess.Popen(
                self._command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            for line in iter(self._process.stdout.readline, ""):
                self.output_line.emit(line.rstrip())

            self._process.wait()
            exit_code = self._process.returncode

            self.output_line.emit("")
            if exit_code == 0:
                self.output_line.emit("✓ Operation completed successfully.")
            elif exit_code == -15 or exit_code == 143:
                self.output_line.emit("⚠ Operation was cancelled by user.")
            else:
                self.output_line.emit(f"✗ Operation finished with exit code {exit_code}")

            self.finished.emit(exit_code)

        except FileNotFoundError:
            self.error.emit("DNF binary not found. Is DNF installed?")
        except Exception as e:
            self.error.emit(str(e))

    def write_input(self, text: str):
        """Write user input to the running process standard input."""
        if self._process and self._process.stdin and self._process.poll() is None:
            try:
                self._process.stdin.write(text + "\n")
                self._process.stdin.flush()
            except Exception:
                pass

    def cancel(self):
        """Attempt to terminate the running process."""
        if self._process and self._process.poll() is None:
            self._process.terminate()


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


class GroupListWorker(QThread):
    """Worker thread to list package groups."""

    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, backend: DNFBackend, parent=None):
        super().__init__(parent)
        self._backend = backend

    def run(self):
        try:
            groups = self._backend.list_groups()
            self.finished.emit(groups)
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
    """Worker thread to download an RPM file from URL."""

    finished = pyqtSignal(str)  # path to downloaded file
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        self._url = url

    def run(self):
        try:
            from dnf_gui.core.updater import _is_safe_download_url
            if not _is_safe_download_url(self._url):
                self.error.emit("Invalid or untrusted download URL")
                return
            self.progress.emit("Downloading update...")
            req = urllib.request.Request(
                self._url,
                headers={"User-Agent": "dnf-gui"},
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()
            # Extract filename from URL or use default
            url_path = urllib.parse.urlparse(self._url).path
            filename = os.path.basename(url_path) if url_path else "dnf-gui-update.noarch.rpm"
            path = os.path.join(tempfile.gettempdir(), filename)
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

