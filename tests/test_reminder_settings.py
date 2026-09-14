"""Tests for update reminder settings, autostart lifecycle, and notification triggers."""

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


class TestAutostartLifecycle(unittest.TestCase):
    """Verify that autostart file creation and deletion works safely."""

    def test_autostart_install_and_remove(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_path = Path(tmpdir) / "autostart" / "dnf-gui-update-checker.desktop"
            with patch.object(AppSettings, "checker_autostart_path", return_value=test_path):
                self.assertFalse(AppSettings.is_checker_installed())

                AppSettings.set_checker_installed(True)
                self.assertTrue(AppSettings.is_checker_installed())
                content = test_path.read_text()
                self.assertIn("dnf-gui --check", content)
                self.assertIn("X-KDE-AutostartScript=true", content)

                AppSettings.set_checker_installed(False)
                self.assertFalse(AppSettings.is_checker_installed())


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
