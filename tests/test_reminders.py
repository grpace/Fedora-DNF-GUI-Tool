"""Update reminders: what the background check finds and says, the
systemd timer that runs it (or the login entry without systemd), the
headless ``dnf-gui --check`` run, and Settings → Reminders.

Desktop notifications themselves are in test_notifications.py.
"""

import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from dnf_gui.core import security
from dnf_gui.core.app_settings import (
    AppSettings, ReminderResult, perform_background_check,
)
from dnf_gui.core.package import UpdateInfo
from dnf_gui.core.security import SecuritySummary
from tests.conftest import answer
from tests.test_security import ADVISORY, FORCED, SECURITY_BLOCKED, _summary


class TestReminderNotificationTriggers(unittest.TestCase):
    """Verify that Flatpak updates trigger reminders independently, even if security_only is enabled."""

    def _mock_settings(self, security_only: bool, notify_flatpak: bool):
        s = MagicMock(spec=AppSettings)
        s.security_only = security_only
        s.notify_flatpak = notify_flatpak
        return s

    @patch("dnf_gui.core.dnf_backend.DNFBackend.check_updates")
    @patch("dnf_gui.core.flatpak_backend.FlatpakBackend.available", True)
    @patch("dnf_gui.core.flatpak_backend.FlatpakBackend.check_updates")
    @patch("dnf_gui.core.security.get_security_summary")
    def test_security_only_with_flatpak_updates(
        self, mock_sec, mock_flatpak, mock_dnf
    ):
        """When security_only is ON and Flatpak updates exist, reminder MUST trigger."""
        # 0 security advisories, 5 routine RPM updates, 2 Flatpak updates
        mock_dnf.return_value = UpdateInfo(total_updates=5)
        mock_flatpak.return_value = [MagicMock(), MagicMock()]
        mock_sec.return_value = SecuritySummary(total=0, critical=0)

        settings = self._mock_settings(security_only=True, notify_flatpak=True)
        res = perform_background_check(settings)

        self.assertTrue(res.should_notify)
        self.assertIn("2 Flatpak", res.message)
        self.assertNotIn("system", res.message)

    @patch("dnf_gui.core.dnf_backend.DNFBackend.check_updates")
    @patch("dnf_gui.core.flatpak_backend.FlatpakBackend.available", True)
    @patch("dnf_gui.core.flatpak_backend.FlatpakBackend.check_updates")
    @patch("dnf_gui.core.security.get_security_summary")
    def test_security_only_with_flatpak_disabled_is_quiet(
        self, mock_sec, mock_flatpak, mock_dnf
    ):
        """When security_only is ON and notify_flatpak is OFF, routine + Flatpak must NOT notify."""
        mock_dnf.return_value = UpdateInfo(total_updates=5)
        mock_flatpak.return_value = [MagicMock()]
        mock_sec.return_value = SecuritySummary(total=0)

        settings = self._mock_settings(security_only=True, notify_flatpak=False)
        res = perform_background_check(settings)

        self.assertFalse(res.should_notify)

    @patch("dnf_gui.core.dnf_backend.DNFBackend.check_updates")
    @patch("dnf_gui.core.flatpak_backend.FlatpakBackend.available", True)
    @patch("dnf_gui.core.flatpak_backend.FlatpakBackend.check_updates")
    @patch("dnf_gui.core.security.get_security_summary")
    def test_security_only_with_security_updates(
        self, mock_sec, mock_flatpak, mock_dnf
    ):
        """Security advisories always trigger notification."""
        mock_dnf.return_value = UpdateInfo(total_updates=3)
        mock_flatpak.return_value = []
        mock_sec.return_value = SecuritySummary(total=2, critical=1)

        settings = self._mock_settings(security_only=True, notify_flatpak=True)
        res = perform_background_check(settings)

        self.assertTrue(res.should_notify)
        self.assertTrue(res.security_urgent)
        self.assertEqual(res.title, "Important Security Updates")
        self.assertIn("2 security updates", res.message)
        self.assertNotIn("3 system", res.message)  # security-only mode

    @patch("dnf_gui.core.dnf_backend.DNFBackend.check_updates")
    @patch("dnf_gui.core.flatpak_backend.FlatpakBackend.available", True)
    @patch("dnf_gui.core.flatpak_backend.FlatpakBackend.check_updates")
    @patch("dnf_gui.core.security.get_security_summary")
    def test_all_updates_triggers_for_routine_dnf(
        self, mock_sec, mock_flatpak, mock_dnf
    ):
        """When security_only is OFF, routine DNF updates trigger notification."""
        mock_dnf.return_value = UpdateInfo(total_updates=4)
        mock_flatpak.return_value = []
        mock_sec.return_value = SecuritySummary(total=0)

        settings = self._mock_settings(security_only=False, notify_flatpak=False)
        res = perform_background_check(settings)

        self.assertTrue(res.should_notify)
        self.assertIn("4 system updates are ready", res.message)
        self.assertEqual(res.title, "Updates Available")


