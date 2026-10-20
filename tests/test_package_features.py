"""Tests for repository search, version transitions, security tags, Clean Up
preview, and completion notifications."""

import unittest
from unittest.mock import patch, MagicMock

from PyQt6.QtWidgets import QApplication, QLabel, QMessageBox

from dnf_gui.core.dnf_backend import DNFBackend
from dnf_gui.core.package import Package, PackageStatus, UpdateInfo
from dnf_gui.core.security import SecuritySummary, get_security_summary
from dnf_gui.ui.widgets.package_card import PackageCard


def _backend():
    with patch("shutil.which", return_value="/usr/bin/dnf5"):
        return DNFBackend()


DNF5_SEARCH = (
    "Matched fields: name (exact)\n"
    " htop.x86_64\tInteractive process viewer\n"
    "Matched fields: name, summary\n"
    " neohtop-debuginfo.x86_64\tDebug information for package neohtop\n"
    " neohtop.aarch64\tSystem monitoring on steroids\n"
    " neohtop.x86_64\tSystem monitoring on steroids\n"
    " neohtop.i686\tSystem monitoring on steroids\n"
)
DNF4_SEARCH = (
    "=== Name Exactly Matched: htop ===\n"
    "htop.x86_64 : Interactive process viewer\n"
    "=== Name & Summary Matched: htop ===\n"
    "pcp-htop.x86_64 : Performance Co-Pilot htop\n"
)


class TestRepoSearch(unittest.TestCase):
    def _search(self, output, installed=None):
        backend = _backend()

        def fake_run(cmd, allow_nonzero=False):
            if "repoquery" in cmd:
                return "neohtop 1.2.0-1.fc44 updates\npcp-htop 6.3-1.fc44 fedora\n"
            return output

        with patch.object(DNFBackend, "_run", side_effect=fake_run), \
             patch.object(DNFBackend, "_installed_versions",
                          return_value=installed or {}), \
             patch("dnf_gui.core.dnf_backend.platform.machine", return_value="x86_64"):
            return backend.search("htop")

    def test_dnf5_keeps_order_native_arch_and_skips_debug(self):
        results = self._search(DNF5_SEARCH, {"htop": "3.4.1-3.fc44"})
        self.assertEqual([(p.name, p.arch) for p in results],
                         [("htop", "x86_64"), ("neohtop", "x86_64")])
        self.assertEqual(results[0].status, PackageStatus.INSTALLED)
        self.assertEqual(results[0].version, "3.4.1-3.fc44")
        self.assertEqual(results[1].status, PackageStatus.AVAILABLE)
        self.assertEqual(results[1].summary, "System monitoring on steroids")
        self.assertEqual((results[1].version, results[1].repo), ("1.2.0-1.fc44", "updates"))

    def test_dnf4_format(self):
        results = self._search(DNF4_SEARCH)
        self.assertEqual([p.name for p in results], ["htop", "pcp-htop"])

    def test_rejects_short_and_option_like_queries(self):
        backend = _backend()
        with patch.object(DNFBackend, "_run") as run:
            self.assertEqual(backend.search("h"), [])
            self.assertEqual(backend.search("--help"), [])
        run.assert_not_called()


class TestInstalledVersions(unittest.TestCase):
    def test_newest_wins_and_missing_ignored(self):
        out = ("kernel-core 7.2.5-200.fc44\nkernel-core 7.2.6-200.fc44\n"
               "package nope is not installed\n")
        with patch("dnf_gui.core.dnf_backend.subprocess.run",
                   return_value=MagicMock(stdout=out)):
            versions = _backend()._installed_versions(["kernel-core", "nope"])
        self.assertEqual(versions, {"kernel-core": "7.2.6-200.fc44"})

    def test_check_updates_fills_installed_version(self):
        backend = _backend()
        with patch.object(DNFBackend, "_run",
                          return_value="firefox.x86_64 146.0-1.fc44 updates\n"), \
             patch.object(DNFBackend, "_installed_versions",
                          return_value={"firefox": "145.0-1.fc44"}):
            info = backend.check_updates()
        self.assertEqual(info.packages[0].installed_version, "145.0-1.fc44")


class TestUnneeded(unittest.TestCase):
    def test_parses_sorted_unique(self):
        with patch.object(DNFBackend, "_run", return_value="b-1-1\na-2-1\nb-1-1\n"):
            self.assertEqual(_backend().unneeded_packages(), ["a-2-1", "b-1-1"])

    def test_upgrade_package_uses_upgrade_verb(self):
        cmd = _backend().build_upgrade_package_command("firefox")
        self.assertEqual(cmd, ["pkexec", "/usr/bin/dnf5", "upgrade", "-y", "firefox"])


class TestSecurityPackageSeverity(unittest.TestCase):
    @patch("dnf_gui.core.security._run")
    def test_highest_severity_per_package(self, mock_run):
        mock_run.side_effect = [
            "FEDORA-2026-1 security Moderate  libfoo-1.0-1.fc44.x86_64 2026-10-01\n"
            "FEDORA-2026-2 security Critical  libfoo-1.1-1.fc44.x86_64 2026-10-02\n"
            "FEDORA-2026-3 security Low       my-pkg-name-2.0-3.fc44.noarch 2026-10-02\n",
            "",
        ]
        sec = get_security_summary()
        self.assertEqual(sec.package_severity,
                         {"libfoo": "critical", "my-pkg-name": "low"})


