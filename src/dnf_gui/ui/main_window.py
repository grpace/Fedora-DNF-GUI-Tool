"""Main application window — orchestrates all pages and DNF operations."""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QStackedWidget,
    QMessageBox, QApplication
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut

from src.dnf_gui.core.dnf_backend import DNFBackend
from src.dnf_gui.core.worker import (
    PackageListWorker, UpdateCheckWorker, SearchWorker,
    PackageInfoWorker, CommandWorker,
)
from src.dnf_gui.ui.sidebar import Sidebar
from src.dnf_gui.ui.pages.updates_page import UpdatesPage
from src.dnf_gui.ui.pages.installed_page import InstalledPage
from src.dnf_gui.ui.pages.search_page import SearchPage
from src.dnf_gui.ui.pages.terminal_page import TerminalPage
from src.dnf_gui.ui.widgets.progress_bar import AnimatedProgressBar
from src.dnf_gui.ui.widgets.status_bar import AppStatusBar


class MainWindow(QMainWindow):
    """Main application window with sidebar navigation and stacked pages."""

    def __init__(self):
        super().__init__()
        self._backend = DNFBackend()
        self._current_worker = None
        self._command_worker = None

        self._setup_window()
        self._setup_ui()
        self._connect_signals()
        self._setup_shortcuts()

    def _setup_window(self):
        """Configure the main window properties."""
        self.setWindowTitle("DNF Package Manager — Greg.Tech")
        self.setMinimumSize(1000, 650)
        self.resize(1200, 750)

    def _setup_ui(self):
        """Build the main UI layout."""
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── Sidebar ──
        self._sidebar = Sidebar()
        main_layout.addWidget(self._sidebar)

        # ── Content Area ──
        content_wrapper = QWidget()
        content_wrapper.setObjectName("content_area")
        content_layout = QHBoxLayout(content_wrapper)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Progress bar at top
        self._progress_bar = AnimatedProgressBar()
        self._progress_bar.hide()

        # Stacked widget for pages
        self._stack = QStackedWidget()

        self._updates_page = UpdatesPage()
        self._installed_page = InstalledPage()
        self._search_page = SearchPage()
        self._terminal_page = TerminalPage()

        self._stack.addWidget(self._updates_page)    # 0
        self._stack.addWidget(self._installed_page)   # 1
        self._stack.addWidget(self._search_page)      # 2
        self._stack.addWidget(self._terminal_page)    # 3

        from PyQt6.QtWidgets import QVBoxLayout
        inner_layout = QVBoxLayout()
        inner_layout.setContentsMargins(0, 0, 0, 0)
        inner_layout.setSpacing(0)
        inner_layout.addWidget(self._progress_bar)
        inner_layout.addWidget(self._stack, 1)

        content_layout.addLayout(inner_layout)
        main_layout.addWidget(content_wrapper, 1)

        # ── Status Bar ──
        self._status_bar = AppStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.set_permanent("DNF Package Manager v1.0.0")

    def _connect_signals(self):
        """Connect all page signals to handlers."""
        # Sidebar
        self._sidebar.page_changed.connect(self._on_page_changed)

        # Updates page
        self._updates_page.check_updates_clicked.connect(self._check_updates)
        self._updates_page.upgrade_all_clicked.connect(self._upgrade_all)
        self._updates_page.upgrade_package_clicked.connect(self._install_package)
        self._updates_page.autoremove_clicked.connect(self._autoremove)

        # Installed page
        self._installed_page.remove_clicked.connect(self._remove_package)
        self._installed_page.refresh_clicked.connect(self._load_installed)

        # Search page
        self._search_page.search_requested.connect(self._search_packages)
        self._search_page.install_clicked.connect(self._install_package)

    def _setup_shortcuts(self):
        """Set up keyboard shortcuts."""
        # Ctrl+R = Refresh
        QShortcut(QKeySequence("Ctrl+R"), self, self._refresh_current)
        # Ctrl+F = Focus search
        QShortcut(QKeySequence("Ctrl+F"), self, self._focus_search)
        # Ctrl+1..4 = Switch pages
        for i in range(4):
            QShortcut(
                QKeySequence(f"Ctrl+{i+1}"), self,
                lambda idx=i: self._switch_page(idx)
            )

    # ─── Page Navigation ────────────────────────────────────────────

    def _on_page_changed(self, index: int):
        """Handle sidebar page change."""
        self._stack.setCurrentIndex(index)

        # Auto-load data on first visit
        if index == 1 and not self._installed_page._all_packages:
            self._load_installed()

    def _switch_page(self, index: int):
        """Switch to a page by index."""
        self._sidebar.set_active_page(index)
        self._stack.setCurrentIndex(index)

    def _refresh_current(self):
        """Refresh the current page."""
        index = self._stack.currentIndex()
        if index == 0:
            self._check_updates()
        elif index == 1:
            self._load_installed()

    def _focus_search(self):
        """Switch to search page and focus input."""
        self._switch_page(2)
        self._search_page.focus_search()

    # ─── DNF Operations ─────────────────────────────────────────────

    def _check_updates(self):
        """Check for available system updates."""
        self._updates_page.set_loading(True)
        self._progress_bar.start_indeterminate()
        self._status_bar.show_message("Checking for updates...")

        worker = UpdateCheckWorker(self._backend)
        worker.finished.connect(self._on_updates_checked)
        worker.error.connect(self._on_worker_error)
        worker.start()
        self._current_worker = worker

    def _on_updates_checked(self, info):
        """Handle update check results."""
        self._progress_bar.stop()
        self._updates_page.set_loading(False)
        self._updates_page.display_updates(info)
        self._sidebar.set_update_badge(info.total_updates)

        if info.total_updates > 0:
            self._status_bar.show_success(f"{info.total_updates} updates available")
        else:
            self._status_bar.show_success("System is up to date")

    def _load_installed(self):
        """Load the list of installed packages."""
        self._installed_page.set_loading(True)
        self._progress_bar.start_indeterminate()
        self._status_bar.show_message("Loading installed packages...")

        worker = PackageListWorker(self._backend)
        worker.finished.connect(self._on_installed_loaded)
        worker.error.connect(self._on_worker_error)
        worker.start()
        self._current_worker = worker

    def _on_installed_loaded(self, packages):
        """Handle installed package list."""
        self._progress_bar.stop()
        self._installed_page.set_loading(False)
        self._installed_page.display_packages(packages)
        self._status_bar.show_success(f"Loaded {len(packages)} installed packages")

    def _search_packages(self, query: str):
        """Search for packages in repositories."""
        self._search_page.set_loading(True)
        self._progress_bar.start_indeterminate()
        self._status_bar.show_message(f"Searching for '{query}'...")

        worker = SearchWorker(self._backend, query)
        worker.finished.connect(self._on_search_done)
        worker.error.connect(self._on_worker_error)
        worker.start()
        self._current_worker = worker

    def _on_search_done(self, packages):
        """Handle search results."""
        self._progress_bar.stop()
        self._search_page.set_loading(False)
        self._search_page.display_results(packages)
        self._status_bar.show_success(f"Found {len(packages)} packages")

    # ─── Privileged Operations ──────────────────────────────────────

    def _upgrade_all(self):
        """Upgrade all packages."""
        reply = QMessageBox.question(
            self,
            "Confirm Upgrade",
            "This will upgrade all packages on your system.\n\n"
            "You will be prompted for your password.\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            cmd = self._backend.build_upgrade_command()
            self._run_command(cmd, "System Upgrade")

    def _install_package(self, name: str):
        """Install or upgrade a specific package."""
        reply = QMessageBox.question(
            self,
            "Confirm Install",
            f"Install/upgrade package: {name}?\n\n"
            "You will be prompted for your password.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply == QMessageBox.StandardButton.Yes:
            cmd = self._backend.build_install_command(name)
            self._run_command(cmd, f"Installing {name}")

    def _remove_package(self, name: str):
        """Remove a package."""
        reply = QMessageBox.question(
            self,
            "Confirm Removal",
            f"Remove package: {name}?\n\n"
            "This will also remove any packages that depend on it.\n"
            "You will be prompted for your password.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            cmd = self._backend.build_remove_command(name)
            self._run_command(cmd, f"Removing {name}")

    def _autoremove(self):
        """Run autoremove to clean up unneeded dependencies."""
        reply = QMessageBox.question(
            self,
            "Confirm Cleanup",
            "This will remove packages that were installed as dependencies\n"
            "but are no longer needed by any installed package.\n\n"
            "You will be prompted for your password.\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            cmd = self._backend.build_autoremove_command()
            self._run_command(cmd, "Autoremove")

    def _run_command(self, cmd: list[str], operation: str):
        """Run a privileged command and stream output to terminal."""
        # Switch to terminal page
        self._switch_page(3)
        self._terminal_page.set_running(True, operation)
        self._progress_bar.start_indeterminate()
        self._status_bar.show_message(f"Running: {operation}...")

        self._terminal_page.append_line(f"\n{'─' * 60}")
        self._terminal_page.append_line(f"  {operation}")
        self._terminal_page.append_line(f"{'─' * 60}\n")

        worker = CommandWorker(cmd)
        worker.output_line.connect(self._terminal_page.append_line)
        worker.finished.connect(lambda code: self._on_command_done(code, operation))
        worker.error.connect(self._on_command_error)
        worker.start()
        self._command_worker = worker

    def _on_command_done(self, exit_code: int, operation: str):
        """Handle command completion."""
        self._progress_bar.stop()

        if exit_code == 0:
            self._terminal_page.set_success()
            self._status_bar.show_success(f"{operation} completed successfully")
        else:
            self._terminal_page.set_error()
            self._status_bar.show_error(f"{operation} failed (exit code {exit_code})")

        # Refresh data after operations
        self._installed_page._all_packages = []  # Force reload on next visit

    def _on_command_error(self, error: str):
        """Handle command execution error."""
        self._progress_bar.stop()
        self._terminal_page.set_error()
        self._terminal_page.append_line(f"\n❌ Error: {error}")
        self._status_bar.show_error(error)

    def _on_worker_error(self, error: str):
        """Handle background worker error."""
        self._progress_bar.stop()
        self._status_bar.show_error(error)
        QMessageBox.warning(
            self,
            "Operation Failed",
            f"An error occurred:\n\n{error}",
        )
