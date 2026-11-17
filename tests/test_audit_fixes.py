"""Regression tests for the audit fixes (self-update, command guard, firmware,
passwordless rule install)."""

import gc
import subprocess
import time
import unittest
from unittest.mock import patch

from PyQt6.QtWidgets import QApplication

from dnf_gui.core.updater import _asset_sha256, _is_safe_download_url
from tests.conftest import answer


def _controller():
    # Free controllers left by earlier tests now, while none of their
    # threads run: a later processEvents() would otherwise fire their
    # pending start-up timers and GC could destroy a running QThread.
    gc.collect()
    from dnf_gui.ui.controllers.app_controller import AppController
    return AppController()


def _wait(predicate, timeout=2.0):
    app = QApplication.instance()
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        time.sleep(0.05)
        app.processEvents()
    return predicate()


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
    def test_second_command_refused_while_running(self):
        app = _controller()
        shown = answer(app)
        self.assertTrue(app.runner.run(["sleep", "0.5"], "first"))
        first = app.runner.worker
        self.assertFalse(app.runner.run(["echo", "second"], "second"))
        self.assertEqual([p.title for p in shown], ["Operation in Progress"])
        self.assertIs(app.runner.worker, first)
        self.assertTrue(_wait(lambda: app.runner.worker is None))

    def test_missing_binary_finishes_through_done_path(self):
        app = _controller()
        done = []
        app.runner._start(["/nonexistent/binary-xyz"], done.append)
        _wait(lambda: done)
        self.assertEqual(done, [-1])
        self.assertIsNone(app.runner.worker)


class TestPasswordlessEnable(unittest.TestCase):
    """The sudoers rule is visudo-checked before anything runs, and the
    scope is only remembered once the install command succeeded."""

    def setUp(self):
        from dnf_gui.core import passwordless as pw
        self.pw = pw
        # Never run the real `sudo -n -l` status probe.
        for p in (patch.object(pw, "current_user", return_value="alice"),
                  patch.object(pw, "live_status", return_value=("off", False, True))):
            p.start()
            self.addCleanup(p.stop)
        self.app = _controller()
        self.app.settings.passwordless_scope = "off"
        self.addCleanup(setattr, self.app.settings, "passwordless_scope", "off")

    def _enable(self, scope, *choices, valid=True):
        shown = answer(self.app, *choices)
        with patch.object(self.pw, "validate_content",
                          return_value=(valid, "" if valid else "syntax error")) as check, \
                patch.object(self.app.runner, "run") as run:
            self.app.settings_controller.enablePasswordless(scope)
        return shown, check, run

    def test_declined_runs_nothing(self):
        shown, check, run = self._enable("updates", "no")
        run.assert_not_called()
        check.assert_not_called()
        self.assertEqual(shown[0].title, "Turn On Passwordless Updates?")
        self.assertEqual(self.app.settings.passwordless_scope, "off")

    def test_validation_failure_runs_nothing(self):
        shown, check, run = self._enable("updates", "yes", valid=False)
        check.assert_called_once()
        run.assert_not_called()
        self.assertEqual(shown[-1].title, "Validation Failed")
        self.assertEqual(self.app.settings.passwordless_scope, "off")

    def test_installs_validated_rule_and_saves_scope_only_on_success(self):
        _, check, run = self._enable("updates", "yes")
        content = self.pw.build_rule_content(
            "alice", "updates", self.app.settings.held_back_patterns)
        check.assert_called_once_with(content)
        run.assert_called_once_with(self.pw.build_install_commands(content),
                                    "Enabling passwordless updates")
        # Nothing is remembered until the privileged step finishes.
        self.assertEqual(self.app.settings.passwordless_scope, "off")
        self.app._on_operation_finished(0, "Enabling passwordless updates", False)
        self.assertEqual(self.app.settings.passwordless_scope, "updates")

    def test_failed_install_keeps_scope_off(self):
        self._enable("full", "yes")
        self.app._on_operation_finished(1, "Enabling passwordless updates", False)
        self.assertEqual(self.app.settings.passwordless_scope, "off")

    def test_full_scope_warns_and_defaults_to_no(self):
        shown, _, run = self._enable("full", "no")
        prompt = shown[0]
        self.assertTrue(prompt.destructive)
        self.assertEqual(prompt.default, "no")
        self.assertIn("removes every password prompt", prompt.text)
        run.assert_not_called()

    def test_disable_removes_rule_and_turns_scope_off(self):
        self.app.settings.passwordless_scope = "updates"
        answer(self.app, "yes")
        with patch.object(self.app.runner, "run") as run:
            self.app.settings_controller.disablePasswordless()
        run.assert_called_once_with(self.pw.build_remove_commands(),
                                    "Disabling passwordless updates")
        self.app._on_operation_finished(0, "Disabling passwordless updates", False)
        self.assertEqual(self.app.settings.passwordless_scope, "off")


if __name__ == "__main__":
    unittest.main()
