"""Tests for Fedora release upgrades and per-row Hold back / Release."""

import gc
import os
import tempfile
import unittest
from unittest.mock import patch

from dnf_gui.core import release_upgrade as ru
from dnf_gui.core.package import Package, PackageStatus, UpdateInfo
from dnf_gui.core import passwordless as pw
from tests.conftest import answer

RELEASES = [
    {"name": "F43", "version": "43", "state": "current", "eol": "2026-12-02"},
    {"name": "F44", "version": "44", "state": "current", "eol": "2027-06-02"},
    {"name": "F45", "version": "45", "state": "frozen", "eol": "2027-11-24"},
    {"name": "F46", "version": "46", "state": "pending", "eol": "2028-05-24"},
]


class TestPickTarget(unittest.TestCase):
    def test_betas_are_never_offered(self):
        self.assertEqual(ru.pick_target(44, RELEASES), (None, "2027-06-02"))

    def test_newest_current_release_within_two(self):
        releases = RELEASES[:2] + [dict(RELEASES[2], state="current")]
        self.assertEqual(ru.pick_target(43, releases)[0], 45)
        self.assertEqual(ru.pick_target(44, releases)[0], 45)
        self.assertEqual(ru.pick_target(42, releases)[0], 44)  # 45 is 3 ahead

    def test_fetch_filters_non_fedora(self):
        payload = {"releases": RELEASES + [
            {"name": "EPEL-10", "version": "10", "state": "current", "id_prefix": "FEDORA-EPEL"},
            {"name": "F45C", "version": "45", "state": "current", "id_prefix": "FEDORA-CONTAINER"}]}
        for rel in payload["releases"][:4]:
            rel["id_prefix"] = "FEDORA"
        import io
        import json
        with patch("urllib.request.urlopen",
                   return_value=io.BytesIO(json.dumps(payload).encode())):
            names = [r["name"] for r in ru.fetch_releases()]
        self.assertEqual(names, ["F43", "F44", "F45", "F46"])

    def test_fetch_failure_is_empty(self):
        with patch("urllib.request.urlopen", side_effect=OSError("offline")):
            self.assertEqual(ru.fetch_releases(), [])


class TestDownloadedState(unittest.TestCase):
    def _state(self, body):
        fd, path = tempfile.mkstemp(suffix=".toml")
        with os.fdopen(fd, "w") as f:
            f.write(body)
        self.addCleanup(os.unlink, path)
        return path

    def test_download_complete(self):
        path = self._state('[offline-transaction-state]\nstatus = "download-complete"\n'
                           'target_releasever = "45"\nverb = "system-upgrade download"\n')
        self.assertEqual(ru.downloaded_release(path), 45)

    def test_incomplete_or_other_verbs_ignored(self):
        self.assertIsNone(ru.downloaded_release(self._state(
            '[offline-transaction-state]\nstatus = "download-incomplete"\n'
            'target_releasever = "45"\nverb = "system-upgrade download"\n')))
        self.assertIsNone(ru.downloaded_release(self._state(
            '[offline-transaction-state]\nstatus = "download-complete"\n'
            'target_releasever = "44"\nverb = "offline upgrade"\n')))
        self.assertIsNone(ru.downloaded_release("/nonexistent/state.toml"))

    def test_check_prefers_downloaded(self):
        with patch.object(ru, "current_release", return_value=44), \
             patch.object(ru, "downloaded_release", return_value=45), \
             patch.object(ru, "fetch_releases", return_value=[]):
            upgrade = ru.check_release_upgrade()
        self.assertEqual((upgrade.target, upgrade.downloaded), (45, True))

    def test_commands(self):
        self.assertEqual(ru.build_download_command("/usr/bin/dnf5", 45),
                         ["pkexec", "/usr/bin/dnf5", "system-upgrade", "download",
                          "--releasever=45", "-y"])
        self.assertIn("--allowerasing",
                      ru.build_download_command("/usr/bin/dnf5", 45, allow_erasing=True))
        self.assertEqual(ru.build_reboot_command("dnf")[-2:], ["system-upgrade", "reboot"])


