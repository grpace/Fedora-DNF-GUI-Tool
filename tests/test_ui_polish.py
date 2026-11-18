"""Tests for the UI polish batch: updates cache, reboot dismiss, plain-language
status text, history details, and the dnf list parsers."""

import gc
import os
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication  # noqa: E402


def _controller():
    # Free controllers left by earlier tests now, while none of their
    # threads run: a later processEvents() would otherwise fire their
    # pending start-up timers and GC could destroy a running QThread.
    gc.collect()
    from dnf_gui.ui.controllers.app_controller import AppController
    return AppController()


class TestUpdatesCache(unittest.TestCase):
    def _cached_result(self):
        from dnf_gui.core.package import UpdateInfo
        from dnf_gui.core.security import SecuritySummary
        return {
            "dnf": UpdateInfo(total_updates=0, last_checked="2026-09-14 09:44 PM"),
            "flatpak": [],
            "security": SecuritySummary(),
            "preview": None,
            "security_preview": None,
            "reboot": False,
        }

    def test_revisit_reuses_cache_without_rescan(self):
        app = _controller()
        self.assertEqual(app.currentPage, "updates")
        app.updates._cache = self._cached_result()
        with patch.object(app.updates, "check") as check:
            app.refreshCurrent(revisit=True)  # page visit
        check.assert_not_called()
        self.assertIn("up to date", app.updates.headline.lower())

    def test_navigating_back_reuses_cache(self):
        app = _controller()
        app.updates._cache = self._cached_result()
        with patch.object(app.updates, "check") as check, \
                patch.object(app.settings_controller, "show"):
            app.navigate("settings")
            app.navigate("updates")
        check.assert_not_called()

    def test_empty_cache_triggers_scan(self):
        app = _controller()
        app.updates._cache = None
        with patch.object(app.updates, "check") as check:
            app.refreshCurrent(revisit=True)
        check.assert_called_once()

    def test_successful_command_invalidates_cache(self):
        app = _controller()
        app.updates._cache = self._cached_result()
        with patch.object(app, "refreshCurrent"), \
                patch.object(app.updates, "recheck_reboot"):
            app._on_operation_finished(0, "System Upgrade", False)
        self.assertIsNone(app.updates._cache)

    def test_failed_command_keeps_cache(self):
        app = _controller()
        app.updates._cache = self._cached_result()
        app._on_operation_finished(1, "System Upgrade", False)
        self.assertIsNotNone(app.updates._cache)


class TestRebootDismiss(unittest.TestCase):
    def test_dismiss_survives_redisplay_until_fresh_scan(self):
        from dnf_gui.core.package import UpdateInfo
        updates = _controller().updates
        updates.set_reboot_required(True)
        self.assertTrue(updates.rebootRequired)
        updates.dismissReboot()
        self.assertFalse(updates.rebootRequired)
        updates.set_reboot_required(True)  # e.g. post-upgrade recheck
        self.assertFalse(updates.rebootRequired)
        # A fresh scan resets the dismissal
        updates._on_checked({"dnf": UpdateInfo(), "flatpak": [], "security": None,
                             "reboot": True})
        self.assertTrue(updates.rebootRequired)


class TestSettingsPolish(unittest.TestCase):
    def test_discover_status_is_plain_language(self):
        settings = _controller().settings_controller

        def show(**kwargs):
            base = dict(discover_installed=True,
                        system_autostart_present=True,
                        per_user_disabled=False,
                        notifier_running=False,
                        notification_interval="-1",
                        unattended_updates="false",
                        restart_update_scheduled=False,
                        system_disabled=False)
            base.update(kwargs)
            settings._on_discover_status(SimpleNamespace(**base))
            for text in (settings.discoverTitle, settings.discoverText):
                self.assertNotIn("—", text)
                for jargon in ("PlasmaDiscoverUpdates", "packagekit-offline-update",
                               "DiscoverNotifier", "autostart"):
                    self.assertNotIn(jargon, text)

        # Active takeover: positive, only Restore offered.
        show(per_user_disabled=True)
        self.assertEqual(settings.discoverLevel, "positive")
        self.assertIn("this app handles updates", settings.discoverTitle.lower())
        self.assertTrue(settings.discoverActive)

        # Discover checking on its own: warning, only Takeover offered.
        show(notifier_running=True, restart_update_scheduled=True)
        self.assertEqual(settings.discoverLevel, "warning")
        self.assertFalse(settings.discoverActive)
        self.assertIn("running right now", settings.discoverText)
        self.assertIn("restart", settings.discoverText)

        # Nothing installed: no jargon, no actions.
        show(discover_installed=False, system_autostart_present=False)
        self.assertEqual(settings.discoverLevel, "info")
        self.assertFalse(settings.discoverInstalled)

    def test_passwordless_status_has_no_em_dash(self):
        from dnf_gui.core import passwordless as pw
        app = _controller()
        self.addCleanup(setattr, app.settings, "passwordless_scope", "off")
        for remembered, live in (("off", "off"), ("updates", "updates"),
                                 ("updates", "off"), ("off", "full")):
            app.settings.passwordless_scope = remembered
            with patch.object(pw, "live_status", return_value=(live, True, False)):
                app.settings_controller.load_passwordless_status()
            controller = app.settings_controller
            for text in [controller.passwordlessTitle, controller.passwordlessText,
                         *controller.passwordlessNotes]:
                self.assertNotIn("—", text)

    def test_passwordless_status_levels(self):
        from dnf_gui.core import passwordless as pw
        app = _controller()
        self.addCleanup(setattr, app.settings, "passwordless_scope", "off")
        controller = app.settings_controller

        def status(remembered, live, legacy=False, covered=True):
            app.settings.passwordless_scope = remembered
            with patch.object(pw, "live_status", return_value=(live, legacy, covered)):
                controller.load_passwordless_status()
            return controller.passwordlessLevel, controller.passwordlessTitle

        self.assertEqual(status("off", "off"), ("info", "Off"))
        self.assertEqual(status("updates", "updates"), ("positive", "On: Updates Only"))
        self.assertEqual(status("updates", "off"), ("warning", "Not Working"))
        # An old wildcard rule is a security warning even when it works.
        self.assertEqual(status("updates", "updates", legacy=True)[0], "warning")
        self.assertTrue(any("overly broad" in n for n in controller.passwordlessNotes))
        self.assertEqual(status("updates", "updates", covered=False)[0], "warning")


