"""Tests for Discover takeover, security summaries, and combined updates."""

import unittest
from unittest.mock import patch, MagicMock

from dnf_gui.core.security import (
    SecuritySummary,
    build_security_update_command,
    build_update_everything_command,
    get_security_summary,
)
from dnf_gui.core.discover_manager import DiscoverManager


class TestSecuritySummary(unittest.TestCase):
    def test_urgent_flags(self):
        sec = SecuritySummary(total=2, critical=1)
        self.assertTrue(sec.has_security_updates)
        self.assertTrue(sec.urgent)
        calm = SecuritySummary(total=1, moderate=1)
        self.assertTrue(calm.has_security_updates)
        self.assertFalse(calm.urgent)
        empty = SecuritySummary()
        self.assertFalse(empty.has_security_updates)

    def test_build_commands(self):
        sec_cmd = build_security_update_command()
        self.assertIn("--security", sec_cmd)
        self.assertIn("pkexec", sec_cmd)
        everything = build_update_everything_command()
        self.assertEqual(everything[0], "pkexec")
        self.assertIn("bash", everything)
        # Chained script must mention both dnf and flatpak
        self.assertIn("flatpak", everything[-1])
        self.assertIn("upgrade", everything[-1])

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
        self.assertIsInstance(status.effectively_quiet, bool)


if __name__ == "__main__":
    unittest.main()