class TestBackgroundCheckerLifecycle(unittest.TestCase):
    """The checker is a systemd timer that follows the reminder interval."""

    def setUp(self):
        self.config = Path(os.environ["XDG_CONFIG_HOME"])  # this test's own
        which = patch("dnf_gui.core.paths.find_system_binary", return_value="/usr/bin/dnf-gui")
        which.start()
        self.addCleanup(which.stop)
        self.unit_dir = self.config / "systemd" / "user"
        self.timer = self.unit_dir / "dnf-gui-update-checker.timer"
        self.service = self.unit_dir / "dnf-gui-update-checker.service"
        self.autostart = self.config / "autostart" / "dnf-gui-update-checker.desktop"

    def _install(self, interval=24, systemd_ok=True):
        calls = []
        with patch("dnf_gui.core.app_settings._systemctl_user",
                   side_effect=lambda *a: calls.append(a) or systemd_ok):
            ok = AppSettings.set_checker_installed(True, interval)
        return ok, calls

    def test_install_writes_service_and_timer(self):
        self.assertFalse(AppSettings.is_checker_installed())
        ok, calls = self._install()
        self.assertTrue(ok)
        self.assertTrue(AppSettings.is_checker_installed())
        self.assertIn(("enable", "dnf-gui-update-checker.timer",
                       "dnf-gui-update-checker.service"), calls)
        self.assertIn(("restart", "dnf-gui-update-checker.timer"), calls)

        service = self.service.read_text()
        self.assertIn("ExecStart=/usr/bin/dnf-gui --check --scheduled", service)
        self.assertIn("SuccessExitStatus=2", service)
        self.assertIn("Restart=on-failure", service)
        self.assertIn("StartLimitBurst=4", service)
        self.assertIn("Requisite=graphical-session.target", service)
        self.assertIn("WantedBy=graphical-session.target", service)
        self.assertIn("ConditionPathExists=/usr/bin/dnf-gui\n", service)
        timer = self.timer.read_text()
        self.assertIn("OnCalendar=*-*-* 09:00:00", timer)
        self.assertIn("Persistent=true", timer)
        self.assertIn("WantedBy=timers.target", timer)
        self.assertFalse(self.autostart.exists())
        self.assertFalse(AppSettings.checker_needs_refresh(24))

    def test_timer_follows_interval(self):
        for hours, schedule in ((12, "*-*-* 09,21:00:00"),
                                (72, "Mon,Thu *-*-* 09:00:00"),
                                (168, "Mon *-*-* 09:00:00")):
            self._install(hours)
            self.assertIn(f"OnCalendar={schedule}\n", self.timer.read_text())
        self.assertTrue(AppSettings.checker_needs_refresh(24))

    def test_install_replaces_legacy_login_entry(self):
        self.autostart.parent.mkdir(parents=True)
        self.autostart.write_text("[Desktop Entry]\nExec=dnf-gui --check\n")
        self.assertTrue(AppSettings.is_checker_installed())
        self.assertTrue(AppSettings.checker_needs_refresh(24))
        self._install()
        self.assertFalse(self.autostart.exists())
        self.assertFalse(AppSettings.checker_needs_refresh(24))

    def test_remove_disables_timer_and_deletes_files(self):
        self._install()
        calls = []
        with patch("dnf_gui.core.app_settings._systemctl_user",
                   side_effect=lambda *a: calls.append(a) or True):
            AppSettings.set_checker_installed(False)
        self.assertIn(("disable", "--now", "dnf-gui-update-checker.timer",
                       "dnf-gui-update-checker.service"), calls)
        self.assertFalse(AppSettings.is_checker_installed())
        self.assertFalse(self.service.exists())

    def test_without_systemd_falls_back_to_login_check(self):
        ok, _ = self._install(systemd_ok=False)
        self.assertFalse(ok)
        self.assertFalse(self.timer.exists())
        entry = self.autostart.read_text()
        self.assertIn("Exec=/usr/bin/dnf-gui --check --wait\n", entry)
        self.assertIn("X-KDE-AutostartScript=true", entry)
        self.assertIn("TryExec=/usr/bin/dnf-gui\n", entry)

    def test_exec_quotes_paths_with_spaces(self):
        with patch("dnf_gui.core.paths.find_system_binary", return_value=None), \
                patch("sys.executable", "/home/me/My Venv/bin/python3"):
            self._install()
        service = self.service.read_text()
        self.assertIn(
            'ExecStart="/home/me/My Venv/bin/python3" -m dnf_gui --check --scheduled',
            service)
        # The interpreter outlives the package, so test the import instead.
        self.assertIn(
            'ExecCondition="/home/me/My Venv/bin/python3" -c "import dnf_gui"',
            service)
        self.assertNotIn("ConditionPathExists", service)