class TestPasswordlessCoverage(unittest.TestCase):
    OUT = ("    (root) NOPASSWD: /usr/bin/dnf5 upgrade -y --refresh, "
           "/usr/bin/dnf5 upgrade -y --refresh --exclude\\=kernel\\*\\,mesa-\\*, "
           "/usr/bin/dnf5 upgrade -y --security\n")

    def test_exact_list_only(self):
        self.assertTrue(pw.covers_held_back(self.OUT, ["kernel*", "mesa-*"]))
        self.assertFalse(pw.covers_held_back(self.OUT, ["kernel*"]))
        self.assertFalse(pw.covers_held_back(self.OUT, ["kernel*", "mesa-*", "firefox"]))
        self.assertTrue(pw.covers_held_back(self.OUT.replace("\\", ""), ["kernel*", "mesa-*"]))


def _controller(test):
    # Free controllers left by earlier tests now, while none of their
    # threads run: a later processEvents() would otherwise fire their
    # pending start-up timers and GC could destroy a running QThread.
    gc.collect()
    from dnf_gui.ui.controllers.app_controller import AppController
    app = AppController()
    settings = app.settings
    saved = (settings.held_back_patterns, settings.dismissed_release,
             settings.passwordless_scope)

    def restore():
        (settings.held_back_patterns, settings.dismissed_release,
         settings.passwordless_scope) = saved
    test.addCleanup(restore)
    settings.dismissed_release = 0
    settings.passwordless_scope = "off"
    return app


def _scanned(test):
    app = _controller(test)
    app.updates._on_checked({"dnf": UpdateInfo(packages=[
        Package(name=n, version="1", status=PackageStatus.UPDATE_AVAILABLE)
        for n in ("firefox", "kernel-core")]), "flatpak": [], "security": None})
    return app


class TestUpdatesReleaseAndHold(unittest.TestCase):
    def test_banner_states(self):
        app = _scanned(self)
        updates = app.updates
        updates.set_release_upgrade(ru.ReleaseUpgrade(44, 45, "2027-06-02"))
        self.assertTrue(updates.release["visible"])
        self.assertIn("June 2, 2027", updates.release["text"])
        with patch.object(updates, "start_release_upgrade") as start:
            updates.releasePrimary()
        start.assert_called_once_with(45)

        updates.releaseSecondary()  # Not Now
        self.assertEqual(app.settings.dismissed_release, 45)
        self.assertEqual(updates.release, {})
        updates.set_release_upgrade(ru.ReleaseUpgrade(44, 45))
        self.assertEqual(updates.release, {})

        # A finished download shows even if the offer was dismissed.
        updates.set_release_upgrade(ru.ReleaseUpgrade(44, 45, downloaded=True))
        self.assertTrue(updates.release["visible"])
        with patch.object(updates, "install_release_upgrade") as install:
            updates.releasePrimary()
        install.assert_called_once_with(45)

    def test_hold_buttons(self):
        app = _scanned(self)
        model = app.updates.model
        firefox = model.find("name", "firefox")
        self.assertEqual(firefox["majorActionLabel"], "Treat as Major")
        self.assertTrue(firefox["canToggleMajor"])
        self.assertFalse(model.find("name", "kernel-core")["canToggleMajor"])  # kernel*

        app.updates.toggleMajor("firefox")
        self.assertIn("firefox", app.settings.held_back_patterns)
        firefox = model.find("name", "firefox")
        self.assertTrue(firefox["major"])
        self.assertEqual(firefox["majorActionLabel"], "Don't Treat as Major")
        self.assertIn("You marked this as major", firefox["majorReason"])

        app.updates.toggleMajor("firefox")
        self.assertNotIn("firefox", app.settings.held_back_patterns)
        self.assertFalse(model.find("name", "firefox")["major"])