class TestCards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _texts(self, widget):
        return [label.text() for label in widget.findChildren(QLabel)]

    def test_update_card_shows_version_transition(self):
        pkg = Package(name="firefox", version="146.0", release="1.fc44",
                      installed_version="145.0-1.fc44",
                      status=PackageStatus.UPDATE_AVAILABLE)
        self.assertIn("145.0-1.fc44 → 146.0-1.fc44", self._texts(PackageCard(pkg)))

    def test_available_card_offers_install(self):
        card = PackageCard(Package(name="htop", version="", status=PackageStatus.AVAILABLE))
        fired = []
        card.install_clicked.connect(fired.append)
        from PyQt6.QtWidgets import QPushButton
        [b for b in card.findChildren(QPushButton) if b.text() == "Install"][0].click()
        self.assertEqual(fired, ["htop"])


class TestUpdatesSecurityFilter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_security_tags_and_show_filter(self):
        from dnf_gui.ui.pages.updates_page import UpdatesPage
        page = UpdatesPage()
        info = UpdateInfo(packages=[
            Package(name=n, version="1", status=PackageStatus.UPDATE_AVAILABLE)
            for n in ("firefox", "libheif", "kernel-core")])
        page.display_combined(info, [], SecuritySummary(
            total=1, package_severity={"libheif": "important"}))
        self.assertIn("1 security", page._list_summary.text())

        def rows():
            layout = page._list_layout
            return {layout.itemAt(i).widget().package.name:
                    [l.text() for l in layout.itemAt(i).widget().findChildren(QLabel)
                     if l.objectName().startswith("badge_")]
                    for i in range(layout.count())
                    if isinstance(layout.itemAt(i).widget(), PackageCard)}

        self.assertEqual(rows()["libheif"], ["Security · Important"])
        page._show_combo.setCurrentIndex(page._show_combo.findData("security"))
        self.assertEqual(list(rows()), ["libheif"])
        page._show_combo.setCurrentIndex(page._show_combo.findData("held"))
        self.assertEqual(list(rows()), ["kernel-core"])


class TestPackagesPageSearch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_stale_results_are_ignored(self):
        from dnf_gui.ui.pages.installed_page import InstalledPage
        page = InstalledPage()
        page._repo_search_input.setText("htop")
        page.display_search_results("ht", [Package(name="old", version="")])
        self.assertEqual(page._search_count.text(), "")
        page.display_search_results("htop", [
            Package(name="htop", version="3.4", status=PackageStatus.INSTALLED),
            Package(name="neohtop", version="")])
        self.assertIn("2 results", page._search_count.text())
        self.assertIn("1 already installed", page._search_count.text())


class TestMainWindowFeatures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_clean_up_with_nothing_unneeded_runs_nothing(self):
        from dnf_gui.ui.main_window import MainWindow
        win = MainWindow()
        with patch.object(QMessageBox, "information") as info, \
             patch.object(win, "_run_command") as run:
            win._confirm_autoremove([])
        info.assert_called_once()
        run.assert_not_called()

    def test_clean_up_lists_packages_before_running(self):
        from dnf_gui.ui.main_window import MainWindow
        win = MainWindow()
        with patch.object(QMessageBox, "question",
                          return_value=QMessageBox.StandardButton.Yes) as ask, \
             patch.object(win, "_run_command") as run:
            win._confirm_autoremove(["libold-1.0-1.fc44"])
        self.assertIn("libold-1.0-1.fc44", ask.call_args.args[2])
        run.assert_called_once()

    def test_notifies_only_when_unfocused(self):
        from dnf_gui.ui import main_window as mw
        win = mw.MainWindow()
        with patch.object(mw, "send_desktop_notification") as notify, \
             patch.object(win, "isActiveWindow", return_value=True):
            win._notify_if_unfocused(0, "System Upgrade")
        notify.assert_not_called()
        with patch.object(mw, "send_desktop_notification") as notify, \
             patch.object(win, "isActiveWindow", return_value=False):
            win._notify_if_unfocused(1, "System Upgrade")
        self.assertEqual(notify.call_args.args[0], "System Upgrade failed")
        self.assertTrue(notify.call_args.kwargs["urgent"])


if __name__ == "__main__":
    unittest.main()


class TestStylesheetColors(unittest.TestCase):
    def test_no_eight_digit_hex_colors(self):
        # Qt parses #xxxxxxxx as #AARRGGBB; translucency must use rgba().
        import re
        from dnf_gui.ui.styles.theme import get_stylesheet
        for mode in ("dark", "light"):
            self.assertEqual(re.findall(r"#[0-9a-fA-F]{8}\b", get_stylesheet(mode)), [])


class TestVersionEpochs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _detail(self, installed, new):
        pkg = Package(name="akmod-nvidia", version=new, installed_version=installed,
                      status=PackageStatus.UPDATE_AVAILABLE)
        return [label.text() for label in PackageCard(pkg).findChildren(QLabel)
                if "→" in label.text()][0]

    def test_mismatched_epochs_are_dropped(self):
        self.assertEqual(self._detail("3:615.71-3.fc44", "615.78-1.fc44"),
                         "615.71-3.fc44 → 615.78-1.fc44")

    def test_matching_epochs_are_kept(self):
        self.assertEqual(self._detail("3:615.71-3.fc44", "3:615.78-1.fc44"),
                         "3:615.71-3.fc44 → 3:615.78-1.fc44")
