"""Main application window — orchestrates all pages and DNF operations."""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget,
    QMessageBox, QApplication, QFrame, QDialog, QLabel, QPushButton
)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QKeySequence, QShortcut, QIcon, QDesktopServices
import os

from dnf_gui.core.dnf_backend import DNFBackend
from dnf_gui.core.flatpak_backend import FlatpakBackend
from dnf_gui.core.discover_manager import DiscoverManager
from dnf_gui.core.security import build_security_update_command
from dnf_gui.core.app_settings import (
    AppSettings, perform_background_check, send_desktop_notification,
)
from dnf_gui.core.worker import (
    PackageListWorker, UpdateCheckWorker,
    PackageInfoWorker, CommandWorker,
    SystemInfoWorker, FlatpakListWorker, FlatpakSearchWorker,
    HistoryWorker, RepoListWorker, GroupListWorker,
    ToolkitCheckWorker, AppUpdateWorker, AppUpdateDownloadWorker,
    SecurityCheckWorker, CombinedUpdateCheckWorker, DiscoverStatusWorker,
    RebootCheckWorker,
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
from dnf_gui.ui.pages.settings_page import SettingsPage
from dnf_gui.ui.widgets.progress_bar import AnimatedProgressBar


# Page index constants
PAGE_UPDATES = 0
PAGE_INSTALLED = 1
PAGE_FLATPAK = 2
PAGE_SYSINFO = 3
PAGE_TOOLKIT = 4
PAGE_REPOS = 5
PAGE_HISTORY = 6
PAGE_TERMINAL = 7
PAGE_SETTINGS = 8


class MainWindow(QMainWindow):
    """Main application window with sidebar navigation and stacked pages."""

    def __init__(self):
        super().__init__()
        self._backend = DNFBackend()
        self._flatpak_backend = FlatpakBackend()
        self._discover_manager = DiscoverManager()
        self._app_settings = AppSettings()
        self._current_worker = None
        self._history_loading = False  # prevent concurrent history refreshes
        self._command_worker = None
        self._app_update_worker = None  # Must keep ref to avoid QThread GC crash
        self._pending_update_info = None  # App update available
        self._updates_cache: dict | None = None  # last scan; revisit reuses it

        self._setup_window()
        self._setup_ui()
        self._connect_signals()
        self._setup_shortcuts()

        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, self._refresh_current)
        QTimer.singleShot(3000, self._check_app_update)  # Check for app updates after 3s
        QTimer.singleShot(15000, self._maybe_background_reminder)  # in-app reminder
        self._reminder_timer = QTimer(self)
        self._reminder_timer.setInterval(3600 * 1000)  # hourly throttle check
        self._reminder_timer.timeout.connect(self._maybe_background_reminder)
        self._reminder_timer.start()

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

        # Progress bar slot (fixed height so content doesn't shift when bar shows/hides)
        progress_slot = QFrame()
        progress_slot.setObjectName("progress_bar_slot")
        progress_slot.setFixedHeight(4)
        progress_layout = QVBoxLayout(progress_slot)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setSpacing(0)
        self._progress_bar = AnimatedProgressBar()
        self._progress_bar.hide()
        progress_layout.addWidget(self._progress_bar)
        inner_layout.addWidget(progress_slot)

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
        self._settings_page = SettingsPage()

        self._stack.addWidget(self._updates_page)     # 0
        self._stack.addWidget(self._installed_page)    # 1
        self._stack.addWidget(self._flatpak_page)      # 2
        self._stack.addWidget(self._sysinfo_page)      # 3
        self._stack.addWidget(self._toolkit_page)      # 4
        self._stack.addWidget(self._repo_page)         # 5
        self._stack.addWidget(self._history_page)      # 6
        self._stack.addWidget(self._terminal_page)     # 7
        self._stack.addWidget(self._settings_page)     # 8

        inner_layout.addWidget(self._stack, 1)
        main_layout.addWidget(content_wrapper, 1)

    def _connect_signals(self):
        """Connect all page signals to handlers."""
        # Sidebar
        self._sidebar.page_changed.connect(self._on_page_changed)
        self._sidebar.update_clicked.connect(self._on_update_clicked)
        self._sidebar.theme_toggle_requested.connect(self._toggle_theme)

        # Updates page
        self._updates_page.check_updates_clicked.connect(self._check_updates)
        self._updates_page.upgrade_all_clicked.connect(self._upgrade_all)
        self._updates_page.update_everything_clicked.connect(self._update_everything)
        self._updates_page.security_upgrade_clicked.connect(self._security_upgrade)
        self._updates_page.upgrade_package_clicked.connect(self._install_package)
        self._updates_page.details_requested.connect(self._show_package_details)
        self._updates_page.reboot_requested.connect(self._reboot_now)
        self._updates_page.autoremove_clicked.connect(self._autoremove)

        # Installed page
        self._installed_page.remove_clicked.connect(self._remove_package)
        self._installed_page.details_requested.connect(self._show_package_details)
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

        # Settings page — Discover + reminders
        self._settings_page.discover_refresh_requested.connect(self._load_discover_status)
        self._settings_page.discover_takeover_requested.connect(self._discover_takeover)
        self._settings_page.discover_restore_requested.connect(self._discover_restore)
        self._settings_page.discover_system_disable_requested.connect(
            self._discover_system_disable)
        self._settings_page.discover_system_enable_requested.connect(
            self._discover_system_enable)
        self._settings_page.discover_kill_requested.connect(self._discover_kill)
        self._settings_page.discover_remove_notifier_requested.connect(
            self._discover_remove_notifier)
        self._settings_page.reminders_save_requested.connect(self._save_reminders)
        self._settings_page.reminders_test_requested.connect(self._test_reminder)
        self._settings_page.checker_toggle_requested.connect(self._toggle_checker)
        self._settings_page.passwordless_enable_requested.connect(
            self._enable_passwordless)
        self._settings_page.passwordless_disable_requested.connect(
            self._disable_passwordless)
        self._settings_page.passwordless_refresh_requested.connect(
            self._load_passwordless_status)

    def _setup_shortcuts(self):
        """Set up keyboard shortcuts."""
        QShortcut(QKeySequence("Ctrl+R"), self, self._refresh_current)
        QShortcut(QKeySequence("Ctrl+F"), self, self._focus_search)
        # Ctrl+1..9 = Switch pages
        for i in range(9):
            QShortcut(
                QKeySequence(f"Ctrl+{i+1}"), self,
                lambda idx=i: self._switch_page(idx)
            )

    def _focus_search(self):
        """Focus the search input on pages that have one (Ctrl+F)."""
        index = self._stack.currentIndex()
        page = None
        if index == PAGE_INSTALLED:
            page = self._installed_page
        elif index == PAGE_FLATPAK:
            page = self._flatpak_page
        elif index == PAGE_REPOS:
            page = self._repo_page
        if page is not None:
            try:
                page.focus_search()
            except Exception:
                pass

    # ═══════════════════════════════════════════════════════════════
    #  Page Navigation
    # ═══════════════════════════════════════════════════════════════

    def _on_page_changed(self, index: int):
        """Handle sidebar page change, auto-load data on first visit."""
        try:
            self._stack.setCurrentIndex(index)
            self._refresh_current()
        except Exception as e:
            import traceback
            traceback.print_exc()

    def _switch_page(self, index: int):
        self._sidebar.set_active_page(index)
        self._on_page_changed(index)

    def _toggle_theme(self):
        """Cycle dark -> light -> dark, persist, and re-apply stylesheet."""
        try:
            from PyQt6.QtWidgets import QApplication
            from dnf_gui.ui.styles.theme import (
                get_stylesheet, get_saved_theme_mode,
                save_theme_mode, resolve_mode,
            )
            current = resolve_mode()
            new_mode = "light" if current == "dark" else "dark"
            save_theme_mode(new_mode)
            app = QApplication.instance()
            if app is not None:
                app.setStyleSheet(get_stylesheet(new_mode))
            self._sidebar.apply_theme(new_mode)
        except Exception:
            import traceback
            traceback.print_exc()

    def _refresh_current(self):
        try:
            index = self._stack.currentIndex()
            if index == PAGE_UPDATES:
                # Reuse the last scan — rescan only via Check button,
                # fresh app start, or after something actually changed.
                if self._updates_cache is not None:
                    self._redisplay_cached_updates()
                else:
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
            elif index == PAGE_SETTINGS:
                self._load_settings_page()
        except Exception as e:
            import traceback
            traceback.print_exc()

    # ═══════════════════════════════════════════════════════════════
    #  DNF Package Operations
    # ═══════════════════════════════════════════════════════════════

    def _check_updates(self):
        self._updates_page.set_loading(True)
        self._progress_bar.start_indeterminate()

        worker = CombinedUpdateCheckWorker(
            self._backend, self._flatpak_backend, parent=self)
        worker.finished.connect(self._on_combined_checked)
        worker.error.connect(self._on_worker_error)
        worker.start()
        self._current_worker = worker

    def _redisplay_cached_updates(self):
        """Show the last scan instantly — no worker, no progress bar."""
        try:
            result = self._updates_cache or {}
            info = result.get("dnf")
            if info is None:
                self._check_updates()
                return
            flatpak_updates = result.get("flatpak") or []
            total = self._updates_page.display_combined(
                info, flatpak_updates, result.get("security"),
                preview=result.get("preview"),
                security_preview=result.get("security_preview"),
                reboot=result.get("reboot", False))
            self._sidebar.set_update_badge(total)
        except Exception:
            import traceback
            traceback.print_exc()
            self._check_updates()

    def _on_combined_checked(self, result: dict):
        try:
            self._progress_bar.stop()
            self._updates_page.set_loading(False)
            info = result.get("dnf")
            flatpak_updates = result.get("flatpak") or []
            security = result.get("security")
            total = self._updates_page.display_combined(
                info, flatpak_updates, security,
                preview=result.get("preview"),
                security_preview=result.get("security_preview"),
                reboot=result.get("reboot", False))
            self._sidebar.set_update_badge(total)
            self._updates_cache = result  # revisit reuses this scan
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._progress_bar.stop()
            self._updates_page.set_loading(False)
            QMessageBox.warning(self, "Error", f"Failed to load updates: {e}")

    def _on_updates_checked(self, info):
        try:
            self._progress_bar.stop()
            self._updates_page.set_loading(False)
            self._updates_page.display_updates(info)
            self._sidebar.set_update_badge(info.total_updates)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._progress_bar.stop()
            self._updates_page.set_loading(False)
            QMessageBox.warning(self, "Error", f"Failed to load updates: {e}")

    def _load_installed(self):
        self._installed_page.set_loading(True)
        self._progress_bar.start_indeterminate()

        worker = PackageListWorker(self._backend, parent=self)
        worker.finished.connect(self._on_installed_loaded)
        worker.error.connect(self._on_worker_error)
        worker.start()
        self._current_worker = worker

    def _on_installed_loaded(self, packages):
        self._progress_bar.stop()
        self._installed_page.set_loading(False)
        self._installed_page.display_packages(packages)

    # ═══════════════════════════════════════════════════════════════
    #  Privileged Package Operations
    # ═══════════════════════════════════════════════════════════════

    def _preview_line(self, preview, count_fallback: int = 0) -> str:
        """One-line 'N packages, ~X download' summary ('' if unknown)."""
        if preview is not None and preview.has_preview:
            if preview.sizes_known and preview.total_bytes > 0:
                from dnf_gui.utils.helpers import format_size
                return (f"{preview.count} packages, "
                        f"~{format_size(preview.total_bytes)} download")
            return f"{preview.count} packages"
        if count_fallback:
            return f"{count_fallback} packages"
        return ""

    def _upgrade_all(self):
        preview = self._preview_line(self._updates_page.upgrade_preview)
        detail = f"\n\n{preview}." if preview else ""
        reply = QMessageBox.question(
            self, "Confirm Upgrade",
            "This will upgrade all packages on your system."
            f"{detail}\n\n"
            "You will be prompted for your password unless passwordless "
            "updates are enabled.\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._run_command(self._backend.build_upgrade_command(), "System Upgrade")

    def _update_everything(self):
        dnf_preview = self._preview_line(self._updates_page.upgrade_preview)
        reply = QMessageBox.question(
            self, "Update Everything?",
            "This runs back-to-back in one terminal session:\n\n"
            "1. dnf upgrade --refresh (system packages"
            f"{f' — {dnf_preview}' if dnf_preview else ''})\n"
            "2. flatpak update -y (all Flatpak apps)\n\n"
            "System packages need your password unless passwordless "
            "updates are enabled in Settings.\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._run_command_chain(
                [self._backend.build_upgrade_command(),
                 self._flatpak_backend.build_update_all_command()],
                "Update Everything (DNF + Flatpak)")

    def _security_upgrade(self):
        preview = self._preview_line(self._updates_page.security_preview)
        detail = f"\n\n{preview}." if preview else ""
        reply = QMessageBox.question(
            self, "Security Updates Only?",
            "Install only security advisories?\n\n"
            "Runs: dnf upgrade --security"
            f"{detail}\n\n"
            "Recommended when you want the important fixes fast without "
            "pulling every feature update. You will be prompted for your "
            "password unless passwordless updates are enabled.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._run_command(
                build_security_update_command(), "Security Upgrade")

    def _show_package_details(self, name: str):
        """Show a Details dialog for one package (fetched in background)."""
        from dnf_gui.ui.widgets.package_details import PackageDetailsDialog
        dialog = PackageDetailsDialog(name, self)
        worker = PackageInfoWorker(self._backend, name, parent=dialog)
        worker.finished.connect(dialog.display_package)
        worker.error.connect(lambda _e: dialog.display_package(None))
        worker.start()
        dialog.exec()

    def _reboot_now(self):
        """Reboot after confirmation (logind allows active local users)."""
        reply = QMessageBox.warning(
            self, "Reboot Now?",
            "Reboot the system now to finish applying updates?\n\n"
            "Save your work first. Unsaved changes will be lost.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        import subprocess
        try:
            result = subprocess.run(
                ["systemctl", "reboot"],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode != 0:
                QMessageBox.warning(
                    self, "Reboot Failed",
                    f"Could not reboot:\n\n"
                    f"{(result.stderr or result.stdout).strip() or 'unknown error'}\n\n"
                    "Try rebooting from the KDE application menu.")
        except FileNotFoundError:
            QMessageBox.warning(
                self, "Reboot Failed", "systemctl not found on this system.")
        except Exception as e:
            QMessageBox.warning(self, "Reboot Failed", str(e))

    def _recheck_reboot_banner(self):
        """Refresh the reboot banner after a successful upgrade."""
        worker = RebootCheckWorker(self._backend, parent=self)
        worker.finished.connect(self._updates_page.set_reboot_banner)
        worker.error.connect(lambda _e: None)
        worker.start()
        self._reboot_check_worker = worker  # keep ref (QThread GC safety)

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
        reply = QMessageBox.warning(
            self, "Clean Up: Proceed With Caution",
            "This will run: dnf autoremove -y\n\n"
            "What it does: Removes packages that were installed as dependencies of other "
            "packages but are no longer needed (e.g. after you uninstalled something).\n\n"
            "While this is mostly safe, it may remove packages you actually want to keep. "
            "For example, libraries you use manually or packages with weak dependency links.\n\n"
            "You will be prompted for your password.\n\n"
            "Proceed with caution. Do you want to continue?",
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

        worker = FlatpakListWorker(self._flatpak_backend, parent=self)
        worker.finished.connect(self._on_flatpaks_loaded)
        worker.error.connect(self._on_worker_error)
        worker.start()
        self._current_worker = worker

    def _on_flatpaks_loaded(self, apps):
        self._progress_bar.stop()
        self._flatpak_page.display_installed(apps)

    def _search_flatpaks(self, query: str):
        self._flatpak_page.set_search_loading(True)
        self._progress_bar.start_indeterminate()

        worker = FlatpakSearchWorker(self._flatpak_backend, query, parent=self)
        worker.finished.connect(self._on_flatpak_search_done)
        worker.error.connect(self._on_worker_error)
        worker.start()
        self._current_worker = worker

    def _on_flatpak_search_done(self, apps):
        self._progress_bar.stop()
        self._flatpak_page.display_search_results(apps)

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

        worker = SystemInfoWorker(parent=self)
        worker.finished.connect(self._on_sysinfo_loaded)
        worker.error.connect(self._on_worker_error)
        worker.start()
        self._current_worker = worker

    def _on_sysinfo_loaded(self, info):
        self._progress_bar.stop()
        self._sysinfo_page.display_info(info)

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
        }

        if tool_id not in tool_map:
            QMessageBox.warning(self, "Unknown Tool", f"Unknown tool: {tool_id}")
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

        worker = RepoListWorker(self._backend, show_all=True, parent=self)
        worker.finished.connect(self._on_repos_loaded)
        worker.error.connect(self._on_worker_error)
        worker.start()
        self._current_worker = worker

    def _on_repos_loaded(self, repos):
        self._progress_bar.stop()
        self._repo_page.display_repos(repos)

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
        try:
            cmd = self._backend.build_add_copr_command(copr_name)
        except ValueError as e:
            QMessageBox.warning(
                self, "Invalid COPR",
                f"{e}\n\nExample: user/my-project",
            )
            return
        reply = QMessageBox.question(
            self, "Add COPR Repository",
            f"Enable COPR repository: {copr_name}?\n\n"
            "COPR repositories are community-maintained. Use at your own risk.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._run_command(cmd, f"Adding COPR: {copr_name}")

    # ═══════════════════════════════════════════════════════════════
    #  History
    # ═══════════════════════════════════════════════════════════════

    def _load_history(self):
        # If a history load is already in progress, ignore additional requests
        if self._history_loading:
            return

        self._history_loading = True

        # Disconnect previous worker to avoid re-entrancy and stale results
        # when user clicks Refresh multiple times quickly
        if self._current_worker is not None:
            try:
                self._current_worker.finished.disconnect()
                self._current_worker.error.disconnect()
            except (TypeError, RuntimeError):
                pass

        self._history_page.set_loading(True)
        self._progress_bar.start_indeterminate()

        worker = HistoryWorker(self._backend, parent=self)
        worker.finished.connect(self._on_history_loaded)
        worker.error.connect(self._on_history_error)
        worker.start()
        self._current_worker = worker

    def _on_history_loaded(self, history):
        self._history_loading = False
        self._progress_bar.stop()
        self._history_page.set_loading(False)
        self._history_page.display_history(history)

    def _on_history_error(self, error: str):
        self._history_loading = False
        self._history_page.set_loading(False)
        self._on_worker_error(error)

    def _history_undo(self, txn_id: str):
        try:
            cmd = self._backend.build_history_undo_command(txn_id)
        except ValueError as e:
            QMessageBox.warning(self, "Invalid Transaction", str(e))
            return
        reply = QMessageBox.question(
            self, "Undo Transaction",
            f"Undo transaction #{txn_id}?\n\n"
            "This will reverse the changes made in that transaction.\n"
            "You will be prompted for your password.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._run_command(cmd, f"Undoing transaction #{txn_id}")

    def _history_info(self, txn_id: str):
        """Get and show detailed info for a history transaction."""
        detail = self._backend.history_info(txn_id)
        self._history_page.show_detail(detail, txn_id)

    # ═══════════════════════════════════════════════════════════════
    #  App Auto-Update
    # ═══════════════════════════════════════════════════════════════

    def _check_app_update(self):
        """Check GitHub for app updates (runs in background)."""
        from dnf_gui import __version__
        worker = AppUpdateWorker(__version__, parent=self)
        worker.finished.connect(self._on_app_update_checked)
        worker.start()
        self._app_update_worker = worker  # Keep ref to prevent QThread GC crash

    def _on_app_update_checked(self, update_info):
        """Handle app update check result."""
        try:
            # Defer worker destruction to avoid QThread GC crash in slot callback
            if self._app_update_worker:
                self._app_update_worker.deleteLater()
                self._app_update_worker = None
            if update_info is None:
                return
            self._pending_update_info = update_info
            self._sidebar.set_update_available(update_info.latest_version)
            self._show_update_dialog(update_info)
        except Exception as e:
            import traceback
            traceback.print_exc()

    def _on_update_clicked(self):
        """Show update dialog when user clicks version/update area."""
        try:
            if self._pending_update_info:
                self._show_update_dialog(self._pending_update_info)
        except Exception as e:
            import traceback
            traceback.print_exc()

    def _show_update_dialog(self, update_info):
        """Show dialog with update available and options."""
        try:
            from dnf_gui import __version__
            msg = (
                f"DNF Package Manager <b>v{update_info.latest_version}</b> is available.\n\n"
                f"You have v{__version__}.\n\n"
                "Choose how to update:"
            )
            dialog = QDialog(self)
            dialog.setWindowTitle("Update Available")
            layout = QVBoxLayout(dialog)
            lbl = QLabel(msg)
            lbl.setTextFormat(Qt.TextFormat.RichText)
            layout.addWidget(lbl)
            layout.addSpacing(12)

            btn_open = QPushButton("Open Releases Page")
            btn_open.clicked.connect(lambda: self._open_releases(update_info.release_url, dialog))
            layout.addWidget(btn_open)

            if update_info.download_url:
                btn_install = QPushButton("Download & Install")
                btn_install.clicked.connect(lambda: self._install_app_update(update_info, dialog))
                layout.addWidget(btn_install)

            btn_later = QPushButton("Later")
            btn_later.clicked.connect(dialog.accept)
            layout.addWidget(btn_later)

            dialog.exec()
        except Exception as e:
            import traceback
            traceback.print_exc()

    def _open_releases(self, url: str, dialog: QDialog):
        """Open releases page in browser, with fallback if it fails."""
        if not url:
            QMessageBox.warning(
                self,
                "Open Releases Page",
                "Could not determine the releases URL.\n\n"
                "You can open the project's Releases page manually:\n"
                "https://github.com/grpace/Fedora-DNF-GUI-Tool/releases",
            )
            return

        qurl = QUrl(url)
        if not qurl.isValid():
            QMessageBox.warning(
                self,
                "Open Releases Page",
                f"Release URL is invalid:\n\n{url}\n\n"
                "You can open the project's Releases page manually:\n"
                "https://github.com/grpace/Fedora-DNF-GUI-Tool/releases",
            )
            return

        opened = QDesktopServices.openUrl(qurl)
        if not opened:
            # Give the user a clickable link they can copy/open manually
            QMessageBox.information(
                self,
                "Open Releases Page",
                (
                    "<p>The system was unable to open your web browser automatically.</p>"
                    f"<p>You can open the releases page manually at:<br>"
                    f'<a href="{url}">{url}</a></p>'
                ),
            )
            return

        dialog.accept()

    def _install_app_update(self, update_info, dialog: QDialog):
        """Download RPM and run dnf install."""
        dialog.accept()
        self._switch_page(PAGE_TERMINAL)
        self._terminal_page.set_running(True, "Installing app update")
        self._progress_bar.start_indeterminate()
        self._terminal_page.append_line("\n" + "─" * 60)
        self._terminal_page.append_line("  Installing DNF Package Manager update")
        self._terminal_page.append_line("─" * 60 + "\n")

        download_worker = AppUpdateDownloadWorker(update_info.download_url, parent=self)
        download_worker.finished.connect(
            lambda path: self._on_update_downloaded(path, update_info)
        )
        download_worker.error.connect(self._on_update_download_error)
        download_worker.progress.connect(self._terminal_page.append_line)
        download_worker.start()
        self._current_worker = download_worker

    def _on_update_downloaded(self, rpm_path: str, update_info):
        """Run dnf install on downloaded RPM."""
        self._terminal_page.append_line(f"Downloaded to {rpm_path}")
        self._terminal_page.append_line("Installing via DNF...\n")
        cmd = ["pkexec", "dnf", "install", "-y", rpm_path]
        self._run_command(cmd, "Installing app update")

    def _on_update_download_error(self, error: str):
        """Handle download error."""
        self._progress_bar.stop()
        self._terminal_page.set_error()
        self._terminal_page.append_line(f"\n❌ Download failed: {error}")
        QMessageBox.warning(
            self, "Update Failed",
            f"Could not download the update:\n\n{error}\n\n"
            "Try opening the Releases page to download manually."
        )

    # ═══════════════════════════════════════════════════════════════
    #  Command Runner & Error Handling
    # ═══════════════════════════════════════════════════════════════

    def _run_command(self, cmd: list[str], operation: str):
        """Run a command and stream output to terminal page."""
        self._switch_page(PAGE_TERMINAL)
        self._terminal_page.set_running(True, operation)
        self._progress_bar.start_indeterminate()

        self._terminal_page.append_line(f"\n{'─' * 60}")
        self._terminal_page.append_line(f"  {operation}")
        self._terminal_page.append_line(f"{'─' * 60}\n")

        self._start_worker(
            cmd, lambda code: self._on_command_done(code, operation))

    def _run_command_chain(self, cmds: list[list[str]], operation: str):
        """Run several commands back-to-back in one terminal session.

        Used by Update Everything so the DNF step (privileged) and the
        Flatpak step (unprivileged) share one view. Stops on first failure.
        """
        self._switch_page(PAGE_TERMINAL)
        self._terminal_page.set_running(True, operation)
        self._progress_bar.start_indeterminate()

        self._terminal_page.append_line(f"\n{'─' * 60}")
        self._terminal_page.append_line(f"  {operation} ({len(cmds)} steps)")
        self._terminal_page.append_line(f"{'─' * 60}\n")

        self._cmd_queue = list(cmds)
        self._run_next_in_chain(operation)

    def _run_next_in_chain(self, operation: str):
        if not self._cmd_queue:
            self._on_command_done(0, operation)
            return
        cmd = self._cmd_queue.pop(0)
        short = " ".join(cmd[1:3]) if len(cmd) > 2 else " ".join(cmd)
        self._terminal_page.append_line(f"\n── Step: {short} ──\n")
        self._start_worker(
            cmd, lambda code: self._on_chain_step_done(code, operation))

    def _on_chain_step_done(self, exit_code: int, operation: str):
        if exit_code != 0:
            self._progress_bar.stop()
            self._terminal_page.set_error()
            self._terminal_page.append_line(
                f"\n✗ Step failed (exit {exit_code}) — stopping here. "
                "Fix the error above and re-run.")
            # Invalidate caches so data reloads on next visit
            self._installed_page._all_packages = []
            self._flatpak_page._all_apps = []
            return
        if self._cmd_queue:
            self._run_next_in_chain(operation)
        else:
            self._on_command_done(0, operation)

    def _start_worker(self, cmd: list[str], done_cb, _retried: bool = False,
                      _collected: list | None = None):
        """Start a CommandWorker, swapping pkexec→sudo -n when covered.

        If the passwordless rule claims to cover the command but sudo still
        demands a password (e.g. the rule was deleted outside the app),
        retry exactly once via pkexec so the user gets a password prompt
        instead of a cryptic failure.
        """
        from dnf_gui.core.passwordless import maybe_passwordless
        scope = self._app_settings.passwordless_scope
        effective = maybe_passwordless(cmd, scope)
        if effective != cmd:
            self._terminal_page.append_line(
                "(passwordless updates rule active — no password needed)")

        collected: list = [] if _collected is None else _collected
        worker = CommandWorker(effective, parent=self)

        def _on_line(line: str):
            collected.append(line)
            self._terminal_page.append_line(line)

        def _on_done(code: int):
            if (code != 0 and not _retried
                    and effective and effective[0] == "sudo"
                    and any("password" in line.lower() for line in collected)):
                self._terminal_page.append_line(
                    "(passwordless rule didn't apply — "
                    "falling back to password prompt)")
                self._start_worker(cmd, done_cb, _retried=True)
                return
            done_cb(code)

        worker.output_line.connect(_on_line)
        worker.finished.connect(_on_done)
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
            if operation == "Installing app update":
                self._terminal_page.append_line(
                    "\n✅ Update installed. Please restart the app to use the new version."
                )
        else:
            self._terminal_page.set_error()

        # Invalidate caches so data reloads on next visit
        self._installed_page._all_packages = []
        self._flatpak_page._all_apps = []
        if exit_code == 0:
            # System state changed → next Updates visit must rescan.
            self._updates_cache = None

        if operation in ("Enabling passwordless updates",
                         "Disabling passwordless updates"):
            self._load_passwordless_status()

        # A finished upgrade may leave a reboot pending (new kernel etc.)
        if exit_code == 0 and operation in (
                "System Upgrade", "Update Everything (DNF + Flatpak)",
                "Security Upgrade"):
            self._recheck_reboot_banner()

    def _on_command_error(self, error: str):
        self._progress_bar.stop()
        self._terminal_page.set_error()
        self._terminal_page.append_line(f"\n❌ Error: {error}")

    def _on_worker_error(self, error: str):
        self._progress_bar.stop()
        QMessageBox.warning(self, "Operation Failed", f"An error occurred:\n\n{error}")

    # ═══════════════════════════════════════════════════════════════
    #  Settings — Discover takeover + reminders
    # ═══════════════════════════════════════════════════════════════

    def _load_settings_page(self):
        prefs = {
            "enabled": self._app_settings.reminders_enabled,
            "security_only": self._app_settings.security_only,
            "notify_flatpak": self._app_settings.notify_flatpak,
            "interval_hours": self._app_settings.check_interval_hours,
        }
        last = self._app_settings.get_last_check()
        last_str = last.strftime("%Y-%m-%d %I:%M %p") if last else ""
        self._settings_page.load_reminder_settings(
            prefs, AppSettings.is_checker_installed(), last_str)
        self._load_discover_status()
        self._load_passwordless_status()

    def _load_discover_status(self):
        self._progress_bar.start_indeterminate()
        worker = DiscoverStatusWorker(parent=self)
        worker.finished.connect(self._on_discover_status)
        worker.error.connect(self._on_worker_error)
        worker.start()
        self._current_worker = worker

    def _on_discover_status(self, status):
        self._progress_bar.stop()
        self._settings_page.display_discover_status(status)

    def _discover_takeover(self):
        reply = QMessageBox.question(
            self, "Use This App for Updates?",
            "Disable Discover's automatic update checks for your user?\n\n"
            "• Stops Discover's background checker (no password needed, reversible)\n"
            "• Silences Discover popups and restart-time updates\n"
            "• DNF Package Manager becomes your updater\n\n"
            "Discover itself stays installed — you can still open it manually.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self._discover_manager.set_per_user_enabled(False)
        except Exception as e:
            QMessageBox.warning(self, "Takeover Failed", str(e))
            return
        # Best-effort: stop the currently running notifier
        import subprocess
        try:
            subprocess.run(["pkill", "-x", "DiscoverNotifier"], timeout=5)
        except Exception:
            pass
        QMessageBox.information(
            self, "This App Handles Updates",
            "Discover will no longer check or notify for your user.\n\n"
            "Use the Updates page plus reminders in this app instead.\n"
            "You can restore Discover anytime from this page.")
        self._load_discover_status()

    def _discover_restore(self):
        try:
            self._discover_manager.set_per_user_enabled(True)
        except Exception as e:
            QMessageBox.warning(self, "Restore Failed", str(e))
            return
        QMessageBox.information(
            self, "Discover Restored",
            "Discover's notifier autostart + popups were re-enabled for your user.")
        self._load_discover_status()

    def _discover_system_disable(self):
        reply = QMessageBox.warning(
            self, "Disable System-Wide?",
            "This runs as root (pkexec):\n\n"
            "• Removes /etc/xdg/autostart/org.kde.discover.notifier.desktop\n"
            "• Masks packagekit-offline-update.service (no surprise reboot updates)\n\n"
            "packagekit.service itself is left intact so manual pkcon still works.\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        for cmd in self._discover_manager.build_system_disable_commands():
            self._run_command(cmd, "Disabling Discover system-wide")
            break  # one chained command; terminal shows output

    def _discover_system_enable(self):
        reply = QMessageBox.question(
            self, "Re-enable System Services?",
            "Unmask packagekit-offline-update.service?\n\n"
            "Note: the system autostart file is owned by the "
            "plasma-discover-notifier package — reinstall that package "
            "to fully restore it.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        for cmd in self._discover_manager.build_system_enable_commands():
            self._run_command(cmd, "Re-enabling PackageKit offline updates")
            break

    def _discover_kill(self):
        import subprocess
        try:
            subprocess.run(["pkill", "-x", "DiscoverNotifier"], timeout=5)
            QMessageBox.information(
                self, "Checker Stopped",
                "Discover's background checker was stopped (it returns at "
                "next login unless this app handles updates).")
        except Exception as e:
            QMessageBox.warning(self, "Stop Failed", str(e))
        self._load_discover_status()

    def _discover_remove_notifier(self):
        reply = QMessageBox.warning(
            self, "Uninstall Update Checker?",
            "Uninstall the Discover update checker package but keep Discover itself?\n\n"
            "This stops automatic checks for everyone on this PC (needs password). "
            "Reinstall the package to undo.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._run_command(
                self._discover_manager.build_remove_notifier_package_command(),
                "Removing plasma-discover-notifier")

    # ─── Reminders ──────────────────────────────────────────────

    def _save_reminders(self, prefs: dict):
        self._app_settings.reminders_enabled = bool(prefs.get("enabled"))
        self._app_settings.security_only = bool(prefs.get("security_only"))
        self._app_settings.notify_flatpak = bool(prefs.get("notify_flatpak", True))
        try:
            self._app_settings.check_interval_hours = int(
                prefs.get("interval_hours", 24))
        except (TypeError, ValueError):
            pass
        QMessageBox.information(self, "Settings Saved",
                                "Reminder preferences saved.")
        self._load_settings_page()

    def _toggle_checker(self, enabled: bool):
        try:
            AppSettings.set_checker_installed(enabled)
        except Exception as e:
            QMessageBox.warning(self, "Autostart Failed", str(e))
            return
        if enabled and not self._app_settings.reminders_enabled:
            self._app_settings.reminders_enabled = True
        QMessageBox.information(
            self, "Login Checker",
            "Login reminder check ENABLED — `dnf-gui --check` will run at login."
            if enabled else "Login reminder check disabled.")

    def _test_reminder(self):
        sent = send_desktop_notification(
            "DNF Package Manager",
            "Test: reminders are working. You'll be notified here about security updates.")
        if sent:
            QMessageBox.information(self, "Test Sent",
                                    "Test notification sent via notify-send.")
        else:
            QMessageBox.information(
                self, "Test Notification",
                "notify-send isn't available, but in-app reminders are configured.\n\n"
                "This is what you'd see:\n"
                "“Security updates are pending — open DNF Package Manager.”")

    def _maybe_background_reminder(self):
        """Hourly in-app check — only notifies when due + something pending."""
        try:
            if not self._app_settings.is_check_due():
                return
            result = perform_background_check(self._app_settings)
            if not result.should_notify:
                return
            title = ("⚠ Security updates pending!"
                     if result.security_urgent else "System updates available")
            delivered = send_desktop_notification(title, result.message,
                                                  urgent=result.security_urgent)
            if not delivered:
                # Fall back to updating the sidebar badge + status so the
                # user still sees it inside the app.
                self._sidebar.set_update_badge(result.total)
        except Exception:
            pass

    # ─── Passwordless updates ───────────────────────────────────

    def _load_passwordless_status(self):
        from dnf_gui.core import passwordless as pw
        try:
            live = pw.live_scope()
        except Exception:
            live = "off"
        remembered = self._app_settings.passwordless_scope
        self._settings_page.display_passwordless_status(remembered, live)

    def _enable_passwordless(self, scope: str):
        from dnf_gui.core import passwordless as pw
        if scope not in ("updates", "full"):
            scope = "updates"
        user = pw.current_user()
        if not user:
            QMessageBox.warning(
                self, "Cannot Enable",
                "Could not determine your login name, so a per-user rule "
                "can't be written safely. Aborting.")
            return
        if scope == "full":
            msg = (
                "Enable passwordless for ALL dnf operations?\n\n"
                "This removes every password prompt — including installs, "
                "removals and repo changes. Any program running as you could "
                "then change system packages without asking.\n\n"
                "Only do this on a single-user desktop where you accept the "
                "tradeoff. 'Updates only' is the safer choice.\n\n"
                "You will authenticate ONCE now to install the rule.\n\nContinue?"
            )
            default = QMessageBox.StandardButton.No
        else:
            msg = (
                "Enable passwordless system updates?\n\n"
                "• `dnf upgrade` will run without a password\n"
                "• Installs, removals, repo changes and firmware updates "
                "will STILL ask\n\n"
                "Installs a validated per-user sudoers file "
                "(/etc/sudoers.d/90-dnf-gui). You will authenticate ONCE now.\n\n"
                "Continue?"
            )
            default = QMessageBox.StandardButton.Yes
        reply = QMessageBox.question(
            self, "Passwordless Updates", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            default,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        content = pw.build_rule_content(user, scope)
        ok, validation_msg = pw.validate_content(content)
        if not ok:
            QMessageBox.warning(
                self, "Validation Failed",
                f"The generated rule did not pass visudo -c, aborting "
                f"before touching the system:\n\n{validation_msg}")
            return
        self._app_settings.passwordless_scope = scope
        self._run_command(
            pw.build_install_commands(content),
            "Enabling passwordless updates")

    def _disable_passwordless(self):
        from dnf_gui.core import passwordless as pw
        reply = QMessageBox.question(
            self, "Restore Password Prompts?",
            "Remove the sudoers rule so every privileged step asks for "
            "your password again?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._app_settings.passwordless_scope = "off"
        self._run_command(
            pw.build_remove_commands(), "Disabling passwordless updates")
