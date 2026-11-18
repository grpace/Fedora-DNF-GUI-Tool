"""Tests for upgrade previews and reboot detection."""

import gc
import subprocess
import unittest
from unittest.mock import patch, MagicMock

from PyQt6.QtWidgets import QApplication

from dnf_gui.core.package import UpgradePreview
from dnf_gui.core.dnf_backend import DNFBackend
from tests.conftest import answer


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
            self.assertIs(backend.check_reboot(), True)

    def test_needs_restarting_rc0_means_no_reboot(self):
        backend = _backend()
        with patch("dnf_gui.core.dnf_backend.subprocess.run",
                   return_value=MagicMock(returncode=0)):
            self.assertIsNot(backend.check_reboot(), True)

    def test_sentinel_file_means_reboot(self):
        backend = _backend()

        def fake_run(cmd, **kwargs):
            if "needs-restarting" in cmd:  # dnf5 built-in and legacy binary
                raise FileNotFoundError()
            raise AssertionError("should not reach rpm query")

        with patch("dnf_gui.core.dnf_backend.subprocess.run", side_effect=fake_run):
            with patch("dnf_gui.core.dnf_backend.os.path.exists",
                       return_value=True):
                self.assertIs(backend.check_reboot(), True)

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
                    self.assertIs(backend.check_reboot(), True)

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
                    self.assertIsNot(backend.check_reboot(), True)

    def test_dnf4_skips_the_dnf_subcommand(self):
        backend = _backend()
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return MagicMock(returncode=0)

        with patch.object(DNFBackend, "is_dnf5", False), \
                patch("dnf_gui.core.dnf_backend.subprocess.run", side_effect=fake_run):
            self.assertIsNot(backend.check_reboot(), True)
        self.assertEqual(calls, [["needs-restarting", "-r"]])

    def test_never_raises(self):
        backend = _backend()
        with patch("dnf_gui.core.dnf_backend.subprocess.run",
                   side_effect=subprocess.TimeoutExpired("x", 1)):
            self.assertIsNot(backend.check_reboot(), True)


def _controller():
    # Free controllers left by earlier tests now, while none of their
    # threads run: a later processEvents() would otherwise fire their
    # pending start-up timers and GC could destroy a running QThread.
    gc.collect()
    from dnf_gui.ui.controllers.app_controller import AppController
    return AppController()


class TestFailedUpdateCheck(unittest.TestCase):
    """An offline scan must not claim the system is up to date."""

    def test_failed_check_is_not_up_to_date(self):
        from dnf_gui.core.package import UpdateInfo
        app = _controller()
        app.set_update_badge(5)
        app.updates._on_checked({"dnf": UpdateInfo(check_failed=True),
                                 "flatpak": [], "security": None})
        updates = app.updates
        self.assertEqual(updates.phase, "failed")
        self.assertIn("Couldn't Check", updates.headline)
        self.assertNotIn("up to date", (updates.headline + updates.summary).lower())
        self.assertEqual(app.updateBadge, 5)  # unknown, not zero
        self.assertIsNone(updates._cache)  # next visit rescans


class TestCloseDuringOperation(unittest.TestCase):
    """Closing mid-operation must not exit: dnf writes to our pipe."""

    def setUp(self):
        from PyQt6.QtGui import QWindow
        self.app = _controller()
        self.window = QWindow()
        self.app.set_window(self.window)
        self.window.show()
        self.addCleanup(self.window.hide)
        self.addCleanup(QApplication.instance().setQuitOnLastWindowClosed, True)

    def _close(self, *choices):
        shown = answer(self.app, *choices)
        with patch.object(self.app.runner, "running", return_value=True):
            accepted = self.app.requestClose()
        return accepted, shown

    def test_close_hides_and_keeps_running(self):
        accepted, shown = self._close("yes")
        self.assertFalse(accepted)
        self.assertEqual(shown[0].title, "Operation Still Running")
        self.assertFalse(self.window.isVisible())
        self.assertFalse(QApplication.instance().quitOnLastWindowClosed())
        # A failure brings the window back with the output.
        self.app._operation_finished(failed=True)
        self.assertTrue(self.window.isVisible())
        self.assertTrue(QApplication.instance().quitOnLastWindowClosed())
        self.assertTrue(self.app.activityExpanded)

    def test_keep_open_keeps_window(self):
        accepted, _ = self._close("no")
        self.assertFalse(accepted)
        self.assertTrue(self.window.isVisible())
        self.assertFalse(self.app._quit_when_done)

    def test_close_when_idle_is_allowed(self):
        shown = answer(self.app)
        with patch.object(self.app, "shutdown_threads") as shutdown:
            self.assertTrue(self.app.requestClose())
        shutdown.assert_called_once()
        self.assertEqual(shown, [])

    def test_success_quits_once_done(self):
        self._close("yes")
        with patch.object(QApplication, "quit") as quit_app, \
                patch("dnf_gui.ui.controllers.app_controller.QTimer.singleShot",
                      side_effect=lambda ms, fn: fn()):
            self.app._operation_finished(failed=False)
        quit_app.assert_called_once()

    def test_background_success_notification_is_not_clickable(self):
        self._close("yes")
        with patch.object(self.app.notifier, "send") as notify:
            self.app._notify_if_unfocused(0, "System Upgrade")
        self.assertFalse(notify.call_args.args[0].clickable)


if __name__ == "__main__":
    unittest.main()
