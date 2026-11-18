"""Fedora release upgrades: picking the target, the downloaded state, the
offer on the Updates page, and the update → download → restart flow."""

import unittest
from unittest.mock import patch

from dnf_gui.core import release_upgrade as ru
from dnf_gui.core.package import Package, PackageStatus, UpdateInfo
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
        import tempfile
        from pathlib import Path
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name, "state.toml")
        path.write_text(body)
        return str(path)

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


def _scanned(app):
    app.updates._on_checked({"dnf": UpdateInfo(packages=[
        Package(name=n, version="1", status=PackageStatus.UPDATE_AVAILABLE)
        for n in ("firefox", "kernel-core")]), "flatpak": [], "security": None})
    return app


def _no_timers():
    return patch("dnf_gui.ui.controllers.app_controller.QTimer.singleShot",
                 side_effect=lambda ms, fn: fn())


def test_notice_states(app):
    updates = _scanned(app).updates
    updates.set_release_upgrade(ru.ReleaseUpgrade(44, 45, "2027-06-02"))
    assert updates.release["visible"]
    assert "June 2, 2027" in updates.release["text"]
    with patch.object(updates, "start_release_upgrade") as start:
        updates.releasePrimary()
    start.assert_called_once_with(45)

    updates.releaseSecondary()  # Not Now
    assert app.settings.dismissed_release == 45
    assert updates.release == {}
    updates.set_release_upgrade(ru.ReleaseUpgrade(44, 45))
    assert updates.release == {}

    # A finished download shows even if the offer was dismissed.
    updates.set_release_upgrade(ru.ReleaseUpgrade(44, 45, downloaded=True))
    assert updates.release["visible"]
    with patch.object(updates, "install_release_upgrade") as install:
        updates.releasePrimary()
    install.assert_called_once_with(45)


def test_upgrade_runs_update_then_download(app):
    shown = answer(app, "yes")
    with patch.object(ru, "current_release", return_value=44), \
            patch.object(app.runner, "run_chain") as chain:
        app.updates.start_release_upgrade(45)
    assert shown[0].default == "no"
    cmds, operation = chain.call_args.args
    assert cmds == [app.backend.build_upgrade_command(),
                    ru.build_download_command(app.backend.dnf_path, 45)]
    assert operation == "Upgrade to Fedora 45"
    assert app.pending_release_target == 45


def test_upgrade_declined_runs_nothing(app):
    answer(app, "no")
    with patch.object(ru, "current_release", return_value=44), \
            patch.object(app.runner, "run_chain") as chain:
        app.updates.start_release_upgrade(45)
    chain.assert_not_called()
    assert app.pending_release_target is None


def test_successful_download_offers_restart(app):
    app.pending_release_target = 45
    with patch.object(app.updates, "install_release_upgrade") as install, \
            patch.object(ru, "current_release", return_value=44):
        app._on_operation_finished(0, "Upgrade to Fedora 45", False)
    install.assert_called_once_with(45)
    assert "downloaded" in app.updates.release["title"]
    assert app.pending_release_target is None


def test_restart_and_install_is_destructive(app):
    shown = answer(app, "yes")
    with patch.object(app.runner, "run") as run:
        app.updates.install_release_upgrade(45)
    assert shown[0].destructive and shown[0].default == "no"
    run.assert_called_once_with(ru.build_reboot_command(app.backend.dnf_path),
                                "Restarting to install Fedora 45")


def test_failed_download_offers_allowerasing(app):
    app.pending_release_target = 45
    app.runner._queue = []
    with patch.object(app.updates, "on_release_download_failed") as failed, _no_timers():
        app.runner._on_chain_step(1, "Upgrade to Fedora 45")
    failed.assert_called_once_with(45)


def test_failed_update_step_does_not_offer_allowerasing(app):
    app.pending_release_target = 45
    app.runner._queue = [["pkexec", "dnf", "system-upgrade", "download"]]
    with patch.object(app.updates, "on_release_download_failed") as failed, _no_timers():
        app.runner._on_chain_step(1, "Upgrade to Fedora 45")
    failed.assert_not_called()


def test_retry_runs_download_with_allowerasing(app):
    shown = answer(app, "yes")
    with patch.object(app.runner, "run") as run:
        app.updates.on_release_download_failed(45)
    assert shown[0].destructive
    run.assert_called_once_with(
        ru.build_download_command(app.backend.dnf_path, 45, allow_erasing=True),
        "Upgrade to Fedora 45")
    answer(app, "no")
    with patch.object(app.runner, "run") as run:
        app.updates.on_release_download_failed(45)
    run.assert_not_called()