class TestControllerReleaseAndHold(unittest.TestCase):
    def test_toggle_hold_persists(self):
        app = _controller(self)
        app.settings_controller.toggle_hold("firefox", True)
        self.assertIn("firefox", app.settings.held_back_patterns)
        self.assertIn("firefox", app.updates.held_back_patterns)
        app.settings_controller.toggle_hold("firefox", False)
        self.assertNotIn("firefox", app.settings.held_back_patterns)
        self.assertNotIn("firefox", app.updates.held_back_patterns)

    def test_upgrade_runs_update_then_download(self):
        app = _controller(self)
        shown = answer(app, "yes")
        with patch.object(ru, "current_release", return_value=44), \
             patch.object(app.runner, "run_chain") as chain:
            app.updates.start_release_upgrade(45)
        self.assertEqual(shown[0].default, "no")
        cmds, operation = chain.call_args.args
        self.assertEqual(cmds[0][2:4], ["upgrade", "-y"])
        self.assertEqual(cmds[1][2:5], ["system-upgrade", "download", "--releasever=45"])
        self.assertEqual(operation, "Upgrade to Fedora 45")
        self.assertEqual(app.pending_release_target, 45)

    def test_upgrade_declined_runs_nothing(self):
        app = _controller(self)
        answer(app, "no")
        with patch.object(ru, "current_release", return_value=44), \
             patch.object(app.runner, "run_chain") as chain:
            app.updates.start_release_upgrade(45)
        chain.assert_not_called()
        self.assertIsNone(app.pending_release_target)

    def test_successful_download_offers_restart(self):
        app = _controller(self)
        app.pending_release_target = 45
        with patch.object(app.updates, "install_release_upgrade") as install, \
             patch.object(ru, "current_release", return_value=44):
            app._on_operation_finished(0, "Upgrade to Fedora 45", False)
        install.assert_called_once_with(45)
        self.assertIn("downloaded", app.updates.release["title"])
        self.assertIsNone(app.pending_release_target)

    def test_restart_and_install_is_destructive(self):
        app = _controller(self)
        shown = answer(app, "yes")
        with patch.object(app.runner, "run") as run:
            app.updates.install_release_upgrade(45)
        self.assertTrue(shown[0].destructive)
        self.assertEqual(shown[0].default, "no")
        run.assert_called_once_with(ru.build_reboot_command(app.backend.dnf_path),
                                    "Restarting to install Fedora 45")

    def test_failed_download_offers_allowerasing(self):
        app = _controller(self)
        app.pending_release_target = 45
        app.runner._queue = []
        with patch.object(app.updates, "on_release_download_failed") as failed, \
                patch("dnf_gui.ui.controllers.app_controller.QTimer.singleShot",
                      side_effect=lambda ms, fn: fn()):
            app.runner._on_chain_step(1, "Upgrade to Fedora 45")
        failed.assert_called_once_with(45)

    def test_failed_regular_update_step_does_not_offer_allowerasing(self):
        app = _controller(self)
        app.pending_release_target = 45
        app.runner._queue = [["pkexec", "dnf", "system-upgrade", "download"]]
        with patch.object(app.updates, "on_release_download_failed") as failed, \
                patch("dnf_gui.ui.controllers.app_controller.QTimer.singleShot",
                      side_effect=lambda ms, fn: fn()):
            app.runner._on_chain_step(1, "Upgrade to Fedora 45")
        failed.assert_not_called()

    def test_retry_runs_download_with_allowerasing(self):
        app = _controller(self)
        shown = answer(app, "yes")
        with patch.object(app.runner, "run") as run:
            app.updates.on_release_download_failed(45)
        self.assertTrue(shown[0].destructive)
        run.assert_called_once_with(
            ru.build_download_command(app.backend.dnf_path, 45, allow_erasing=True),
            "Upgrade to Fedora 45")
        answer(app, "no")
        with patch.object(app.runner, "run") as run:
            app.updates.on_release_download_failed(45)
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
