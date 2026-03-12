"""Background worker threads for non-blocking DNF operations."""

import subprocess
from PyQt6.QtCore import QThread, pyqtSignal

from src.dnf_gui.core.dnf_backend import DNFBackend
from src.dnf_gui.core.package import Package, UpdateInfo


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
            else:
                self.output_line.emit(f"✗ Operation finished with exit code {exit_code}")

            self.finished.emit(exit_code)

        except FileNotFoundError:
            self.error.emit("DNF binary not found. Is DNF installed?")
        except Exception as e:
            self.error.emit(str(e))

    def cancel(self):
        """Attempt to terminate the running process."""
        if self._process and self._process.poll() is None:
            self._process.terminate()
