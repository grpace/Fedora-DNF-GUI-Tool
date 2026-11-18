"""The QML app's root object: navigation, activation, window close,
post-operation bookkeeping, reminders and the app's own updates.

It replaces v1's ``MainWindow`` orchestration. Page logic lives in the
page controllers; every worker is parented to a controller so
:meth:`shutdown_threads` can find it.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

from PyQt6.QtCore import (
    QObject, QThread, QTimer, QUrl, pyqtProperty, pyqtSignal, pyqtSlot,
)
from PyQt6.QtGui import QColor, QDesktopServices, QIcon

from dnf_gui import __version__
from dnf_gui.core.app_settings import AppSettings
from dnf_gui.core.discover_manager import DiscoverManager
from dnf_gui.core.dnf_backend import DNFBackend
from dnf_gui.core.flatpak_backend import FlatpakBackend
from dnf_gui.core.notifications import Notification, Notifier, reminder_notification
from dnf_gui.core.security import parse_blocked_updates, parse_unavailable_updates
from dnf_gui.core.worker import (
    AppIconsWorker, AppUpdateDownloadWorker, AppUpdateWorker, ReminderCheckWorker,
)
from dnf_gui.ui.controllers.base import StateObject, state_property
from dnf_gui.ui.controllers.pages import (
    FlatpakController, HistoryController, PackagesController, ReposController,
    SystemController,
)
from dnf_gui.ui.controllers.prompts import ERROR, Prompts
from dnf_gui.ui.controllers.runner import CANCELLED_EXIT_CODES, OperationRunner
from dnf_gui.ui.controllers.settings import SettingsController
from dnf_gui.ui.controllers.updates import UpdatesController
from dnf_gui.ui.iconset import IconSet

RELEASES_URL = "https://github.com/grpace/Fedora-DNF-GUI-Tool/releases"
WEBSITE_URL = "https://greg.tech"

# Stable page keys: ``--page``, notification clicks and the single-instance
# socket use them (app.PAGE_CHOICES). Order = Ctrl+1..9, as in v1.
PAGES = ("updates", "installed", "flatpak", "sysinfo", "tools", "repos",
         "history", "terminal", "settings")
# "terminal" isn't a page any more: it opens the activity panel.
ACTIVITY = "terminal"

# dnf upgrades: report skipped packages and recheck the reboot banner after.
UPGRADE_OPERATIONS = (
    "System Upgrade", "Update Everything (DNF + Flatpak)", "Security Upgrade",
    "Update Without Core", "Forced Security Upgrade",
)


class AppController(StateObject):
    """Root object exposed to QML as ``App``."""

    changed = pyqtSignal()
    # QML: focus the current page's search field (Ctrl+F).
    focusSearchRequested = pyqtSignal()
    # QML: show this error inline (unexpected exception in a slot).
    errorRaised = pyqtSignal(str)

    _defaults = {
        "currentPage": "updates",
        "updateBadge": 0,
        "activityExpanded": False,
        "activityVisible": False,
        "appUpdate": {},
        "appIconsReady": False,
    }
    currentPage = state_property(str, "currentPage", changed)
    updateBadge = state_property(int, "updateBadge", changed)
    activityExpanded = state_property(bool, "activityExpanded", changed)
    activityVisible = state_property(bool, "activityVisible", changed)
    appUpdate = state_property("QVariantMap", "appUpdate", changed)
    appIconsReady = state_property(bool, "appIconsReady", changed)

    def __init__(self, initial_page: str = "", parent=None):
        super().__init__(parent)
        self.backend = DNFBackend()
        self.flatpak_backend = FlatpakBackend()
        self.discover_manager = DiscoverManager()
        self.settings = AppSettings()
        self.prompts = Prompts(self)
        self.runner = OperationRunner(self.settings, self.prompts, self)
        self.notifier = Notifier(self)
        self.updates = UpdatesController(self, self)
        self.packages = PackagesController(self, self)
        self.flatpak = FlatpakController(self, self)
        self.repos = ReposController(self, self)
        self.history = HistoryController(self, self)
        self.system = SystemController(self, self)
        self.settings_controller = SettingsController(self, self)
        self.icons = IconSet()
        self._app_icons: dict[str, dict] = {}
        self._theme_icons: dict[str, bool] = {}

        self.forced_removals: list[str] = []
        self.pending_release_target: int | None = None
        self.detached_threads: list[QThread] = []
        self._window = None
        self._instance_server = None
        self._quit_when_done = False
        self._reminder_notification_id = 0
        self._pending_update_info = None
        self._reminder_worker = None

        self.runner.finished.connect(self._on_operation_finished)
        self.runner.changed.connect(self._sync_activity)
        self.notifier.activated.connect(self.activate)
        self.prompts.attentionNeeded.connect(self._show_for_prompt)

        if initial_page == ACTIVITY:
            self._set(activityExpanded=True, activityVisible=True)
        elif initial_page in PAGES:
            self._set(currentPage=initial_page)

        # Startup work on timers owned by the controller, so they stop with it.
        self._startup_timers = []
        for delay, slot in ((0, self.refreshCurrent), (3000, self._check_app_update),
                            (15000, self._maybe_background_reminder),
                            (0, self._refresh_background_checker),
                            (200, self._load_app_icons)):
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(slot)
            timer.start(delay)
            self._startup_timers.append(timer)
        self._closing_prompt = False
        self._reminder_timer = QTimer(self)
        self._reminder_timer.setInterval(3600 * 1000)  # hourly throttle check
        self._reminder_timer.timeout.connect(self._maybe_background_reminder)
        self._reminder_timer.start()

    # ── objects for QML ────────────────────────────────────────

    @pyqtProperty(QObject, constant=True)
    def Prompts(self):  # noqa: N802 - QML-facing name
        return self.prompts

    @pyqtProperty(QObject, constant=True)
    def Runner(self):  # noqa: N802
        return self.runner

    @pyqtProperty(QObject, constant=True)
    def Updates(self):  # noqa: N802
        return self.updates

    @pyqtProperty(QObject, constant=True)
    def Packages(self):  # noqa: N802
        return self.packages

    @pyqtProperty(QObject, constant=True)
    def Flatpak(self):  # noqa: N802
        return self.flatpak

    @pyqtProperty(QObject, constant=True)
    def Repos(self):  # noqa: N802
        return self.repos

    @pyqtProperty(QObject, constant=True)
    def History(self):  # noqa: N802
        return self.history

    @pyqtProperty(QObject, constant=True)
    def System(self):  # noqa: N802
        return self.system

    @pyqtProperty(QObject, constant=True)
    def Settings(self):  # noqa: N802
        return self.settings_controller

    @pyqtProperty(str, constant=True)
    def version(self) -> str:
        return __version__

    # ── layout ─────────────────────────────────────────────────

    @pyqtProperty(int, constant=True)
    def listColumnWidth(self) -> int:
        """The list column's width beside a details column (0 = default)."""
        return self.settings.list_column_width

    @pyqtSlot(int)
    def saveListColumnWidth(self, width: int) -> None:
        if width > 0:
            self.settings.list_column_width = width

    # ── icons ──────────────────────────────────────────────────

    @pyqtProperty("QVariantList", constant=True)
    def iconNames(self) -> list:
        return self.icons.names()

    @pyqtSlot(QColor, result=str)
    def iconBaseFor(self, color: QColor) -> str:
        """Directory URL of the app's icons drawn in ``color``."""
        return self.icons.base_url(color.name())

    def _load_app_icons(self) -> None:
        worker = AppIconsWorker(parent=self)
        worker.finished.connect(self._on_app_icons)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _on_app_icons(self, icons) -> None:
        self._app_icons = dict(icons or {})
        self._set(appIconsReady=True)

    @pyqtSlot(str, result="QVariantMap")
    def appIcon(self, package: str) -> dict:
        """``{"theme": name, "file": path}`` for a package that is an app,
        else an empty map (QML then shows a letter tile)."""
        return dict(self._app_icons.get(package, {}))

    @pyqtSlot(str, result=bool)
    def themeIconExists(self, name: str) -> bool:
        """Whether the icon theme has ``name`` (an app or Flatpak id), so
        QML can show the letter tile instead of an empty space."""
        if name not in self._theme_icons:
            self._theme_icons[name] = bool(name) and QIcon.hasThemeIcon(name)
        return self._theme_icons[name]

    # ── window ─────────────────────────────────────────────────

    def set_window(self, window) -> None:
        """The root QQuickWindow (activation, focus, close-to-background)."""
        self._window = window

    def set_instance_server(self, server) -> None:
        self._instance_server = server

    def _window_active(self) -> bool:
        window = self._window
        return bool(window is not None and window.isVisible() and window.isActive())

    def _show_window(self) -> None:
        window = self._window
        if window is None:
            return
        from PyQt6.QtCore import Qt
        if window.windowStates() & Qt.WindowState.WindowMinimized:
            window.showNormal()
        window.show()
        window.raise_()
        window.requestActivate()

    def _show_for_prompt(self) -> None:
        """A prompt needs an answer: the window must be visible to give one."""
        window = self._window
        if window is not None and not window.isVisible():
            if self._quit_when_done:
                self._quit_when_done = False
                self._set_quit_on_close(True)
            self._show_window()

    @staticmethod
    def _set_quit_on_close(enabled: bool) -> None:
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None:
            app.setQuitOnLastWindowClosed(enabled)

    @pyqtSlot(result=bool)
    def requestClose(self) -> bool:
        """Window close: True lets it close; False keeps the app running.

        Closing during an operation only hides the window: dnf writes to a
        pipe this process reads, so exiting would kill it mid-transaction
        (SIGPIPE). The app quits once the operation is done.
        """
        if not (self.runner.running() or self.runner.queue):
            self._shutdown()
            return True
        if self._closing_prompt:
            return False  # already asking

        def hide() -> None:
            self._closing_prompt = False
            if not (self.runner.running() or self.runner.queue):
                # It finished while the question was open: just quit.
                self._quit_now()
                return
            self._quit_when_done = True
            self._set_quit_on_close(False)
            if self._window is not None:
                self._window.hide()

        def keep() -> None:
            self._closing_prompt = False
        self._closing_prompt = True
        self.prompts.confirm(
            "Operation Still Running",
            "A package operation is still running. If you close the window, it "
            "keeps running in the background and you'll get a notification "
            "when it finishes.",
            hide, on_no=keep, confirm_label="Close Window", cancel_label="Keep Open")
        return False

    def _quit_now(self) -> None:
        from PyQt6.QtWidgets import QApplication

        def quit_app() -> None:
            self._shutdown()
            QApplication.quit()
        QTimer.singleShot(0, quit_app)

    def _shutdown(self) -> None:
        for timer in self._startup_timers:
            timer.stop()
        self._reminder_timer.stop()
        self.prompts.cancel_all(run_callbacks=False)
        self.shutdown_threads()
        self.icons.cleanup()

    def shutdown_threads(self, timeout_ms: int = 2000) -> list:
        """Wait briefly for worker threads; detach any still running.

        The caller must then exit with ``os._exit`` when this returns
        threads: letting Python finalize a running QThread aborts.
        """
        deadline = time.monotonic() + timeout_ms / 1000
        for thread in self.findChildren(QThread):
            remaining = int((deadline - time.monotonic()) * 1000)
            if thread.isRunning() and remaining > 0:
                thread.wait(remaining)
        still_running = [t for t in self.findChildren(QThread) if t.isRunning()]
        for thread in still_running:
            thread.setParent(None)
        # Keep earlier ones too: a second call no longer finds them as
        # children, and the caller's os._exit guard depends on this list.
        self.detached_threads.extend(t for t in still_running
                                     if t not in self.detached_threads)
        return list(self.detached_threads)

    def _operation_finished(self, failed: bool) -> None:
        """After a closed window's operation ends: quit, or reopen the
        window with the output open when it failed."""
        if not self._quit_when_done:
            return
        self._quit_when_done = False
        if failed:
            self._set_quit_on_close(True)
            self.activate(ACTIVITY)
            return

        self._quit_now()

    # ── navigation ─────────────────────────────────────────────

    @pyqtSlot(str)
    def navigate(self, page: str) -> None:
        if page == ACTIVITY:
            self.toggleActivity(True)
            return
        if page not in PAGES:
            return
        if page == self._state["currentPage"]:
            return
        self._set(currentPage=page)
        self.refreshCurrent(revisit=True)

    @pyqtSlot(int)
    def navigateIndex(self, index: int) -> None:
        """Ctrl+1..9 (v1's order)."""
        if 0 <= index < len(PAGES):
            page = PAGES[index]
            if page == ACTIVITY:
                self.toggleActivity(not self._state["activityExpanded"])
            else:
                self.navigate(page)

    @pyqtSlot(str, str)
    def activate(self, page: str = "", token: str = "") -> None:
        """Bring the window forward (notification click, second launch) and
        show ``page`` if given."""
        try:
            if token:
                # Qt hands this to the compositor on requestActivate(), so
                # Wayland lets the window take focus.
                os.environ["XDG_ACTIVATION_TOKEN"] = token
            if page == "updates" and not self.runner.running():
                self.updates.invalidate()  # the click is newer than the last scan
            if page == ACTIVITY:
                self.toggleActivity(True)
            elif page in PAGES:
                if self._state["currentPage"] == page:
                    self.refreshCurrent()
                else:
                    self.navigate(page)
            if self._quit_when_done:  # reopened while finishing in the background
                self._quit_when_done = False
                self._set_quit_on_close(True)
            self._show_window()
        except Exception:
            import traceback
            traceback.print_exc()

    @pyqtSlot()
    def refreshCurrent(self, revisit: bool = False) -> None:
        """Load the current page (Ctrl+R forces a fresh update scan)."""
        page = self._state["currentPage"]
        try:
            if page == "updates":
                if revisit:
                    self.updates.show()
                else:
                    self.updates.invalidate()
                    self.updates.show()
            elif page == "installed":
                self.packages.show() if revisit else self.packages.refresh()
            elif page == "flatpak":
                self.flatpak.show() if revisit else self.flatpak.refresh()
            elif page in ("sysinfo", "tools"):
                self.system.show()
            elif page == "repos":
                self.repos.show() if revisit else self.repos.refresh()
            elif page == "history":
                self.history.show() if revisit else self.history.refresh()
            elif page == "settings":
                self.settings_controller.show()
        except Exception:
            import traceback
            traceback.print_exc()

    @pyqtSlot()
    def focusSearch(self) -> None:
        self.focusSearchRequested.emit()

    @pyqtSlot()
    def runFavoriteUpdate(self) -> None:
        """Ctrl+U: run the favorite update mode from any page."""
        self.navigate("updates")
        self.updates.runFavorite()

    # ── activity panel ─────────────────────────────────────────

    @pyqtSlot(bool)
    def toggleActivity(self, expanded: bool) -> None:
        self._set(activityExpanded=bool(expanded),
                  activityVisible=self._state["activityVisible"] or bool(expanded))

    @pyqtSlot()
    def closeActivity(self) -> None:
        if not self.runner.busy:
            self._set(activityVisible=False, activityExpanded=False)

    def _sync_activity(self) -> None:
        if self.runner.busy and not self._state["activityVisible"]:
            self._set(activityVisible=True)

    # ── errors ─────────────────────────────────────────────────

    def _live_passwordless(self) -> tuple[str, bool]:
        """(scope of the rule actually installed, does it cover the current
        major-package list), checked with ``sudo -n -l`` at most once a minute."""
        now = time.monotonic()
        cached = getattr(self, "_pw_cache", None)
        if cached and now - cached[0] < 60:
            return cached[1]
        from dnf_gui.core import passwordless as pw
        try:
            live, _legacy, covered = pw.live_status(self.settings.held_back_patterns)
        except Exception:
            live, covered = "off", False
        self._pw_cache = (now, (live, covered))
        return live, covered

    def forget_passwordless_status(self) -> None:
        """The rule or the major-package list changed: check again next time."""
        self._pw_cache = None

    def password_note(self, cmd: list[str]) -> str:
        """What the confirmation should say about a password for ``cmd``:
        "no password" only when the rule installed right now covers it."""
        from dnf_gui.core.passwordless import maybe_passwordless
        if cmd and cmd[0] == "pkexec":
            live, covered = self._live_passwordless()
            excluded = any(a.startswith("--exclude=") for a in cmd)
            if maybe_passwordless(cmd, live) != cmd and (covered or not excluded):
                return "No password needed: your passwordless updates rule covers this."
        return "You'll be asked for your password."

    def show_error(self, title: str, text: str) -> None:
        self.prompts.inform(title, text, level=ERROR)

    def report_exception(self, text: str) -> None:
        """Unexpected exception in a slot: tell the user instead of aborting."""
        self.errorRaised.emit(text)

    @pyqtSlot(str)
    def copyText(self, text: str) -> None:
        from PyQt6.QtGui import QGuiApplication
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)
            self.prompts.toast(f"Copied {text}")

    def set_update_badge(self, count: int) -> None:
        self._set(updateBadge=max(0, int(count)))

    # ── after an operation ─────────────────────────────────────

    def _on_operation_finished(self, exit_code: int, operation: str,
                               chain_failed: bool) -> None:
        if chain_failed:
            self._on_chain_failed(exit_code, operation)
            return
        output = "\n".join(self.runner.output)
        upgrade_ok = exit_code == 0 and operation in UPGRADE_OPERATIONS
        skipped = parse_blocked_updates(output) if upgrade_ok else None
        unavailable = parse_unavailable_updates(output) if upgrade_ok and not skipped else []
        not_installed = len(skipped.packages) if skipped else len(unavailable)
        self._notify_if_unfocused(
            exit_code, operation,
            f"{not_installed} update(s) couldn't be installed yet." if not_installed else "")
        if exit_code == 0:
            if skipped:
                self._report_skipped(skipped, operation)
            elif unavailable:
                self._report_unavailable(unavailable)
            if operation == "Forced Security Upgrade" and self.forced_removals:
                names = " ".join(self.forced_removals)
                self.runner.append(
                    f"\nRemoved to make room: {', '.join(self.forced_removals)}. "
                    "Reinstall once a matching update is published:\n"
                    f"  sudo dnf install {names}")
                self.forced_removals = []
            if operation == "Installing app update":
                self.runner.append("\n✅ Update installed.")
                self._offer_relaunch()
            elif operation == "Enabling passwordless updates":
                self.settings.passwordless_scope = (
                    self.settings_controller.pending_passwordless_scope)
            elif operation == "Disabling passwordless updates":
                self.settings.passwordless_scope = "off"
        elif operation == "Enabling passwordless updates":
            self.settings.passwordless_scope = "off"
        if exit_code != 0 and exit_code not in CANCELLED_EXIT_CODES:
            self.toggleActivity(True)  # show what went wrong

        self._invalidate_lists()
        if exit_code == 0:
            self.updates.invalidate()  # system changed: next visit rescans
        if operation in ("Enabling passwordless updates",
                         "Disabling passwordless updates"):
            self.forget_passwordless_status()
            self.settings_controller.load_passwordless_status()
        if operation in ("Disabling Discover system-wide",
                         "Re-enabling Discover system-wide",
                         "Cancelling Discover's restart update"):
            self.settings_controller.load_discover_status()
        target = self.pending_release_target
        if exit_code == 0 and target and operation == self.updates.release_operation(target):
            self.pending_release_target = None
            self.updates.on_release_downloaded(target)
        elif exit_code == 0 and operation == "Cancelling Fedora upgrade":
            self.updates.set_release_upgrade(None)
        if exit_code == 0 and operation in UPGRADE_OPERATIONS:
            self.updates.recheck_reboot()
            self.notifier.close(self._reminder_notification_id)  # out of date now
            self._reminder_notification_id = 0
        if operation == "Removing plasma-discover-notifier":
            self.settings_controller.load_discover_status()
        if exit_code == 0 and not self._quit_when_done and operation != "Installing app update":
            # Show the new state where the user is looking.
            page = self._state["currentPage"]
            if page in ("updates", "installed", "flatpak", "repos", "history",
                        "tools", "sysinfo"):
                self.refreshCurrent(revisit=True)
            self.packages.reload_details()
        self._operation_finished(
            failed=exit_code != 0 and exit_code not in CANCELLED_EXIT_CODES)

    def _on_chain_failed(self, exit_code: int, operation: str) -> None:
        self._notify_if_unfocused(exit_code, operation)
        target = self.pending_release_target
        if (target and operation == self.updates.release_operation(target)
                and exit_code not in CANCELLED_EXIT_CODES
                and self.runner.failed_steps_left == 0):
            # The download (last step) failed, not the regular update.
            QTimer.singleShot(0,
                              lambda: self.updates.on_release_download_failed(target))
        if exit_code not in CANCELLED_EXIT_CODES:
            self.toggleActivity(True)
        self._invalidate_lists()
        self._operation_finished(failed=exit_code not in CANCELLED_EXIT_CODES)

    def _invalidate_lists(self) -> None:
        self.packages.invalidate()
        self.flatpak.invalidate()
        self.repos.invalidate()
        self.history.invalidate()

    def _report_skipped(self, skipped, operation: str) -> None:
        """dnf exits 0 when it skips blocked updates; say so plainly."""
        count = len(skipped.packages)
        self.runner.set_result_text(
            f"Completed · {count} Update{'s' if count != 1 else ''} Skipped")
        lines = [f"\n⚠ {count} update{'s' if count != 1 else ''} couldn't be "
                 f"installed: {', '.join(skipped.packages)}",
                 f"  {skipped.explanation()}"]
        if operation == "Security Upgrade":
            lines.append("  Running Security Only again won't install it until "
                         "then. To install it now anyway, use Force Install on "
                         "the Updates page.")
        self.runner.append("\n".join(lines))

    def _report_unavailable(self, names: list[str]) -> None:
        """Updates whose repository published them before their dependencies."""
        count = len(names)
        self.runner.set_result_text(
            f"Completed · {count} Update{'s' if count != 1 else ''} Skipped")
        self.runner.append(
            f"\n⚠ {count} update{'s' if count != 1 else ''} couldn't be installed: "
            f"{', '.join(names)}\n  Their repository published them before "
            "something they need. This usually clears up within a few days; "
            "they install with your next update once it does.")

    def _notify_if_unfocused(self, exit_code: int, operation: str,
                             note: str = "") -> None:
        """Desktop notification for operations that finish while you're away.

        Clicking it brings the window back; a failure or skipped updates
        open the output.
        """
        if self._window_active():
            return
        if exit_code == 0 and not note:
            notification = Notification(title=operation, body="Finished successfully.")
        elif exit_code == 0:
            notification = Notification(
                title=operation, body=f"Finished. {note}", page=ACTIVITY,
                icon="dialog-warning", actions=[(ACTIVITY, "Show Details")])
        elif exit_code in CANCELLED_EXIT_CODES:
            notification = Notification(title=operation, body="Cancelled.")
        else:
            notification = Notification(
                title=operation,
                body=f"Failed (exit code {exit_code}). The output shows what went wrong.",
                icon="dialog-error", page=ACTIVITY,
                actions=[(ACTIVITY, "Show Output")])
        if self._quit_when_done and (exit_code == 0
                                     or exit_code in CANCELLED_EXIT_CODES):
            # The window was closed and the app quits now: nothing to open.
            notification.clickable = False
        self.notifier.send(notification)

    # ── reboot ─────────────────────────────────────────────────

    def reboot_now(self) -> None:
        try:
            result = subprocess.run(["systemctl", "reboot"], capture_output=True,
                                    text=True, timeout=15)
            if result.returncode != 0:
                self.show_error(
                    "Restart Failed",
                    "Could not restart:\n\n"
                    f"{(result.stderr or result.stdout).strip() or 'unknown error'}"
                    "\n\nTry restarting from the application menu.")
        except FileNotFoundError:
            self.show_error("Restart Failed", "systemctl not found on this system.")
        except Exception as e:
            self.show_error("Restart Failed", str(e))

    # ── reminders ──────────────────────────────────────────────

    def _refresh_background_checker(self) -> None:
        """Keep the background checker in step with the reminder switch."""
        try:
            enabled = self.settings.reminders_enabled
            interval = self.settings.check_interval_hours
            if enabled and AppSettings.checker_needs_refresh(interval):
                AppSettings.set_checker_installed(True, interval)
            elif not enabled and AppSettings.is_checker_installed():
                AppSettings.set_checker_installed(False)
        except Exception:
            pass

    def _maybe_background_reminder(self) -> None:
        """Hourly in-app check; only notifies when due and something waits."""
        try:
            if not self.settings.is_check_due():
                return
            if self._reminder_worker is not None and self._reminder_worker.isRunning():
                return
            worker = ReminderCheckWorker(parent=self)
            worker.finished.connect(self._on_reminder_checked)
            worker.error.connect(lambda _e: None)
            self._reminder_worker = worker
            worker.start()
        except Exception:
            pass

    def _on_reminder_checked(self, result) -> None:
        try:
            if not result.should_notify:
                return
            self.notifier.close(self._reminder_notification_id)
            nid = self.notifier.send(reminder_notification(result))
            self._reminder_notification_id = max(nid, 0)
            if not nid:
                self.set_update_badge(result.total)
        except Exception:
            pass

    # ── the app's own updates ──────────────────────────────────

    @pyqtSlot()
    def checkAppUpdate(self) -> None:
        """Settings → Check for App Updates (says so when there's none)."""
        self._check_app_update(manual=True)

    def _check_app_update(self, manual: bool = False) -> None:
        worker = AppUpdateWorker(__version__, parent=self)
        worker.finished.connect(self._on_app_update_checked)
        if manual:
            worker.finished.connect(
                lambda info: None if info is not None else self.prompts.toast(
                    f"No newer version found (you have {__version__}). "
                    "If you're offline, try again later."))
        self._app_update_worker = worker  # keep a ref (QThread GC safety)
        worker.start()

    def _on_app_update_checked(self, update_info) -> None:
        # Don't deleteLater() the worker here: this slot runs while its run()
        # is still returning, and deleting a running QThread aborts.
        if update_info is None:
            return
        self._pending_update_info = update_info
        self._set(appUpdate={
            "available": True, "version": update_info.latest_version,
            # Only with a digest to check it against (the download refuses
            # without one).
            "canInstall": bool(update_info.download_url
                               and getattr(update_info, "sha256", "")),
            "notes": update_info.release_notes or "",
            "url": update_info.release_url or RELEASES_URL})

    @pyqtSlot()
    def openWebsite(self) -> None:
        """Greg.Tech, who makes the app (the sidebar and About credit)."""
        if not QDesktopServices.openUrl(QUrl(WEBSITE_URL)):
            self.prompts.inform(
                "Open Website",
                f"Your web browser couldn't be opened. The website is:\n\n{WEBSITE_URL}")

    @pyqtSlot()
    def openReleases(self) -> None:
        info = self._pending_update_info
        url = (info.release_url if info else "") or RELEASES_URL
        qurl = QUrl(url)
        if not qurl.isValid() or not QDesktopServices.openUrl(qurl):
            self.prompts.inform(
                "Open Releases Page",
                f"Your web browser couldn't be opened. The releases page is:\n\n{url}")

    @pyqtSlot()
    def dismissAppUpdate(self) -> None:
        info = dict(self._state["appUpdate"])
        if info:
            info["dismissed"] = True
            self._set(appUpdate=info)

    @pyqtSlot()
    def installAppUpdate(self) -> None:
        """Download the release RPM, check its digest, and dnf install it."""
        info = self._pending_update_info
        if info is None or not info.download_url or self.runner.check_busy():
            return
        self.prompts.confirm(
            f"Install Version {info.latest_version}?",
            f"Download DNF Package Manager {info.latest_version} from GitHub, check "
            "it against the digest GitHub published, and install it with dnf. "
            f"You have version {__version__}.",
            self._start_app_update_download, confirm_label="Install Update")

    def _start_app_update_download(self) -> None:
        info = self._pending_update_info
        if info is None or self.runner.check_busy():
            return
        self.toggleActivity(True)
        worker = AppUpdateDownloadWorker(
            info.download_url, getattr(info, "sha256", ""), parent=self)
        self.runner.start_external("Downloading app update", worker)
        worker.finished.connect(self._on_update_downloaded)
        worker.error.connect(self._on_update_download_error)
        worker.progress.connect(self.runner.append)
        self._download_worker = worker
        worker.start()

    def _on_update_downloaded(self, rpm_path: str) -> None:
        from dnf_gui.core.updater import build_verified_install_command
        info = self._pending_update_info
        self.runner.finish_external(True, "Downloaded")
        self.runner.append(f"Downloaded to {rpm_path}\nInstalling with DNF...\n")
        self.runner.run(
            build_verified_install_command(rpm_path, getattr(info, "sha256", ""),
                                           self.backend.dnf_path),
            "Installing app update")

    def _on_update_download_error(self, error: str) -> None:
        self.runner.finish_external(False, "Download Failed")
        self.runner.append(f"\n❌ Download failed: {error}")
        self.show_error(
            "Update Failed",
            f"Could not download the update:\n\n{error}\n\n"
            "Try opening the Releases page to download it yourself.")

    def _offer_relaunch(self) -> None:
        self._set(appUpdate={})
        self.prompts.confirm(
            "Update Installed",
            "The new version is installed. Restart the app now to use it?",
            self.relaunch, confirm_label="Restart App", cancel_label="Later")

    @staticmethod
    def _launcher() -> list[str]:
        """The installed launcher, else this interpreter on this package."""
        if os.access("/usr/bin/dnf-gui", os.X_OK):
            return ["/usr/bin/dnf-gui"]
        return [sys.executable, "-P", "-m", "dnf_gui"]

    def relaunch(self) -> None:
        """Replace this process with the newly installed version.

        Tears nothing down until it knows the exec will happen: when a
        worker won't stop in time, the user restarts it, and the running
        app keeps working meanwhile.
        """
        busy = [t for t in self.findChildren(QThread) if t.isRunning()]
        deadline = time.monotonic() + 3  # one wait for all, not per thread
        for thread in busy:
            thread.wait(max(0, int((deadline - time.monotonic()) * 1000)))
        if self.runner.running() or any(t.isRunning() for t in busy):
            self.prompts.inform(
                "Restart the App Yourself",
                "Something is still running, so the app can't restart right now. "
                "Close it and open it again to use the new version.")
            return
        argv = self._launcher()
        self._shutdown()
        if self._instance_server is not None:
            self._instance_server.close()
        sys.stdout.flush()
        sys.stderr.flush()
        os.execv(argv[0], argv)
