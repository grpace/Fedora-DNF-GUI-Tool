"""Settings page: major-update patterns, reminders, passwordless updates,
the Discover takeover, and About (version and app updates)."""

from __future__ import annotations

import subprocess

from PyQt6.QtCore import pyqtSignal, pyqtSlot

from dnf_gui.core.app_settings import AppSettings
from dnf_gui.core.notifications import Notification
from dnf_gui.core.worker import DiscoverStatusWorker
from dnf_gui.ui.controllers.base import StateObject, state_property

SCOPE_LABELS = {"updates": "Updates Only", "full": "All DNF Operations"}
INTERVALS = [{"hours": 12, "label": "Every 12 Hours"}, {"hours": 24, "label": "Daily"},
             {"hours": 72, "label": "Every 3 Days"}, {"hours": 168, "label": "Weekly"}]


class SettingsController(StateObject):
    changed = pyqtSignal()
    _defaults = {
        # Update Without Major
        "heldBack": "", "heldBackMessage": "",
        # Reminders
        "remindersEnabled": False, "securityOnly": False, "notifyFlatpak": True,
        "intervalHours": 24, "intervals": INTERVALS, "lastCheck": "",
        "checkerInstalled": False,
        # Passwordless
        "passwordlessScope": "off", "passwordlessLive": "off",
        "passwordlessTitle": "", "passwordlessText": "", "passwordlessLevel": "info",
        "passwordlessNotes": [],
        # Discover
        "discoverLoading": False, "discoverLevel": "info", "discoverTitle": "",
        "discoverText": "", "discoverInstalled": True, "discoverActive": False,
        "discoverScheduled": False,
    }
    for _name, _type in (
            ("heldBack", str), ("heldBackMessage", str),
            ("remindersEnabled", bool), ("securityOnly", bool), ("notifyFlatpak", bool),
            ("intervalHours", int), ("intervals", "QVariantList"), ("lastCheck", str),
            ("checkerInstalled", bool),
            ("passwordlessScope", str), ("passwordlessLive", str),
            ("passwordlessTitle", str), ("passwordlessText", str),
            ("passwordlessLevel", str), ("passwordlessNotes", "QVariantList"),
            ("discoverLoading", bool), ("discoverLevel", str), ("discoverTitle", str),
            ("discoverText", str), ("discoverInstalled", bool),
            ("discoverActive", bool), ("discoverScheduled", bool)):
        locals()[_name] = state_property(_type, _name, changed)
    del _name, _type

    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self._hold_notice_shown = False
        self.pending_passwordless_scope = "updates"

    def show(self) -> None:
        settings = self.app.settings
        last = settings.get_last_check()
        self._set(
            heldBack=", ".join(settings.held_back_patterns),
            heldBackMessage=f"{len(settings.held_back_patterns)} pattern(s) count as major.",
            remindersEnabled=settings.reminders_enabled,
            securityOnly=settings.security_only,
            notifyFlatpak=settings.notify_flatpak,
            intervalHours=settings.check_interval_hours,
            lastCheck=last.strftime("%B %-d, %Y at %-I:%M %p") if last else "",
            checkerInstalled=AppSettings.is_checker_installed())
        self.load_discover_status()
        self.load_passwordless_status()

    # ── Update Without Major ───────────────────────────────────

    @pyqtSlot(str)
    def saveHeldBack(self, text: str) -> None:
        from dnf_gui.core.dnf_backend import (
            DEFAULT_HELD_BACK_PATTERNS, parse_held_back_patterns,
        )
        valid, invalid = parse_held_back_patterns(text)
        if invalid:
            self.app.prompts.inform(
                "Invalid Patterns",
                "These aren't valid package-name globs and were not saved:\n\n"
                + ", ".join(invalid)
                + "\n\nUse letters, digits and . _ + - * ? [ ] only.",
                level="warning")
            return
        if not valid:
            valid = list(DEFAULT_HELD_BACK_PATTERNS)
            message = "Reset to the defaults."
        else:
            message = f"Saved. {len(valid)} pattern(s) count as major."
        changed = valid != self.app.settings.held_back_patterns
        self.app.settings.held_back_patterns = valid
        self.app.updates.set_held_back_patterns(valid)
        if changed and self.app.settings.passwordless_scope == "updates":
            message += (" Passwordless Updates Only lists the exact command, so "
                        "choose Turn On again to cover the new list.")
        self._set(heldBack=", ".join(valid), heldBackMessage=message)
        if changed:
            self.load_passwordless_status()

    @pyqtSlot()
    def resetHeldBack(self) -> None:
        self.saveHeldBack("")

    def toggle_hold(self, name: str, hold: bool) -> None:
        """Per-row Treat as Major from the Updates page."""
        patterns = self.app.settings.held_back_patterns
        if hold and name not in patterns:
            patterns.append(name)
        elif not hold and name in patterns:
            patterns.remove(name)
        else:
            return
        self.app.settings.held_back_patterns = patterns
        self.app.updates.set_held_back_patterns(patterns)
        self._set(heldBack=", ".join(patterns),
                  heldBackMessage=f"Marked {name} as major." if hold
                  else f"{name} no longer counts as major.")
        self.app.prompts.toast(f"{name} now counts as major" if hold
                               else f"{name} no longer counts as major")
        if (self.app.settings.passwordless_scope == "updates"
                and not self._hold_notice_shown):
            self._hold_notice_shown = True
            self.app.prompts.inform(
                "Major Packages Changed",
                "Passwordless Updates Only lists the exact Update Without Major "
                "command, so it asks for your password until you choose Turn On "
                "again under Settings → Passwordless Updates.")

    # ── Reminders ──────────────────────────────────────────────

    @pyqtSlot(bool, bool, bool, int)
    def saveReminders(self, enabled: bool, security_only: bool,
                      notify_flatpak: bool, interval_hours: int) -> None:
        settings = self.app.settings
        settings.reminders_enabled = bool(enabled)
        settings.security_only = bool(security_only)
        settings.notify_flatpak = bool(notify_flatpak)
        if interval_hours in {i["hours"] for i in INTERVALS}:
            settings.check_interval_hours = int(interval_hours)
        try:
            scheduled = AppSettings.set_checker_installed(
                bool(enabled), settings.check_interval_hours)
        except Exception:
            scheduled = False
        if not enabled:
            self.app.prompts.toast("Reminders are off")
        elif scheduled:
            self.app.prompts.toast("Reminders saved. Background checks are on.")
        else:
            self.app.prompts.inform(
                "Reminders Saved",
                "The background timer couldn't be set up (no systemd user "
                "session), so updates are only checked at login and while this "
                "app is open.", level="warning")
        self.show()

    @pyqtSlot()
    def testReminder(self) -> None:
        settings = self.app.settings
        targets = ["security updates" if settings.security_only else "system updates"]
        if settings.notify_flatpak:
            targets.append("Flatpak updates")
        notification = Notification(
            title="Test Reminder",
            body=f"Reminders are working. You'll hear about {' and '.join(targets)}. "
                 "Click this to open the Updates page.",
            page="updates", actions=[("updates", "View Updates")])
        sent = self.app.notifier.send(notification)
        if sent > 0:
            self.app.prompts.inform(
                "Test Sent",
                "A test reminder was sent. Click it (or its View Updates button) "
                "to check that it opens the Updates page.")
        elif sent:
            self.app.prompts.inform(
                "Test Sent",
                "A test reminder was sent with notify-send. The desktop's "
                "notification service couldn't be reached directly, so clicking "
                "reminders won't open the app.")
        else:
            self.app.prompts.inform(
                "Test Not Delivered",
                "No notification service answered, so reminders can't be shown. "
                "Updates are still counted on the Updates page.", level="warning")

    # ── Passwordless updates ───────────────────────────────────

    def load_passwordless_status(self) -> None:
        from dnf_gui.core import passwordless as pw
        try:
            live, legacy, covered = pw.live_status(self.app.settings.held_back_patterns)
        except Exception:
            live, legacy, covered = "off", False, True
        remembered = self.app.settings.passwordless_scope
        label = SCOPE_LABELS.get
        if live == "off" and remembered == "off":
            level, title = "info", "Off"
            text = "Every privileged step asks for your password."
        elif live == remembered:
            level, title = "positive", f"On: {label(live, live)}"
            text = "Verified. Updates run without a password prompt."
        elif live == "off":
            level, title = "warning", "Not Working"
            text = (f"Set to {label(remembered, remembered)}, but the system rule "
                    "is missing. Turn it on again to reinstall it.")
        else:
            level, title = "warning", f"On: {label(live, live)}"
            text = f"Your setting is {label(remembered, remembered)}."
        notes = []
        if not covered:
            notes.append("Update Without Major still asks for a password: your "
                         "list of major packages changed after the rule was "
                         "installed. Turn it on again to update it.")
        if legacy:
            notes.append("Your rule uses an older, overly broad format that could "
                         "let other programs gain root. Turn it on again to "
                         "replace it with the exact-command rule.")
        if notes and level == "positive":
            level = "warning"
        self._set(passwordlessScope=remembered, passwordlessLive=live,
                  passwordlessTitle=title, passwordlessText=text,
                  passwordlessLevel=level, passwordlessNotes=notes)

    @pyqtSlot(str)
    def enablePasswordless(self, scope: str) -> None:
        from dnf_gui.core import passwordless as pw
        if scope not in ("updates", "full"):
            scope = "updates"
        user = pw.current_user()
        if not user:
            self.app.prompts.inform(
                "Can't Turn On Passwordless Updates",
                "Could not determine your login name, so a per-user rule can't "
                "be written safely.", level="error")
            return
        if scope == "full":
            title = "Passwordless for All DNF Operations?"
            text = ("This removes every password prompt, including installs, "
                    "removals and repo changes. Any program running as you could "
                    "then change system packages without asking.\n\n"
                    "Only do this on a single-user desktop where you accept the "
                    "tradeoff. Updates Only is the safer choice.\n\n"
                    "You'll authenticate once now to install the rule.")
            destructive = True
        else:
            title = "Turn On Passwordless Updates?"
            text = ("• Upgrade All, Security Only and Update Without Major run "
                    "without a password\n"
                    "• Installs, removals, repo changes and firmware updates still "
                    "ask\n\n"
                    "Installs a validated per-user sudoers file "
                    "(/etc/sudoers.d/90-dnf-gui). You'll authenticate once now.")
            destructive = False

        def go() -> None:
            content = pw.build_rule_content(
                user, scope, self.app.settings.held_back_patterns)
            ok, validation_msg = pw.validate_content(content)
            if not ok:
                self.app.prompts.inform(
                    "Validation Failed",
                    "The generated rule did not pass visudo -c, so nothing was "
                    f"changed:\n\n{validation_msg}", level="error")
                return
            previous = self.pending_passwordless_scope
            self.pending_passwordless_scope = scope
            if not self.app.runner.run(pw.build_install_commands(content),
                                       "Enabling passwordless updates"):
                self.pending_passwordless_scope = previous  # busy: nothing ran
        self.app.prompts.confirm(title, text, go, confirm_label="Turn On",
                                 destructive=destructive)

    @pyqtSlot()
    def disablePasswordless(self) -> None:
        from dnf_gui.core import passwordless as pw

        def go() -> None:
            previous = self.pending_passwordless_scope
            self.pending_passwordless_scope = "off"
            if not self.app.runner.run(pw.build_remove_commands(),
                                       "Disabling passwordless updates"):
                self.pending_passwordless_scope = previous
        self.app.prompts.confirm(
            "Restore Password Prompts?",
            "Remove the sudoers rule so every privileged step asks for your "
            "password again?", go, confirm_label="Restore Prompts")

    # ── Discover ───────────────────────────────────────────────

    @pyqtSlot()
    def load_discover_status(self) -> None:
        self._set(discoverLoading=True)
        worker = DiscoverStatusWorker(parent=self)
        worker.finished.connect(self._on_discover_status)
        worker.error.connect(lambda e: self._set(discoverLoading=False))
        self._discover_worker = worker
        worker.start()

    refreshDiscover = load_discover_status

    def _on_discover_status(self, status) -> None:
        nothing_to_do = (not status.discover_installed
                         and not status.system_autostart_present)
        active = bool(status.per_user_disabled or status.system_disabled)
        scheduled = bool(status.restart_update_scheduled)
        extras = []
        if status.notifier_running:
            extras.append("Its background checker is running right now.")
        if scheduled:
            extras.append("It has updates scheduled to install at your next restart.")
        extra = (" " + " ".join(extras)) if extras else ""
        if nothing_to_do:
            level, title, text = "info", "Discover Isn't Installed", "Nothing to turn off."
        elif active and scheduled:
            level, title = "warning", "Discover Still Has an Update Scheduled"
            text = ("Its checks are off, but it will install updates at your next "
                    "restart. Cancel it and update from this app instead.")
        elif active:
            level, title = "positive", "This App Handles Updates"
            text = "Discover's automatic checks are off." + extra
        else:
            level, title = "warning", "Discover Is Checking for Updates Too"
            text = "You may see double notifications." + extra
        self._set(discoverLoading=False, discoverLevel=level, discoverTitle=title,
                  discoverText=text, discoverInstalled=not nothing_to_do,
                  discoverActive=active, discoverScheduled=scheduled)

    @pyqtSlot()
    def takeOver(self) -> None:
        manager = self.app.discover_manager

        def apply(cancel_scheduled: bool) -> None:
            try:
                manager.set_per_user_enabled(False)
            except Exception as e:
                self.app.prompts.inform("Takeover Failed", str(e), level="error")
                return
            try:  # best effort: stop the running notifier
                subprocess.run(manager.build_kill_notifier_command(), timeout=5)
            except Exception:
                pass
            self.app.prompts.inform(
                "This App Handles Updates",
                "Discover no longer checks or notifies for your user. Use the "
                "Updates page and reminders in this app instead. You can restore "
                "Discover anytime from Settings.")
            if cancel_scheduled:
                self.app.runner.run(manager.build_cancel_restart_update_command(),
                                    "Cancelling Discover's restart update")
            self.load_discover_status()

        def confirmed() -> None:
            if manager.restart_update_scheduled():
                self.app.prompts.confirm(
                    "Cancel Discover's Scheduled Update?",
                    "Discover has already scheduled updates to install at your "
                    "next restart. Cancel that too, so updates come from this "
                    "app instead?\n\nRecommended: otherwise PackageKit installs "
                    "its own, possibly out-of-date, update set during the restart.",
                    lambda: apply(True), on_no=lambda: apply(False),
                    confirm_label="Cancel It", cancel_label="Keep It")
            else:
                apply(False)

        self.app.prompts.confirm(
            "Use This App for Updates?",
            "Turn off Discover's automatic update checks for your user?\n\n"
            "• Stops Discover's background checker (no password needed, reversible)\n"
            "• Silences Discover popups and restart-time updates\n"
            "• DNF Package Manager becomes your updater\n\n"
            "Discover itself stays installed, and you can still open it.",
            confirmed, confirm_label="Use This App")

    @pyqtSlot()
    def restoreDiscover(self) -> None:
        try:
            self.app.discover_manager.set_per_user_enabled(True)
        except Exception as e:
            self.app.prompts.inform("Restore Failed", str(e), level="error")
            return
        self.app.prompts.toast("Discover's update checks are back on for you")
        self.load_discover_status()

    @pyqtSlot()
    def cancelRestartUpdate(self) -> None:
        manager = self.app.discover_manager
        self.app.prompts.confirm(
            "Cancel Restart Update?",
            "Discover scheduled system updates to install at your next restart. "
            "Cancel them? Nothing is uninstalled; install updates from the "
            "Updates page instead.\n\nRuns: pkcon offline-cancel",
            lambda: self.app.runner.run(
                manager.build_cancel_restart_update_command(),
                "Cancelling Discover's restart update"),
            confirm_label="Cancel Restart Update", cancel_label="Keep It")

    @pyqtSlot()
    def disableDiscoverSystem(self) -> None:
        manager = self.app.discover_manager
        self.app.prompts.confirm(
            "Turn Off Discover Update Checks for All Users?",
            "This runs as root (pkexec) and affects every account on this "
            "computer:\n\n"
            "• Stops Discover's background update checker for all users\n"
            "• Turns off Discover's update notifications by default\n"
            "• Stops PackageKit from installing updates during restarts\n\n"
            "Discover itself keeps working for browsing and installing apps, and "
            "this survives Discover package updates. Turn Back On undoes all of it.",
            lambda: self.app.runner.run(
                manager.build_system_disable_commands()[0],
                "Disabling Discover system-wide"),
            confirm_label="Turn Off for All Users", destructive=True)

    @pyqtSlot()
    def enableDiscoverSystem(self) -> None:
        manager = self.app.discover_manager
        self.app.prompts.confirm(
            "Turn Discover Update Checks Back On?",
            "Restore Discover's update checker, notifications and restart-time "
            "updates for all users? This undoes Turn Off for All Users.",
            lambda: self.app.runner.run(
                manager.build_system_enable_commands()[0],
                "Re-enabling Discover system-wide"),
            confirm_label="Turn Back On")

    @pyqtSlot()
    def stopDiscoverChecker(self) -> None:
        try:
            subprocess.run(self.app.discover_manager.build_kill_notifier_command(),
                           timeout=5)
            self.app.prompts.inform(
                "Checker Stopped",
                "Discover's background checker was stopped. It returns at the "
                "next login unless this app handles updates.")
        except Exception as e:
            self.app.prompts.inform("Stop Failed", str(e), level="error")
        self.load_discover_status()

    @pyqtSlot()
    def removeDiscoverNotifier(self) -> None:
        manager = self.app.discover_manager
        self.app.prompts.confirm(
            "Uninstall the Update Checker?",
            "Uninstall Discover's update checker package but keep Discover "
            "itself?\n\nThis stops automatic checks for everyone on this "
            "computer (needs your password). Reinstall the package to undo.",
            lambda: self.app.runner.run(
                manager.build_remove_notifier_package_command(),
                "Removing plasma-discover-notifier"),
            confirm_label="Uninstall", destructive=True)
