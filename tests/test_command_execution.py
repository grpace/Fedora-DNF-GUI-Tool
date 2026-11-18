"""Tests for command execution, worker lifecycle, cancellation, and the
passwordless sudo -n → pkexec fallback."""

import gc
import os
import time
import unittest
from unittest.mock import patch

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication

os.environ["QT_QPA_PLATFORM"] = "offscreen"


def _controller():
    # Free controllers left by earlier tests now, while none of their
    # threads run: a later processEvents() would otherwise fire their
    # pending start-up timers and GC could destroy a running QThread.
    gc.collect()
    from dnf_gui.ui.controllers.app_controller import AppController
    return AppController()


def _wait(predicate, timeout=2.5):
    app = QApplication.instance()
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        time.sleep(0.05)
        app.processEvents()
    return predicate()


class TestCommandWorkerExecution(unittest.TestCase):
    def test_start_worker_runs_without_attribute_error(self):
        """_start runs the command and reports its exit code."""
        app = _controller()
        done = []
        app.runner._start(["echo", "hello_world"], done.append)
        self.assertTrue(_wait(lambda: done), "Worker should have invoked callback")
        self.assertEqual(done, [0])
        self.assertIn("hello_world", app.runner.text())

    def test_cancel_button_cancels_running_command(self):
        """Cancel terminates the process group and marks the run cancelled."""
        app = _controller()
        app.runner.run(["sleep", "10"], "Test sleep cancellation")
        self.assertTrue(app.runner.busy)  # the Cancel button is offered

        time.sleep(0.15)
        QApplication.instance().processEvents()
        app.runner.cancel()

        self.assertTrue(_wait(lambda: app.runner.worker is None),
                        "Worker should be cleared after cancel")
        self.assertIn("cancelled", app.runner.text().lower())
        self.assertEqual(app.runner.status, "cancelled")
        self.assertFalse(app.runner.busy)


class _FakeWorker(QObject):
    """Stands in for CommandWorker: records argv, finishes synchronously."""

    output_line = pyqtSignal(str)
    finished = pyqtSignal(int)
    error = pyqtSignal(str)
    started_argvs: list = []
    script = None  # argv -> (lines, exit code)

    def __init__(self, command, parent=None):
        super().__init__(parent)
        self._command = list(command)

    def isRunning(self):  # noqa: N802 - Qt API
        return False

    def start(self):
        _FakeWorker.started_argvs.append(self._command)
        lines, code = _FakeWorker.script(self._command)
        for line in lines:
            self.output_line.emit(line)
        self.finished.emit(code)


class TestPasswordlessFallback(unittest.TestCase):
    """pkexec is swapped for sudo -n only for covered argv, and a sudo that
    still wants a password falls back to pkexec exactly once."""

    def setUp(self):
        self.app = _controller()
        self.addCleanup(setattr, self.app.settings, "passwordless_scope", "off")
        _FakeWorker.started_argvs = []
        # A successful "System Upgrade" rechecks the reboot banner (real dnf).
        for patcher in (patch("dnf_gui.ui.controllers.runner.CommandWorker", _FakeWorker),
                        patch.object(self.app.updates, "recheck_reboot")):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.cmd = self.app.backend.build_upgrade_command()
        self.assertEqual(self.cmd[0], "pkexec")

    def _run(self, scope, script):
        self.app.settings.passwordless_scope = scope
        _FakeWorker.script = staticmethod(script)
        finished = []
        self.app.runner.finished.connect(lambda *a: finished.append(a))
        self.app.runner.run(self.cmd, "System Upgrade")
        return finished

    def test_off_scope_uses_pkexec(self):
        self._run("off", lambda argv: ([], 0))
        self.assertEqual(_FakeWorker.started_argvs, [self.cmd])

    def test_covered_command_uses_sudo_n(self):
        finished = self._run("updates", lambda argv: ([], 0))
        self.assertEqual(_FakeWorker.started_argvs, [["/usr/bin/sudo", "-n"] + self.cmd[1:]])
        self.assertEqual(finished, [(0, "System Upgrade", False)])

    def test_sudo_password_prompt_retries_once_with_pkexec(self):
        def script(argv):
            if argv[0].endswith("/sudo"):
                return (["sudo: a password is required"], 1)
            return ([], 0)
        finished = self._run("updates", script)
        self.assertEqual(_FakeWorker.started_argvs,
                         [["/usr/bin/sudo", "-n"] + self.cmd[1:], self.cmd])
        self.assertEqual(finished, [(0, "System Upgrade", False)])
        self.assertIn("falling back to password prompt", self.app.runner.text())

    def test_pkexec_failure_after_fallback_is_not_retried_again(self):
        finished = self._run("updates", lambda argv: (["sudo: a password is required"], 1))
        self.assertEqual(len(_FakeWorker.started_argvs), 2)
        self.assertEqual(finished, [(1, "System Upgrade", False)])

    def test_other_sudo_failures_are_not_retried(self):
        finished = self._run("updates", lambda argv: (["Error: no space left"], 1))
        self.assertEqual(_FakeWorker.started_argvs, [["/usr/bin/sudo", "-n"] + self.cmd[1:]])
        self.assertEqual(finished, [(1, "System Upgrade", False)])

    def test_uncovered_command_keeps_pkexec(self):
        self.app.settings.passwordless_scope = "updates"
        _FakeWorker.script = staticmethod(lambda argv: ([], 0))
        cmd = self.app.backend.build_install_command("htop")
        self.app.runner.run(cmd, "Installing htop")
        self.assertEqual(_FakeWorker.started_argvs, [cmd])


if __name__ == "__main__":
    unittest.main()
