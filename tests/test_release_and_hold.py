"""Tests for Fedora release upgrades and per-row Hold back / Release."""

import os
import tempfile
import unittest
from unittest.mock import patch

from PyQt6.QtWidgets import QApplication, QLabel, QMessageBox, QPushButton

from dnf_gui.core import release_upgrade as ru
from dnf_gui.core.package import Package, PackageStatus, UpdateInfo
from dnf_gui.core import passwordless as pw
from dnf_gui.ui.widgets.package_card import PackageCard

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


def _page():
    from dnf_gui.ui.pages.updates_page import UpdatesPage
    page = UpdatesPage()
    page.display_combined(UpdateInfo(packages=[
        Package(name=n, version="1", status=PackageStatus.UPDATE_AVAILABLE)
        for n in ("firefox", "kernel-core")]), [], None)
    return page


def _hold_button(page, name):
    layout = page._list_layout
    for i in range(layout.count()):
        card = layout.itemAt(i).widget()
        if isinstance(card, PackageCard) and card.package.name == name:
            return [b for b in card.findChildren(QPushButton)
                    if b.text() in ("Mark Major", "Unmark Major")][0]
    raise AssertionError(name)


class TestUpdatesPageReleaseAndHold(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_banner_states(self):
        page = _page()
        page.set_release_upgrade(ru.ReleaseUpgrade(44, 45, "2027-06-02"))
        self.assertFalse(page._release_banner.isHidden())
        self.assertIn("June 2, 2027", page._release_detail.text())
        fired = []
        page.release_upgrade_clicked.connect(fired.append)
        page._release_primary.click()
        self.assertEqual(fired, [45])

        dismissed = []
        page.release_dismissed.connect(dismissed.append)
        page._release_secondary.click()
        self.assertEqual(dismissed, [45])
        self.assertTrue(page._release_banner.isHidden())
        page.set_release_upgrade(ru.ReleaseUpgrade(44, 45), dismissed_release=45)
        self.assertTrue(page._release_banner.isHidden())

        # A finished download shows even if the offer was dismissed.
        page.set_release_upgrade(ru.ReleaseUpgrade(44, 45, downloaded=True),
                                 dismissed_release=45)
        self.assertFalse(page._release_banner.isHidden())
        installs = []
        page.release_install_clicked.connect(installs.append)
        page._release_primary.click()
        self.assertEqual(installs, [45])

    def test_hold_buttons(self):
        page = _page()
        self.assertEqual(_hold_button(page, "firefox").text(), "Mark Major")
        pattern_btn = _hold_button(page, "kernel-core")
        self.assertFalse(pattern_btn.isEnabled())  # held by kernel*
        toggles = []
        page.hold_toggled.connect(lambda name, hold: toggles.append((name, hold)))
        _hold_button(page, "firefox").click()
        self.assertEqual(toggles, [("firefox", True)])
        page.set_held_back_patterns(page.held_back_patterns + ["firefox"])
        released = _hold_button(page, "firefox")
        self.assertEqual(released.text(), "Unmark Major")
        badge = [l for l in released.parent().findChildren(QLabel)
                 if l.objectName() == "badge_muted"][0]
        self.assertIn("You marked this as major", badge.toolTip())
        released.click()
        self.assertEqual(toggles[-1], ("firefox", False))


class TestMainWindowReleaseAndHold(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_toggle_hold_persists(self):
        from dnf_gui.ui.main_window import MainWindow
        win = MainWindow()
        win._app_settings.passwordless_scope = "off"
        win._toggle_hold("firefox", True)
        self.assertIn("firefox", win._app_settings.held_back_patterns)
        self.assertIn("firefox", win._updates_page.held_back_patterns)
        win._toggle_hold("firefox", False)
        self.assertNotIn("firefox", win._app_settings.held_back_patterns)

    def test_upgrade_runs_update_then_download(self):
        from dnf_gui.ui.main_window import MainWindow
        win = MainWindow()
        with patch.object(QMessageBox, "question",
                          return_value=QMessageBox.StandardButton.Yes), \
             patch.object(ru, "current_release", return_value=44), \
             patch.object(win, "_run_command_chain") as chain:
            win._start_release_upgrade(45)
        cmds, operation = chain.call_args.args
        self.assertEqual(cmds[0][2:4], ["upgrade", "-y"])
        self.assertEqual(cmds[1][2:5], ["system-upgrade", "download", "--releasever=45"])
        self.assertEqual(operation, "Upgrade to Fedora 45")

    def test_successful_download_offers_restart(self):
        from dnf_gui.ui.main_window import MainWindow
        win = MainWindow()
        win._pending_release_target = 45
        with patch.object(win, "_install_release_upgrade") as install, \
             patch.object(ru, "current_release", return_value=44):
            win._on_command_done(0, "Upgrade to Fedora 45")
        install.assert_called_once_with(45)
        self.assertIn("downloaded", win._updates_page._release_title.text())

    def test_failed_download_offers_allowerasing(self):
        from dnf_gui.ui.main_window import MainWindow
        win = MainWindow()
        win._pending_release_target = 45
        win._cmd_queue = []
        with patch.object(win, "_on_release_download_failed") as failed:
            win._on_chain_step_done(1, "Upgrade to Fedora 45")
            self.app.processEvents()
        failed.assert_called_once_with(45)


if __name__ == "__main__":
    unittest.main()