class TestHeadlessCheck(unittest.TestCase):
    """``dnf-gui --check`` must not lose reminders."""

    def setUp(self):
        AppSettings().set("reminders/enabled", True)
        AppSettings().set("reminders/interval_hours", 24)
        AppSettings().set("reminders/last_check", "")

    def _run(self, result=None, delivered=True, server=True, scheduled=False,
             wait=False, clicked=None):
        from dnf_gui import app
        from dnf_gui.core.notifications import Activation
        argv = (["--check"] + (["--scheduled"] if scheduled else [])
                + (["--wait"] if wait else []))

        def fake_check(settings, security_only=None):
            if not result.check_failed:
                settings.set_last_check()
            return result

        outcome = Activation(delivered=delivered, page=clicked, token="tok")
        with patch("dnf_gui.core.app_settings.perform_background_check",
                   side_effect=fake_check) as check, \
                patch("dnf_gui.core.notifications.send_once",
                      return_value=delivered) as notify, \
                patch("dnf_gui.core.notifications.notify_and_wait",
                      return_value=outcome) as notify_wait, \
                patch("dnf_gui.core.notifications.launch_app") as launch, \
                patch("dnf_gui.core.app_settings.notification_server_available",
                      return_value=server), \
                patch("dnf_gui.core.app_settings.wait_for_desktop",
                      return_value=server):
            code = app._run_headless_check(app._parse_args(argv))
        self.notify_wait, self.launch = notify_wait, launch
        return code, check, (notify_wait if wait else notify)

    def test_skips_when_reminders_off(self):
        AppSettings().set("reminders/enabled", False)
        code, check, _ = self._run()
        self.assertEqual(code, 0)
        check.assert_not_called()

    def test_waits_for_notification_server(self):
        code, check, _ = self._run(server=False)
        self.assertEqual(code, 1)  # systemd retries
        check.assert_not_called()
        self.assertTrue(AppSettings().is_check_due())

    def test_notifies_when_updates_pending(self):
        res = ReminderResult(security_total=2, should_notify=True, message="2 security")
        code, _, notify = self._run(res)
        self.assertEqual(code, 2)
        notify.assert_called_once()
        self.assertFalse(AppSettings().is_check_due())

    def test_reminder_without_wait_offers_no_click(self):
        res = ReminderResult(should_notify=True, title="Updates Available",
                             message="4 system updates are ready to install.")
        _, _, notify = self._run(res)
        sent = notify.call_args.args[0]
        self.assertEqual(sent.action_list(), [])
        self.launch.assert_not_called()

    def test_clicked_reminder_opens_updates_page(self):
        res = ReminderResult(should_notify=True, security_total=2,
                             title="Security Updates Available", message="x")
        code, _, notify = self._run(res, wait=True, clicked="updates")
        self.assertEqual(code, 2)
        sent = notify.call_args.args[0]
        self.assertEqual(sent.page, "updates")
        self.assertIn(("updates", "View Updates"), sent.actions)
        # Withdrawn just before the next daily check would replace it.
        self.assertEqual(notify.call_args.args[1], 23 * 3600)
        self.launch.assert_called_once_with("updates", "tok")

    def test_dismissed_reminder_opens_nothing(self):
        res = ReminderResult(should_notify=True, message="x")
        code, _, _ = self._run(res, wait=True, clicked=None)
        self.assertEqual(code, 2)
        self.launch.assert_not_called()

    def test_scheduled_run_skips_only_recent_checks(self):
        from datetime import datetime, timedelta
        settings = AppSettings()
        settings.set_last_check(datetime.now() - timedelta(hours=2))
        _, check, _ = self._run(scheduled=True)
        check.assert_not_called()  # the app checked 2 hours ago
        settings.set_last_check(datetime.now() - timedelta(hours=20))
        _, check, _ = self._run(ReminderResult(), scheduled=True)
        check.assert_called_once()  # timer slot, even though < 24h
        settings.set_last_check(datetime.now() - timedelta(hours=20))
        _, check, _ = self._run(ReminderResult())
        check.assert_not_called()  # unscheduled runs keep the full interval

    def test_scheduled_run_gives_up_when_desktop_never_ready(self):
        code, check, _ = self._run(server=False, scheduled=True)
        self.assertEqual(code, 1)
        check.assert_not_called()

    def test_undelivered_notification_keeps_check_due(self):
        res = ReminderResult(security_total=2, should_notify=True, message="2 security")
        code, _, _ = self._run(res, delivered=False)
        self.assertEqual(code, 1)
        self.assertTrue(AppSettings().is_check_due())

    def test_failed_dnf_check_keeps_check_due(self):
        code, _, notify = self._run(ReminderResult(check_failed=True))
        self.assertEqual(code, 1)
        notify.assert_not_called()
        self.assertTrue(AppSettings().is_check_due())


