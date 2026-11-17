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
        with patch.object(DNFBackend, "_run", return_value=output):
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
            if "needs-restarting" in cmd:  # dnf5 built-in and legacy binary
                raise FileNotFoundError()
            raise AssertionError("should not reach rpm query")

        with patch("dnf_gui.core.dnf_backend.subprocess.run", side_effect=fake_run):
            with patch("dnf_gui.core.dnf_backend.os.path.exists",
                       return_value=True):
                self.assertTrue(backend.reboot_required())

    def test_kernel_drift_means_reboot(self):
        backend = _backend()

        def fake_run(cmd, **kwargs):
            if "needs-restarting" in cmd:  # dnf5 built-in and legacy binary
                raise FileNotFoundError()
            if cmd[0] == "rpm":
                return MagicMock(returncode=0,
                                 stdout="1760000000 6.18.5-200.fc44.x86_64\n"
                                        "1750000000 6.17.1-100.fc44.x86_64\n")
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
            if "needs-restarting" in cmd:  # dnf5 built-in and legacy binary
                raise FileNotFoundError()
            if cmd[0] == "rpm":
                return MagicMock(returncode=0,
                                 stdout="1760000000 6.18.5-200.fc44.x86_64\n"
                                        "1750000000 6.17.1-100.fc44.x86_64\n")
            raise AssertionError(f"unexpected {cmd}")

        with patch("dnf_gui.core.dnf_backend.subprocess.run", side_effect=fake_run):
            with patch("dnf_gui.core.dnf_backend.os.path.exists",
                       return_value=False):
                with patch("dnf_gui.core.dnf_backend.platform.release",
                           return_value="6.18.5-200.fc44.x86_64"):
                    self.assertFalse(backend.reboot_required())

    def test_dnf4_skips_the_dnf_subcommand(self):
        backend = _backend()
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return MagicMock(returncode=0)

        with patch.object(DNFBackend, "is_dnf5", False), \
                patch("dnf_gui.core.dnf_backend.subprocess.run", side_effect=fake_run):
            self.assertFalse(backend.reboot_required())
        self.assertEqual(calls, [["needs-restarting", "-r"]])

    def test_never_raises(self):
        backend = _backend()
        with patch("dnf_gui.core.dnf_backend.subprocess.run",
                   side_effect=subprocess.TimeoutExpired("x", 1)):
            self.assertFalse(backend.reboot_required())


if __name__ == "__main__":
    unittest.main()


class TestFailedUpdateCheck(unittest.TestCase):
    """An offline scan must not claim the system is up to date."""

    def test_failed_check_is_not_up_to_date(self):
        from dnf_gui.core.package import UpdateInfo
        from dnf_gui.ui.main_window import MainWindow
        win = MainWindow()
        win._sidebar.set_update_badge(5)
        win._on_combined_checked({"dnf": UpdateInfo(check_failed=True),
                                  "flatpak": [], "security": None})
        page = win._updates_page
        self.assertIn("Couldn't check", page._empty_label.text())
        self.assertNotIn("up to date", page._empty_label.text())
        self.assertEqual(page._last_check_card._val_label.text(), "Failed")
        self.assertIsNone(win._updates_cache)  # next visit rescans


class TestCloseDuringOperation(unittest.TestCase):
    """Closing mid-operation must not exit: dnf writes to our pipe."""

    def _close(self, win):
        from PyQt6.QtGui import QCloseEvent
        from PyQt6.QtWidgets import QMessageBox
        event = QCloseEvent()
        with patch.object(win, "_operation_running", return_value=True), \
                patch.object(QMessageBox, "question",
                             return_value=QMessageBox.StandardButton.Yes):
            win.closeEvent(event)
        return event

    def test_close_hides_and_keeps_running(self):
        from PyQt6.QtWidgets import QApplication
        from dnf_gui.ui.main_window import MainWindow
        win = MainWindow()
        win.show()
        event = self._close(win)
        self.assertFalse(event.isAccepted())
        self.assertFalse(win.isVisible())
        self.assertFalse(QApplication.instance().quitOnLastWindowClosed())
        # A failure brings the window back with the output.
        win._operation_finished(failed=True)
        self.assertTrue(win.isVisible())
        self.assertTrue(QApplication.instance().quitOnLastWindowClosed())
        from dnf_gui.ui.main_window import PAGE_TERMINAL
        self.assertEqual(win._stack.currentIndex(), PAGE_TERMINAL)
        win.hide()

    def test_success_quits_once_done(self):
        from PyQt6.QtWidgets import QApplication
        from dnf_gui.ui.main_window import MainWindow
        win = MainWindow()
        win.show()
        self._close(win)
        with patch.object(QApplication, "quit") as quit_app, \
                patch("dnf_gui.ui.main_window.QTimer.singleShot",
                      side_effect=lambda ms, fn: fn()):
            win._operation_finished()
        quit_app.assert_called_once()
        QApplication.instance().setQuitOnLastWindowClosed(True)
