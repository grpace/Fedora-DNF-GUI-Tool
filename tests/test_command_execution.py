"""Tests for command execution, worker lifecycle, cancellation, and passwordless flow."""

import os
import sys
import time
import unittest
from PyQt6.QtWidgets import QApplication

os.environ["QT_QPA_PLATFORM"] = "offscreen"


class TestCommandWorkerExecution(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_start_worker_runs_without_attribute_error(self):
        """Ensure _start_worker does not crash on missing input_submitted signal."""
        from dnf_gui.ui.main_window import MainWindow

        win = MainWindow()
        done_called = False
        exit_code = None

        def _on_done(code):
            nonlocal done_called, exit_code
            done_called = True
            exit_code = code

        win._start_worker(["echo", "hello_world"], _on_done)
        for _ in range(40):
            time.sleep(0.05)
            self.app.processEvents()
            if done_called:
                break

        self.assertTrue(done_called, "Worker should have invoked callback")
        self.assertEqual(exit_code, 0)

    def test_cancel_button_cancels_running_command(self):
        """Ensure clicking the Cancel button terminates the process group and marks cancelled."""
        from dnf_gui.ui.main_window import MainWindow

        win = MainWindow()
        win._run_command(["sleep", "10"], "Test sleep cancellation")
        self.assertTrue(win._terminal_page._cancel_btn.isEnabled())

        time.sleep(0.15)
        self.app.processEvents()

        # Click cancel
        win._terminal_page._cancel_btn.click()

        for _ in range(50):
            time.sleep(0.05)
            self.app.processEvents()
            if win._command_worker is None:
                break

        self.assertIsNone(win._command_worker, "Worker should be cleared after cancel")
        terminal_text = win._terminal_page._terminal.toPlainText()
        self.assertIn("cancelled", terminal_text.lower())