class TestReminderText(unittest.TestCase):
    def _text(self, security_only=False, notify_flatpak=True, **counts):
        from dnf_gui.core.notifications import reminder_text
        return reminder_text(ReminderResult(**counts), security_only, notify_flatpak)

    def test_combines_system_security_and_flatpak(self):
        title, body = self._text(dnf_updates=343, security_total=2,
                                 flatpak_updates=6)
        self.assertEqual(title, "Security Updates Available")
        self.assertEqual(body, "343 system updates (2 security) and "
                               "6 Flatpak updates are ready to install.")

    def test_singular(self):
        self.assertEqual(self._text(dnf_updates=1)[1],
                         "1 system update is ready to install.")

    def test_security_only_hides_routine_updates(self):
        title, body = self._text(security_only=True, dnf_updates=343,
                                 security_total=2, security_urgent=True,
                                 flatpak_updates=6)
        self.assertEqual(title, "Important Security Updates")
        self.assertTrue(body.startswith(
            "2 security updates and 6 Flatpak updates are ready to install."))
        self.assertNotIn("343", body)

    def test_no_shouting_or_symbols(self):
        title, body = self._text(security_total=3, security_urgent=True)
        self.assertNotIn("⚠", title + body)
        self.assertNotIn("SECURITY", title + body)

    def test_wait_lasts_until_the_next_check(self):
        from dnf_gui.core.app_settings import reminder_wait_seconds
        self.assertEqual(reminder_wait_seconds(12), 11 * 3600)
        self.assertEqual(reminder_wait_seconds(168), 23 * 3600)


