"""Main application window — orchestrates all pages and DNF operations."""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget,
    QMessageBox, QApplication
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut, QIcon
import os

from dnf_gui.core.dnf_backend import DNFBackend
from dnf_gui.core.flatpak_backend import FlatpakBackend
from dnf_gui.core.worker import (
    PackageListWorker, UpdateCheckWorker,
    PackageInfoWorker, CommandWorker,
    SystemInfoWorker, FlatpakListWorker, FlatpakSearchWorker,
    HistoryWorker, RepoListWorker, GroupListWorker,
    ToolkitCheckWorker
)
from dnf_gui.ui.sidebar import Sidebar
from dnf_gui.ui.pages.updates_page import UpdatesPage
from dnf_gui.ui.pages.installed_page import InstalledPage
from dnf_gui.ui.pages.flatpak_page import FlatpakPage
from dnf_gui.ui.pages.system_info_page import SystemInfoPage
from dnf_gui.ui.pages.toolkit_page import ToolkitPage
from dnf_gui.ui.pages.repo_manager_page import RepoManagerPage
from dnf_gui.ui.pages.history_page import HistoryPage
from dnf_gui.ui.pages.terminal_page import TerminalPage
from dnf_gui.ui.widgets.progress_bar import AnimatedProgressBar
from dnf_gui.ui.widgets.status_bar import AppStatusBar


# Page index constants
PAGE_UPDATES = 0
PAGE_INSTALLED = 1
PAGE_FLATPAK = 2
PAGE_SYSINFO = 3
PAGE_TOOLKIT = 4
PAGE_REPOS = 5
PAGE_HISTORY = 6
PAGE_TERMINAL = 7