class TestHistoryDetail(unittest.TestCase):
    def test_detail_loads_for_the_selected_transaction(self):
        app = _controller()
        history = app.history
        with patch.object(app.backend, "history_info", return_value="Line 1\nLine 2"):
            history.loadDetail("42")
            self.assertTrue(history.detailLoading)
            deadline = time.monotonic() + 2
            while history.detailLoading and time.monotonic() < deadline:
                time.sleep(0.02)
                QApplication.instance().processEvents()
        self.assertEqual(history.detailId, "42")
        self.assertEqual(history.detailText, "Line 1\nLine 2")
        history._on_detail("41", "stale")  # an older request finishing late
        self.assertEqual(history.detailText, "Line 1\nLine 2")

    def test_undo_confirms_then_runs(self):
        from tests.conftest import answer
        app = _controller()
        shown = answer(app, "yes")
        with patch.object(app.runner, "run") as run:
            app.history.undo("42")
        self.assertTrue(shown[0].destructive)
        run.assert_called_once_with(app.backend.build_history_undo_command("42"),
                                    "Undoing transaction #42")
        answer(app, "no")
        with patch.object(app.runner, "run") as run:
            app.history.undo("42")
        run.assert_not_called()


class TestListParsing(unittest.TestCase):
    def test_repolist_parsing_status(self):
        from dnf_gui.core.dnf_backend import DNFBackend
        from unittest.mock import patch
        sample_output = "\n".join([
            "repo id                                            repo name                                                  status",
            "brave-browser                                      Brave Browser                                              enabled",
            "copr:copr.fedorainfracloud.org:avengemedia:dms     Copr repo for dms owned by avengemedia                     disabled",
            "fedora                                             Fedora 43 - x86_64                                         enabled",
        ])
        b = DNFBackend()
        with patch.object(b, "_run", return_value=sample_output):
            repos = b.list_repos(show_all=True)
            self.assertEqual(len(repos), 3)
            self.assertEqual(repos[0]["id"], "brave-browser")
            self.assertEqual(repos[0]["name"], "Brave Browser")
            self.assertTrue(repos[0]["enabled"])
            self.assertEqual(repos[1]["id"], "copr:copr.fedorainfracloud.org:avengemedia:dms")
            self.assertEqual(repos[1]["name"], "Copr repo for dms owned by avengemedia")
            self.assertFalse(repos[1]["enabled"])

    def test_history_parsing_packagekit(self):
        from dnf_gui.core.dnf_backend import DNFBackend
        from unittest.mock import patch
        sample_output = "\n".join([
            "    ID Command line                         Date and time       Action(s) Altered",
            "   242 /usr/bin/dnf5 upgrade -y --refresh   2026-09-09 13:03:56               126",
            "   238                                      2026-09-05 05:51:10                 2",
        ])
        b = DNFBackend()
        with patch.object(b, "_run", return_value=sample_output):
            txns = b.history()
            self.assertEqual(len(txns), 2)
            self.assertEqual(txns[0]["id"], "242")
            self.assertEqual(txns[0]["altered"], "126")
            self.assertEqual(txns[1]["id"], "238")
            self.assertEqual(txns[1]["command"], "System / PackageKit")
            self.assertEqual(txns[1]["altered"], "2")


if __name__ == "__main__":
    unittest.main()
