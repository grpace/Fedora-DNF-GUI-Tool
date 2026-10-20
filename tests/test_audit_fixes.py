"""Regression tests for the audit fixes (self-update, command guard, firmware)."""

import subprocess
import time
import unittest
from unittest.mock import patch

from PyQt6.QtWidgets import QApplication, QMessageBox

from dnf_gui.core.updater import _asset_sha256, _is_safe_download_url


class TestUpdaterVerification(unittest.TestCase):
    def test_asset_digest_parsing(self):
        good = "sha256:" + "ab" * 32
        self.assertEqual(_asset_sha256({"digest": good}), "ab" * 32)
        self.assertEqual(_asset_sha256({"digest": "md5:abc"}), "")
        self.assertEqual(_asset_sha256({}), "")

    def test_release_asset_cdn_allowed(self):
        self.assertTrue(_is_safe_download_url(
            "https://release-assets.githubusercontent.com/x/y.rpm"))
        self.assertFalse(_is_safe_download_url("http://github.com/x.rpm"))
        self.assertFalse(_is_safe_download_url("https://evil.example/x.rpm"))

    def test_download_refuses_without_checksum(self):
        from dnf_gui.core.worker import AppUpdateDownloadWorker
        worker = AppUpdateDownloadWorker("https://github.com/a/b/x.rpm", "")
        errors = []
        worker.error.connect(errors.append)
        with patch("urllib.request.urlopen") as urlopen:
            worker.run()  # synchronous: no thread needed
        urlopen.assert_not_called()
        self.assertIn("checksum", errors[0])


class TestFirmwareCheckExitCode(unittest.TestCase):
    def test_no_updates_exit_2_is_success_and_errors_propagate(self):
        from dnf_gui.core.dnf_backend import DNFBackend
        script = DNFBackend().build_firmware_update_check_command()[2]
        for fw_rc, expected in ((0, 0), (1, 1), (2, 0), (3, 3)):
            probe = script.replace("fwupdmgr get-updates", f"(exit {fw_rc})")
            self.assertEqual(subprocess.run(["bash", "-c", probe]).returncode,
                             expected, fw_rc)


class TestCommandGuard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_second_command_refused_while_running(self):
        from dnf_gui.ui.main_window import MainWindow
        win = MainWindow()
        win._run_command(["sleep", "0.5"], "first")
        first = win._command_worker
        with patch.object(QMessageBox, "information") as info:
            win._run_command(["echo", "second"], "second")
        info.assert_called_once()
        self.assertIs(win._command_worker, first)
        for _ in range(40):
            time.sleep(0.05)
            self.app.processEvents()
            if win._command_worker is None:
                break
        self.assertIsNone(win._command_worker)

    def test_missing_binary_finishes_through_done_path(self):
        from dnf_gui.ui.main_window import MainWindow
        win = MainWindow()
        done = []
        win._start_worker(["/nonexistent/binary-xyz"], done.append)
        for _ in range(40):
            time.sleep(0.05)
            self.app.processEvents()
            if done:
                break
        self.assertEqual(done, [-1])
        self.assertIsNone(win._command_worker)


if __name__ == "__main__":
    unittest.main()