class MainWindow(QMainWindow):
    """Main application window with sidebar navigation and stacked pages."""

    def __init__(self):
        super().__init__()
        self._backend = DNFBackend()
        self._flatpak_backend = FlatpakBackend()
        self._current_worker = None
        self._command_worker = None

        self._setup_window()
        self._setup_ui()
        self._connect_signals()
        self._setup_shortcuts()
        
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, self._refresh_current)

    def _setup_window(self):
        """Configure the main window properties."""
        self.setWindowTitle("DNF Package Manager")
        
        # Determine the assets path relative to the module
        try:
            icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "assets", "icons", "app_icon.svg")
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
            else:
                self.setWindowIcon(QIcon.fromTheme("system-software-install"))
        except:
            pass

        self.setMinimumSize(1050, 700)
        self.resize(1280, 800)

    def _setup_ui(self):
        """Build the main UI layout."""
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

        inner_layout = QVBoxLayout(content_wrapper)
        inner_layout.setContentsMargins(0, 0, 0, 0)
        inner_layout.setSpacing(0)

        # Progress bar
        self._progress_bar = AnimatedProgressBar()
        self._progress_bar.hide()
        inner_layout.addWidget(self._progress_bar)

        # Stacked pages
        self._stack = QStackedWidget()

        self._updates_page = UpdatesPage()
        self._installed_page = InstalledPage()
        self._flatpak_page = FlatpakPage()
        self._sysinfo_page = SystemInfoPage()
        self._toolkit_page = ToolkitPage()
        self._repo_page = RepoManagerPage()
        self._history_page = HistoryPage()
        self._terminal_page = TerminalPage()

        self._stack.addWidget(self._updates_page)     # 0
        self._stack.addWidget(self._installed_page)    # 1
        self._stack.addWidget(self._flatpak_page)      # 2
        self._stack.addWidget(self._sysinfo_page)      # 3
        self._stack.addWidget(self._toolkit_page)      # 4
        self._stack.addWidget(self._repo_page)         # 5
        self._stack.addWidget(self._history_page)      # 6
        self._stack.addWidget(self._terminal_page)     # 7

        inner_layout.addWidget(self._stack, 1)
        main_layout.addWidget(content_wrapper, 1)

        # ── Status Bar ──
        self._status_bar = AppStatusBar()
        self.setStatusBar(self._status_bar)

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

        # Flatpak page
        self._flatpak_page.refresh_clicked.connect(self._load_flatpaks)
        self._flatpak_page.search_requested.connect(self._search_flatpaks)
        self._flatpak_page.install_clicked.connect(self._flatpak_install)
        self._flatpak_page.remove_clicked.connect(self._flatpak_remove)
        self._flatpak_page.update_all_clicked.connect(self._flatpak_update_all)
        self._flatpak_page.remove_unused_clicked.connect(self._flatpak_remove_unused)
        self._flatpak_page.repair_clicked.connect(self._flatpak_repair)

        # System info page
        self._sysinfo_page.refresh_clicked.connect(self._load_sysinfo)

        # Toolkit page
        self._toolkit_page.tool_clicked.connect(self._handle_tool)

        # Repo manager page
        self._repo_page.refresh_clicked.connect(self._load_repos)
        self._repo_page.enable_repo_clicked.connect(self._enable_repo)
        self._repo_page.disable_repo_clicked.connect(self._disable_repo)
        self._repo_page.add_copr_clicked.connect(self._add_copr)

        # History page
        self._history_page.refresh_clicked.connect(self._load_history)
        self._history_page.undo_clicked.connect(self._history_undo)
        self._history_page.info_requested.connect(self._history_info)

    def _setup_shortcuts(self):
        """Set up keyboard shortcuts."""
        QShortcut(QKeySequence("Ctrl+R"), self, self._refresh_current)
        # Ctrl+1..8 = Switch pages
        for i in range(8):
            QShortcut(
                QKeySequence(f"Ctrl+{i+1}"), self,
                lambda idx=i: self._switch_page(idx)
            )

    # ═══════════════════════════════════════════════════════════════
    #  Page Navigation
    # ═══════════════════════════════════════════════════════════════

    def _on_page_changed(self, index: int):
        """Handle sidebar page change, auto-load data on first visit."""
        self._stack.setCurrentIndex(index)
        # Automatically refresh content for the active tab (e.g. Check for Updates)
        self._refresh_current()

    def _switch_page(self, index: int):
        self._sidebar.set_active_page(index)
        self._on_page_changed(index)

    def _refresh_current(self):
        index = self._stack.currentIndex()
        if index == PAGE_UPDATES:
            self._check_updates()
        elif index == PAGE_INSTALLED:
            self._load_installed()
        elif index == PAGE_FLATPAK:
            self._load_flatpaks()
        elif index == PAGE_SYSINFO:
            self._load_sysinfo()
        elif index == PAGE_TOOLKIT:
            self._load_toolkit_status()
        elif index == PAGE_REPOS:
            self._load_repos()
        elif index == PAGE_HISTORY:
            self._load_history()

    # ═══════════════════════════════════════════════════════════════
    #  DNF Package Operations
    # ═══════════════════════════════════════════════════════════════

    def _check_updates(self):
        self._updates_page.set_loading(True)
        self._progress_bar.start_indeterminate()
        self._status_bar.show_message("Checking for updates...")

        worker = UpdateCheckWorker(self._backend)
        worker.finished.connect(self._on_updates_checked)
        worker.error.connect(self._on_worker_error)
        worker.start()
        self._current_worker = worker

    def _on_updates_checked(self, info):
        self._progress_bar.stop()
        self._updates_page.set_loading(False)
        self._updates_page.display_updates(info)
        self._sidebar.set_update_badge(info.total_updates)

        if info.total_updates > 0:
            self._status_bar.show_success(f"{info.total_updates} updates available")
        else:
            self._status_bar.show_success("System is up to date")

    def _load_installed(self):
        self._installed_page.set_loading(True)
        self._progress_bar.start_indeterminate()
        self._status_bar.show_message("Loading installed packages...")

        worker = PackageListWorker(self._backend)
        worker.finished.connect(self._on_installed_loaded)
        worker.error.connect(self._on_worker_error)
        worker.start()
        self._current_worker = worker

    def _on_installed_loaded(self, packages):
        self._progress_bar.stop()
        self._installed_page.set_loading(False)
        self._installed_page.display_packages(packages)
        self._status_bar.show_success(f"Loaded {len(packages)} installed packages")

    # ═══════════════════════════════════════════════════════════════
    #  Privileged Package Operations
    # ═══════════════════════════════════════════════════════════════

    def _upgrade_all(self):
        reply = QMessageBox.question(
            self, "Confirm Upgrade",
            "This will upgrade all packages on your system.\n\n"
            "You will be prompted for your password.\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._run_command(self._backend.build_upgrade_command(), "System Upgrade")

    def _install_package(self, name: str):
        reply = QMessageBox.question(
            self, "Confirm Install",
            f"Install/upgrade package: {name}?\n\nYou will be prompted for your password.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._run_command(self._backend.build_install_command(name), f"Installing {name}")

    def _remove_package(self, name: str):
        reply = QMessageBox.question(
            self, "Confirm Removal",
            f"Remove package: {name}?\n\nThis will also remove packages that depend on it.\n"
            "You will be prompted for your password.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._run_command(self._backend.build_remove_command(name), f"Removing {name}")

    def _autoremove(self):
        reply = QMessageBox.question(
            self, "Confirm Cleanup",
            "Remove unneeded dependency packages?\n\nYou will be prompted for your password.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._run_command(self._backend.build_autoremove_command(), "Autoremove")

    # ═══════════════════════════════════════════════════════════════
    #  Flatpak Operations
    # ═══════════════════════════════════════════════════════════════

    def _load_flatpaks(self):
        if not self._flatpak_backend.available:
            self._flatpak_page.set_unavailable()
            return

        self._flatpak_page.set_loading(True)
        self._progress_bar.start_indeterminate()
        self._status_bar.show_message("Loading Flatpak apps...")

        worker = FlatpakListWorker(self._flatpak_backend)
        worker.finished.connect(self._on_flatpaks_loaded)
        worker.error.connect(self._on_worker_error)
        worker.start()
        self._current_worker = worker

    def _on_flatpaks_loaded(self, apps):
        self._progress_bar.stop()
        self._flatpak_page.display_installed(apps)
        self._status_bar.show_success(f"Loaded {len(apps)} Flatpak apps")

    def _search_flatpaks(self, query: str):
        self._flatpak_page.set_search_loading(True)
        self._progress_bar.start_indeterminate()

        worker = FlatpakSearchWorker(self._flatpak_backend, query)
        worker.finished.connect(self._on_flatpak_search_done)
        worker.error.connect(self._on_worker_error)
        worker.start()
        self._current_worker = worker

    def _on_flatpak_search_done(self, apps):
        self._progress_bar.stop()
        self._flatpak_page.display_search_results(apps)
        self._status_bar.show_success(f"Found {len(apps)} Flatpak apps")

    def _flatpak_install(self, app_id: str):
        reply = QMessageBox.question(
            self, "Install Flatpak",
            f"Install Flatpak app: {app_id}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._run_command(
                self._flatpak_backend.build_install_command(app_id),
                f"Installing Flatpak: {app_id}",
            )

    def _flatpak_remove(self, app_id: str):
        reply = QMessageBox.question(
            self, "Remove Flatpak",
            f"Remove Flatpak app: {app_id}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._run_command(
                self._flatpak_backend.build_remove_command(app_id),
                f"Removing Flatpak: {app_id}",
            )

    def _flatpak_update_all(self):
        reply = QMessageBox.question(
            self, "Update Flatpaks",
            "Update all Flatpak applications?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._run_command(
                self._flatpak_backend.build_update_all_command(),
                "Updating all Flatpak apps",
            )

    def _flatpak_remove_unused(self):
        reply = QMessageBox.question(
            self, "Remove Unused",
            "Remove unused Flatpak runtimes and extensions?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._run_command(
                self._flatpak_backend.build_remove_unused_command(),
                "Removing unused Flatpak runtimes",
            )

    def _flatpak_repair(self):
        reply = QMessageBox.question(
            self, "Repair Flatpak",
            "Repair Flatpak installation?\nThis may fix broken apps.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._run_command(
                self._flatpak_backend.build_repair_command(),
                "Repairing Flatpak installation",
            )

    # ═══════════════════════════════════════════════════════════════
    #  System Info
    # ═══════════════════════════════════════════════════════════════

    def _load_sysinfo(self):
        self._sysinfo_page.set_loading(True)
        self._progress_bar.start_indeterminate()
        self._status_bar.show_message("Collecting system information...")

        worker = SystemInfoWorker()
        worker.finished.connect(self._on_sysinfo_loaded)
        worker.error.connect(self._on_worker_error)
        worker.start()
        self._current_worker = worker

    def _on_sysinfo_loaded(self, info):
        self._progress_bar.stop()
        self._sysinfo_page.display_info(info)
        self._status_bar.show_success("System information loaded")

    # ═══════════════════════════════════════════════════════════════
    #  Quick Tools Operations
    # ═══════════════════════════════════════════════════════════════

    def _load_toolkit_status(self):
        self._toolkit_worker = ToolkitCheckWorker(self)
        self._toolkit_worker.finished.connect(self._toolkit_page.update_card_statuses)
        self._toolkit_worker.start()


    def _handle_tool(self, tool_id: str):
        """Route tool card clicks to the appropriate command."""
        tool_map = {
            # Repositories
            "rpmfusion_free": (
                self._backend.build_install_rpmfusion_free_command,
                "Installing RPM Fusion (Free)",
                "Enable RPM Fusion Free repository?",
            ),
            "rpmfusion_nonfree": (
                self._backend.build_install_rpmfusion_nonfree_command,
                "Installing RPM Fusion (Non-Free)",
                "Enable RPM Fusion Non-Free repository?",
            ),
            "add_flathub": (
                lambda: ["flatpak", "remote-add", "--if-not-exists", "flathub",
                          "https://dl.flathub.org/repo/flathub.flatpakrepo"],
                "Adding Flathub repository",
                "Add the Flathub repository to Flatpak?",
            ),
            # Multimedia
            "install_codecs": (
                self._backend.build_install_multimedia_codecs_command,
                "Installing multimedia codecs",
                "Install multimedia codecs?\n(Requires RPM Fusion to be enabled first)",
            ),
            "install_vlc": (
                lambda: self._backend.build_install_command("vlc"),
                "Installing VLC",
                "Install VLC media player?",
            ),
            # Development
            "install_devtools": (
                self._backend.build_install_devtools_command,
                "Installing Development Tools",
                "Install the Development Tools group?\n(gcc, make, autoconf, etc.)",
            ),
            "install_vscode": (
                self._backend.build_install_vscode_command,
                "Installing Visual Studio Code",
                "Install VS Code?\nThis will add the Microsoft repository.",
            ),
            "install_git": (
                lambda: ["pkexec", self._backend._dnf_path, "install", "-y",
                          "git", "git-lfs", "git-extras"],
                "Installing Git",
                "Install Git, git-lfs, and git-extras?",
            ),
            "install_python_dev": (
                lambda: ["pkexec", self._backend._dnf_path, "install", "-y",
                          "python3-devel", "python3-pip", "python3-virtualenv",
                          "python3-setuptools", "python3-wheel"],
                "Installing Python development tools",
                "Install Python development packages?",
            ),
            "install_nodejs": (
                lambda: ["pkexec", self._backend._dnf_path, "install", "-y",
                          "nodejs", "npm"],
                "Installing Node.js",
                "Install Node.js and npm?",
            ),
            # System
            "firmware_check": (
                self._backend.build_firmware_update_check_command,
                "Checking firmware updates",
                "Check for available firmware updates?",
            ),
            "firmware_update": (
                self._backend.build_firmware_update_apply_command,
                "Applying firmware updates",
                "Apply firmware updates?\n(May require a reboot)",
            ),
            "clean_cache": (
                self._backend.build_clean_cache_command,
                "Cleaning DNF cache",
                "Clean all DNF cached data?",
            ),
            "rebuild_cache": (
                self._backend.build_makecache_command,
                "Rebuilding metadata cache",
                "Rebuild DNF metadata cache?",
            ),
            "distro_sync": (
                self._backend.build_distro_sync_command,
                "Distribution Sync",
                "Run distribution sync?\nThis synchronizes installed packages to latest versions.",
            ),
            # Popular apps
            "install_firefox": (
                lambda: self._backend.build_install_command("firefox"),
                "Installing Firefox",
                "Install Firefox browser?",
            ),
            "install_thunderbird": (
                lambda: self._backend.build_install_command("thunderbird"),
                "Installing Thunderbird",
                "Install Thunderbird email client?",
            ),
            "install_gimp": (
                lambda: self._backend.build_install_command("gimp"),
                "Installing GIMP",
                "Install GIMP image editor?",
            ),
            "install_libreoffice": (
                lambda: ["pkexec", self._backend._dnf_path, "install", "-y",
                          "libreoffice"],
                "Installing LibreOffice",
                "Install the LibreOffice suite?",
            ),
            "install_kdenlive": (
                lambda: self._backend.build_install_command("kdenlive"),
                "Installing Kdenlive",
                "Install Kdenlive video editor?",
            ),
            "install_obs": (
                lambda: self._backend.build_install_command("obs-studio"),
                "Installing OBS Studio",
                "Install OBS Studio?",
            ),
        }

        if tool_id not in tool_map:
            self._status_bar.show_error(f"Unknown tool: {tool_id}")
            return

        cmd_builder, operation, confirm_msg = tool_map[tool_id]

        reply = QMessageBox.question(
            self, "Confirm Action", confirm_msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply == QMessageBox.StandardButton.Yes:
            cmd = cmd_builder() if callable(cmd_builder) else cmd_builder
            self._run_command(cmd, operation)

    # ═══════════════════════════════════════════════════════════════
    #  Repository Manager
    # ═══════════════════════════════════════════════════════════════

    def _load_repos(self):
        self._repo_page.set_loading(True)
        self._progress_bar.start_indeterminate()
        self._status_bar.show_message("Loading repositories...")

        worker = RepoListWorker(self._backend, show_all=True)
        worker.finished.connect(self._on_repos_loaded)
        worker.error.connect(self._on_worker_error)
        worker.start()
        self._current_worker = worker

    def _on_repos_loaded(self, repos):
        self._progress_bar.stop()
        self._repo_page.display_repos(repos)
        self._status_bar.show_success(f"Loaded {len(repos)} repositories")

    def _enable_repo(self, repo_id: str):
        reply = QMessageBox.question(
            self, "Enable Repository",
            f"Enable repository: {repo_id}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._run_command(
                self._backend.build_enable_repo_command(repo_id),
                f"Enabling repo: {repo_id}",
            )

    def _disable_repo(self, repo_id: str):
        reply = QMessageBox.question(
            self, "Disable Repository",
            f"Disable repository: {repo_id}?\n\n"
            "You won't receive updates from this repo until re-enabled.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._run_command(
                self._backend.build_disable_repo_command(repo_id),
                f"Disabling repo: {repo_id}",
            )

    def _add_copr(self, copr_name: str):
        reply = QMessageBox.question(
            self, "Add COPR Repository",
            f"Enable COPR repository: {copr_name}?\n\n"
            "COPR repositories are community-maintained. Use at your own risk.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._run_command(
                self._backend.build_add_copr_command(copr_name),
                f"Adding COPR: {copr_name}",
            )

    # ═══════════════════════════════════════════════════════════════
    #  History
    # ═══════════════════════════════════════════════════════════════

    def _load_history(self):
        self._history_page.set_loading(True)
        self._progress_bar.start_indeterminate()
        self._status_bar.show_message("Loading transaction history...")

        worker = HistoryWorker(self._backend)
        worker.finished.connect(self._on_history_loaded)
        worker.error.connect(self._on_worker_error)
        worker.start()
        self._current_worker = worker

    def _on_history_loaded(self, history):
        self._progress_bar.stop()
        self._history_page.set_loading(False)
        self._history_page.display_history(history)
        self._status_bar.show_success(f"Loaded {len(history)} transactions")

    def _history_undo(self, txn_id: str):
        reply = QMessageBox.question(
            self, "Undo Transaction",
            f"Undo transaction #{txn_id}?\n\n"
            "This will reverse the changes made in that transaction.\n"
            "You will be prompted for your password.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._run_command(
                self._backend.build_history_undo_command(txn_id),
                f"Undoing transaction #{txn_id}",
            )

    def _history_info(self, txn_id: str):
        """Get and show detailed info for a history transaction."""
        detail = self._backend.history_info(txn_id)
        self._history_page.show_detail(detail)

    # ═══════════════════════════════════════════════════════════════
    #  Command Runner & Error Handling
    # ═══════════════════════════════════════════════════════════════

    def _run_command(self, cmd: list[str], operation: str):
        """Run a command and stream output to terminal page."""
        self._switch_page(PAGE_TERMINAL)
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

        # Clear old signals to prevent connecting multiple times to dead workers
        try:
            self._terminal_page.input_submitted.disconnect()
            self._terminal_page.cancel_clicked.disconnect()
        except TypeError:
            pass

        self._terminal_page.input_submitted.connect(worker.write_input)
        self._terminal_page.cancel_clicked.connect(worker.cancel)

        worker.start()
        self._command_worker = worker

    def _on_command_done(self, exit_code: int, operation: str):
        self._progress_bar.stop()

        if exit_code == 0:
            self._terminal_page.set_success()
            self._status_bar.show_success(f"{operation} completed successfully")
        else:
            self._terminal_page.set_error()
            self._status_bar.show_error(f"{operation} failed (exit code {exit_code})")

        # Invalidate caches so data reloads on next visit
        self._installed_page._all_packages = []
        self._flatpak_page._all_apps = []

    def _on_command_error(self, error: str):
        self._progress_bar.stop()
        self._terminal_page.set_error()
        self._terminal_page.append_line(f"\n❌ Error: {error}")
        self._status_bar.show_error(error)

    def _on_worker_error(self, error: str):
        self._progress_bar.stop()
        self._status_bar.show_error(error)
        QMessageBox.warning(self, "Operation Failed", f"An error occurred:\n\n{error}")
