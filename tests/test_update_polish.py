"""Tests for upgrade previews and reboot detection."""

import subprocess
import unittest
from unittest.mock import patch, MagicMock

from dnf_gui.core.package import UpgradePreview
from dnf_gui.core.dnf_backend import DNFBackend


def _backend():
    with patch("shutil.which", return_value="/usr/bin/dnf5"):
        return DNFBackend()


class TestUpgradePreviewModel(unittest.TestCase):
    def test_defaults(self):
        p = UpgradePreview()
        self.assertFalse(p.has_preview)
        self.assertEqual(p.count, 0)


class TestGetUpgradePreview(unittest.TestCase):
    def test_parses_rows_and_sums_sizes(self):
        backend = _backend()
        output = ("firefox 125.0-1.fc44 x86_64 842853\n"
                  "kernel-core 6.18.5-200.fc44 x86_64 168236\n")
        with patch.object(DNFBackend, "_run", return_value=output) as mock_run:
            preview = backend.get_upgrade_preview()
        self.assertEqual(preview.count, 2)
        self.assertEqual(preview.total_bytes, 842853 + 168236)
        self.assertTrue(preview.sizes_known)
        self.assertTrue(preview.has_preview)

    def test_security_flag_passes_through(self):
        backend = _backend()
        seen = {}

        def fake_run(cmd, allow_nonzero=False):
            seen["cmd"] = cmd
            return ""

        with patch.object(DNFBackend, "_run", side_effect=fake_run):
            backend.get_upgrade_preview(security_only=True)
        self.assertIn("--security", seen["cmd"])
        self.assertIn("--upgrades", seen["cmd"])

    def test_tolerates_garbage_and_unknown_sizes(self):
        backend = _backend()
        output = ("Last metadata expiration check...\n"
                  "firefox 125.0-1.fc44 x86_64 %{downloadsize}\n"
                  "broken-line\n"
                  "bash 5.2-1.fc44 x86_64 1024\n")
        with patch.object(DNFBackend, "_run", return_value=output):
            preview = backend.get_upgrade_preview()
        self.assertEqual(preview.count, 2)  # firefox + bash counted
        self.assertEqual(preview.total_bytes, 1024)
        self.assertTrue(preview.sizes_known)

    def test_empty_on_backend_failure(self):
        backend = _backend()
        with patch.object(DNFBackend, "_run", return_value=None):
            preview = backend.get_upgrade_preview()
        self.assertFalse(preview.has_preview)
        self.assertEqual(preview.total_bytes, 0)


class TestRebootRequired(unittest.TestCase):
    def test_needs_restarting_rc1_means_reboot(self):
        backend = _backend()
        with patch("dnf_gui.core.dnf_backend.subprocess.run",
                   return_value=MagicMock(returncode=1)):
            self.assertTrue(backend.reboot_required())

    def test_needs_restarting_rc0_means_no_reboot(self):
        backend = _backend()
        with patch("dnf_gui.core.dnf_backend.subprocess.run",
                   return_value=MagicMock(returncode=0)):
            self.assertFalse(backend.reboot_required())

    def test_sentinel_file_means_reboot(self):
        backend = _backend()

        def fake_run(cmd, **kwargs):
            if cmd[0] == "needs-restarting":
                raise FileNotFoundError()
            raise AssertionError("should not reach rpm query")

        with patch("dnf_gui.core.dnf_backend.subprocess.run", side_effect=fake_run):
            with patch("dnf_gui.core.dnf_backend.os.path.exists",
                       return_value=True):
                self.assertTrue(backend.reboot_required())

    def test_kernel_drift_means_reboot(self):
        backend = _backend()

        def fake_run(cmd, **kwargs):
            if cmd[0] == "needs-restarting":
                raise FileNotFoundError()
            if cmd[0] == "rpm":
                return MagicMock(returncode=0,
                                 stdout="6.18.5-200.fc44.x86_64\n")
            raise AssertionError(f"unexpected {cmd}")

        with patch("dnf_gui.core.dnf_backend.subprocess.run", side_effect=fake_run):
            with patch("dnf_gui.core.dnf_backend.os.path.exists",
                       return_value=False):
                with patch("dnf_gui.core.dnf_backend.platform.release",
                           return_value="6.17.1-100.fc44.x86_64"):
                    self.assertTrue(backend.reboot_required())

    def test_matching_kernel_means_no_reboot(self):
        backend = _backend()

        def fake_run(cmd, **kwargs):
            if cmd[0] == "needs-restarting":
                raise FileNotFoundError()
            if cmd[0] == "rpm":
                return MagicMock(returncode=0,
                                 stdout="6.18.5-200.fc44.x86_64\n")
            raise AssertionError(f"unexpected {cmd}")

        with patch("dnf_gui.core.dnf_backend.subprocess.run", side_effect=fake_run):
            with patch("dnf_gui.core.dnf_backend.os.path.exists",
                       return_value=False):
                with patch("dnf_gui.core.dnf_backend.platform.release",
                           return_value="6.18.5-200.fc44.x86_64"):
                    self.assertFalse(backend.reboot_required())

    def test_never_raises(self):
        backend = _backend()
        with patch("dnf_gui.core.dnf_backend.subprocess.run",
                   side_effect=subprocess.TimeoutExpired("x", 1)):
            self.assertFalse(backend.reboot_required())


if __name__ == "__main__":
    unittest.main()