class TestWaitForDesktop(unittest.TestCase):
    def test_waits_for_notification_server_then_network(self):
        from dnf_gui.core import app_settings
        with patch.object(app_settings, "notification_server_available",
                          side_effect=[False, False, True]), \
                patch.object(app_settings, "network_online",
                             return_value=True) as online, \
                patch("time.sleep") as sleep:
            self.assertTrue(app_settings.wait_for_desktop(timeout=60, poll=1))
        self.assertEqual(sleep.call_count, 2)
        online.assert_called_once()

    def test_gives_up_after_timeout(self):
        from dnf_gui.core import app_settings
        with patch.object(app_settings, "notification_server_available",
                          return_value=False), \
                patch("time.sleep"):
            self.assertFalse(app_settings.wait_for_desktop(timeout=0))


class TestFailedCheckThrottle(unittest.TestCase):
    @patch("dnf_gui.core.dnf_backend.DNFBackend.check_updates")
    @patch("dnf_gui.core.flatpak_backend.FlatpakBackend.available", False)
    @patch("dnf_gui.core.security.get_security_summary")
    def test_failed_check_does_not_record_last_check(self, mock_sec, mock_dnf):
        mock_dnf.return_value = UpdateInfo(check_failed=True)
        mock_sec.return_value = SecuritySummary(total=0)
        settings = MagicMock(spec=AppSettings)
        settings.security_only = False
        settings.notify_flatpak = False
        res = perform_background_check(settings)
        self.assertTrue(res.check_failed)
        settings.set_last_check.assert_not_called()

    @patch("dnf_gui.core.dnf_backend.DNFBackend.check_updates",
           return_value=UpdateInfo(total_updates=3))
    @patch("dnf_gui.core.flatpak_backend.FlatpakBackend.available", False)
    @patch("dnf_gui.core.security.get_security_summary")
    def test_security_only_reminder_quiet_when_all_are_waiting(self, mock_sec, _dnf):
        mock_sec.return_value = _summary((ADVISORY, "important", {"libheif"}))
        settings = AppSettings()
        settings.security_only = True
        settings.notify_flatpak = False
        with patch.object(security, "_dry_run", side_effect=[SECURITY_BLOCKED, FORCED]):
            res = perform_background_check(settings)
        self.assertEqual(res.security_total, 0)
        self.assertFalse(res.security_urgent)
        self.assertFalse(res.should_notify)


class TestSettingsReminders:
    """Settings → Reminders writes the settings and schedules the checker."""

    @pytest.fixture(autouse=True)
    def quiet_status(self, app):
        # show() re-reads status; keep it off the real system (sudo -n -l).
        with patch.object(app.settings_controller, "load_passwordless_status"), \
                patch.object(app.settings_controller, "load_discover_status"):
            yield

    def test_save_writes_settings_and_installs_checker(self, app):
        with patch.object(AppSettings, "set_checker_installed", return_value=True) as install:
            app.settings_controller.saveReminders(True, True, False, 72)
        settings = app.settings
        assert (settings.reminders_enabled, settings.security_only,
                settings.notify_flatpak, settings.check_interval_hours) == (True, True, False, 72)
        install.assert_called_once_with(True, 72)
        assert app.prompts.notices[-1] == "Reminders saved. Background checks are on."

    def test_unknown_interval_is_ignored(self, app):
        app.settings.check_interval_hours = 24
        with patch.object(AppSettings, "set_checker_installed", return_value=True):
            app.settings_controller.saveReminders(True, False, True, 5)
        assert app.settings.check_interval_hours == 24

    def test_turning_off_removes_checker(self, app):
        with patch.object(AppSettings, "set_checker_installed", return_value=True) as install:
            app.settings_controller.saveReminders(False, False, True, 24)
        assert not app.settings.reminders_enabled
        install.assert_called_once_with(False, 24)

    def test_no_systemd_warns(self, app):
        shown = answer(app)
        with patch.object(AppSettings, "set_checker_installed", return_value=False):
            app.settings_controller.saveReminders(True, False, True, 24)
        assert shown[-1].title == "Reminders Saved"
        assert shown[-1].level == "warning"
