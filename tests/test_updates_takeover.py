"""Tests for Discover takeover, security summaries, and combined updates."""

import unittest
from unittest.mock import patch

from dnf_gui.core.security import (
    SecuritySummary,
    build_security_update_command,
    get_security_summary,
)
from dnf_gui.core.discover_manager import DiscoverManager


class TestSecuritySummary(unittest.TestCase):
    def test_urgent_flags(self):
        sec = SecuritySummary(total=2, critical=1)
        self.assertTrue(sec.urgent)
        calm = SecuritySummary(total=1, moderate=1)
        self.assertFalse(calm.urgent)
        self.assertFalse(SecuritySummary().urgent)

    def test_build_commands(self):
        sec_cmd = build_security_update_command()
        self.assertIn("--security", sec_cmd)
        self.assertIn("pkexec", sec_cmd)

    @patch("dnf_gui.core.security._run")
    def test_parses_dnf4_style_list(self, mock_run):
        mock_run.side_effect = [
            "FEDORA-2026-aaa Critical/Sec. kernel-6.12-1.fc43.x86_64\n"
            "FEDORA-2026-bbb Moderate/Sec. firefox-125-1.fc43.x86_64\n",
            "",
        ]
        sec = get_security_summary()
        self.assertEqual(sec.total, 2)
        self.assertEqual(sec.critical, 1)
        self.assertEqual(sec.moderate, 1)
        self.assertIn("FEDORA-2026-aaa", sec.advisories)

    @patch("dnf_gui.core.security._run")
    def test_parses_dnf5_list_counting_unique_advisories(self, mock_run):
        mock_run.side_effect = [
            "Updating and loading repositories:\n"
            "Repositories loaded.\n"
            "Name                   Type     Severity   Package                       Issued\n"
            "FEDORA-2026-0ba06812ef security Important  libheif-1.23.6-1.fc44.x86_64 2026-10-18 01:17:00\n"
            "FEDORA-2026-0ba06812ef security Important  libheif-1.23.6-1.fc44.i686   2026-10-18 01:17:00\n"
            "FEDORA-2026-1111111111 security Critical   kernel-6.18-1.fc44.x86_64    2026-10-18 01:17:00\n",
            "",
        ]
        sec = get_security_summary()
        self.assertEqual(sec.total, 2)
        self.assertEqual(sec.important, 1)
        self.assertEqual(sec.critical, 1)
        self.assertEqual(len(sec.packages), 3)
        self.assertEqual(mock_run.call_args_list[0].args[0][1:],
                         ["updateinfo", "list", "--updates", "--security"])

    @patch("dnf_gui.core.security._run")
    def test_dnf5_summary_fallback_ignores_other_sections(self, mock_run):
        mock_run.side_effect = [
            "",
            "Available advisory information summary:\n"
            "Security    : 36\n"
            "  Critical  : 3\n"
            "  Important : 18\n"
            "  Moderate  : 11\n"
            "  Low       : 2\n"
            "  Other     : 2\n"
            "Bugfix      : 36\n"
            "Enhancement : 30\n",
        ]
        sec = get_security_summary()
        self.assertEqual(sec.total, 34)
        self.assertEqual((sec.critical, sec.important, sec.moderate, sec.low),
                         (3, 18, 11, 2))

    @patch("dnf_gui.core.security._run")
    def test_summary_fallback_counts(self, mock_run):
        mock_run.side_effect = [
            "",  # empty list output
            "Updates Information Summary: available\n"
            "    2 Critical Security notice(s)\n"
            "    3 Important Security notice(s)\n",
        ]
        sec = get_security_summary()
        self.assertEqual(sec.total, 5)
        self.assertEqual(sec.critical, 2)
        self.assertEqual(sec.important, 3)


class TestDiscoverManager(unittest.TestCase):
    def setUp(self):
        self.mgr = DiscoverManager()

    def test_system_commands_use_pkexec(self):
        for cmd in self.mgr.build_system_disable_commands():
            self.assertIn("pkexec", cmd[0])
        for cmd in self.mgr.build_system_enable_commands():
            self.assertIn("pkexec", cmd[0])

    def test_kill_command_no_root(self):
        cmd = self.mgr.build_kill_notifier_command()
        self.assertNotIn("pkexec", cmd)
        self.assertIn("pkill", cmd)

    def test_remove_notifier_targets_split_package(self):
        cmd = self.mgr.build_remove_notifier_package_command()
        self.assertIn("plasma-discover-notifier", cmd)
        # Must NOT remove plasma-discover itself
        self.assertNotIn("plasma-discover ", " ".join(cmd).replace(
            "plasma-discover-notifier", ""))

    @patch("dnf_gui.core.discover_manager.DiscoverManager.is_notifier_running",
           return_value=False)
    def test_status_does_not_raise(self, _mock):
        status = self.mgr.get_status()
        self.assertIsInstance(status.per_user_disabled, bool)


if __name__ == "__main__":
    unittest.main()


