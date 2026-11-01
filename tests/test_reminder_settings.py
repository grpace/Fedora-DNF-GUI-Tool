"""Tests for update reminder settings, the background checker, and notification triggers."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from dnf_gui.core.app_settings import (
    AppSettings, ReminderResult, perform_background_check,
)
from dnf_gui.core.security import SecuritySummary
from dnf_gui.core.package import UpdateInfo

_app = None


def _ensure_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication([])
    return _app


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
        self.assertIn("SECURITY", res.message)

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
        self.assertIn("4 system", res.message)


class TestBackgroundCheckerLifecycle(unittest.TestCase):
    """The checker is a systemd timer that follows the reminder interval."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.config = Path(tmp.name)
        env = patch.dict(os.environ, {"XDG_CONFIG_HOME": tmp.name})
        env.start()
        self.addCleanup(env.stop)
        which = patch("shutil.which", return_value="/usr/bin/dnf-gui")
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
        self.assertIn("Exec=/usr/bin/dnf-gui --check\n", entry)
        self.assertIn("X-KDE-AutostartScript=true", entry)
        self.assertIn("TryExec=/usr/bin/dnf-gui\n", entry)

    def test_exec_quotes_paths_with_spaces(self):
        with patch("shutil.which", return_value=None), \
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
        self.addCleanup(AppSettings().set, "reminders/enabled", False)

    def _run(self, result=None, delivered=True, server=True, scheduled=False):
        from dnf_gui import app
        argv = ["dnf-gui", "--check"] + (["--scheduled"] if scheduled else [])

        def fake_check(settings, security_only=None):
            if not result.check_failed:
                settings.set_last_check()
            return result

        with patch("dnf_gui.core.app_settings.perform_background_check",
                   side_effect=fake_check) as check, \
                patch("dnf_gui.core.app_settings.send_desktop_notification",
                      return_value=delivered) as notify, \
                patch("dnf_gui.core.app_settings.notification_server_available",
                      return_value=server), \
                patch("dnf_gui.core.app_settings.wait_for_desktop",
                      return_value=server), \
                patch("sys.argv", argv):
            code = app._run_headless_check()
        return code, check, notify

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

    @patch("subprocess.run")
    def test_dnf_error_exit_marks_check_failed(self, mock_run):
        from dnf_gui.core.dnf_backend import DNFBackend
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        self.assertTrue(DNFBackend().check_updates().check_failed)


class TestSettingsPageUI(unittest.TestCase):
    """Verify UI components on SettingsPage."""

    @classmethod
    def setUpClass(cls):
        _ensure_app()

    def test_reminder_suboptions_toggle_with_master(self):
        from dnf_gui.ui.pages.settings_page import SettingsPage
        page = SettingsPage()
        page.show()
        self.addCleanup(page.close)
        self.addCleanup(page.deleteLater)

        # By default when loaded as disabled
        page.load_reminder_settings({"enabled": False})
        self.assertFalse(page._rem_enabled.isChecked())
        self.assertFalse(page._child_options.isEnabled())
        self.assertFalse(page._interval_combo.isEnabled())

        # When enabled
        page._rem_enabled.setChecked(True)
        self.assertTrue(page._child_options.isEnabled())
        self.assertTrue(page._interval_combo.isEnabled())

        # When unchecked again
        page._rem_enabled.setChecked(False)
        self.assertFalse(page._child_options.isEnabled())
        self.assertFalse(page._interval_combo.isEnabled())