class TestSystemWideDiscoverTakeover(unittest.TestCase):
    def setUp(self):
        self.mgr = DiscoverManager()

    def _script(self, cmds):
        self.assertEqual(len(cmds), 1)
        self.assertEqual(cmds[0][:3], ["pkexec", "bash", "-c"])
        import subprocess
        check = subprocess.run(["bash", "-n", "-c", cmds[0][3]])
        self.assertEqual(check.returncode, 0, "generated script has a syntax error")
        return cmds[0][3]

    def test_disable_masks_unit_instead_of_deleting_package_file(self):
        from dnf_gui.core import discover_manager as dm
        script = self._script(self.mgr.build_system_disable_commands())
        self.assertIn(f"systemctl --global mask {dm.NOTIFIER_UNIT}", script)
        self.assertIn("systemctl mask packagekit-offline-update.service", script)
        self.assertNotIn("rm -f /etc/xdg/autostart", script)
        # Never clobbers an admin's own system-wide Discover config.
        self.assertIn(f"grep -qF '{dm.MANAGED_MARKER}'", script)

    def test_enable_undoes_everything(self):
        from dnf_gui.core import discover_manager as dm
        script = self._script(self.mgr.build_system_enable_commands())
        self.assertIn(f"systemctl --global unmask {dm.NOTIFIER_UNIT}", script)
        self.assertIn("systemctl unmask packagekit-offline-update.service", script)
        self.assertIn("reinstall -y plasma-discover-notifier", script)

    def test_status_detects_global_mask(self):
        from dnf_gui.core import discover_manager as dm
        from dnf_gui.core.discover_manager import DiscoverStatus
        status = DiscoverStatus(discover_installed=True, system_autostart_present=True)
        with patch.object(dm.os.path, "islink", return_value=True), \
             patch.object(dm.os, "readlink", return_value="/dev/null"):
            self.assertTrue(DiscoverManager._is_system_disabled(status))
        with patch.object(dm.os.path, "islink", return_value=False):
            self.assertFalse(DiscoverManager._is_system_disabled(status))
            legacy = DiscoverStatus(discover_installed=True, system_autostart_present=False)
            self.assertTrue(DiscoverManager._is_system_disabled(legacy))


class TestRestartUpdateCancel(unittest.TestCase):
    def test_detects_only_packagekit_trigger(self):
        from dnf_gui.core import discover_manager as dm
        with patch.object(dm.os.path, "islink", return_value=True), \
             patch.object(dm.os, "readlink", return_value="/var/lib/PackageKit/prepared-update"):
            self.assertTrue(DiscoverManager.restart_update_scheduled())
        # dnf's own offline upgrades use the same trigger but point elsewhere.
        with patch.object(dm.os.path, "islink", return_value=True), \
             patch.object(dm.os, "readlink", return_value="/usr/lib/sysimage/libdnf5/offline"):
            self.assertFalse(DiscoverManager.restart_update_scheduled())
        with patch.object(dm.os.path, "islink", return_value=False):
            self.assertFalse(DiscoverManager.restart_update_scheduled())

    def test_cancel_command_and_system_disable_cancels_first(self):
        self.assertEqual(DiscoverManager.build_cancel_restart_update_command(),
                         ["pkcon", "offline-cancel"])
        script = DiscoverManager().build_system_disable_commands()[0][3]
        self.assertLess(script.index("pkcon offline-cancel"),
                        script.index("systemctl mask packagekit-offline-update"))


class TestRestartUpdateUi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _status(self, **kwargs):
        from dnf_gui.core.discover_manager import DiscoverStatus
        base = dict(discover_installed=True, system_autostart_present=True)
        base.update(kwargs)
        return DiscoverStatus(**base)

    def test_settings_warns_even_after_takeover(self):
        from dnf_gui.ui.pages.settings_page import SettingsPage
        page = SettingsPage()
        page.display_discover_status(self._status(per_user_disabled=True))
        self.assertEqual(page._discover_banner.objectName(), "status_ok")
        self.assertFalse(page._btn_cancel_restart.isVisibleTo(page))
        page.display_discover_status(self._status(per_user_disabled=True,
                                                  restart_update_scheduled=True))
        self.assertEqual(page._discover_banner.objectName(), "status_warn")
        self.assertIn("scheduled", page._discover_title.text())
        self.assertTrue(page._btn_cancel_restart.isVisibleTo(page))

    def test_takeover_offers_to_cancel_scheduled_update(self):
        from PyQt6.QtWidgets import QMessageBox
        from dnf_gui.ui.main_window import MainWindow
        win = MainWindow()
        with patch.object(QMessageBox, "question",
                          return_value=QMessageBox.StandardButton.Yes) as ask, \
             patch.object(QMessageBox, "information"), \
             patch.object(win._discover_manager, "restart_update_scheduled", return_value=True), \
             patch.object(win._discover_manager, "set_per_user_enabled"), \
             patch("subprocess.run"), \
             patch.object(win, "_run_command") as run:
            win._discover_takeover()
        self.assertEqual(ask.call_count, 2)  # takeover, then cancel?
        run.assert_called_once_with(["pkcon", "offline-cancel"],
                                    "Cancelling Discover's restart update")
