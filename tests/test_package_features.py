"""Tests for repository search, version transitions, security tags, Clean Up
preview, and completion notifications."""

import gc
import unittest
from unittest.mock import patch, MagicMock

from dnf_gui.core.dnf_backend import DNFBackend
from dnf_gui.core.package import Package, PackageStatus, UpdateInfo
from dnf_gui.core.security import SecuritySummary, get_security_summary
from tests.conftest import answer


def _backend():
    with patch("shutil.which", return_value="/usr/bin/dnf5"):
        return DNFBackend()


def _controller():
    # Free controllers left by earlier tests now, while none of their
    # threads run: a later processEvents() would otherwise fire their
    # pending start-up timers and GC could destroy a running QThread.
    gc.collect()
    from dnf_gui.ui.controllers.app_controller import AppController
    return AppController()


def _update_row(pkg):
    """The Updates page row the QML shows for one pending update."""
    app = _controller()
    app.updates._on_checked({"dnf": UpdateInfo(packages=[pkg]), "flatpak": [],
                             "security": None})
    return app.updates.model.find("name", pkg.name)


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
        proc = MagicMock(returncode=100,
                         stdout="firefox.x86_64 146.0-1.fc44 updates\n")
        with patch("dnf_gui.core.dnf_backend.subprocess.run", return_value=proc), \
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


class TestRows(unittest.TestCase):
    def test_update_row_shows_version_transition(self):
        row = _update_row(Package(name="firefox", version="146.0", release="1.fc44",
                                  installed_version="145.0-1.fc44",
                                  status=PackageStatus.UPDATE_AVAILABLE))
        self.assertEqual((row["fromVersion"], row["toVersion"]),
                         ("145.0-1.fc44", "146.0-1.fc44"))

    def test_install_confirms_then_runs_exact_command(self):
        app = _controller()
        shown = answer(app, "yes")
        with patch.object(app.runner, "run") as run:
            app.packages.install("htop")
        self.assertEqual(shown[0].title, "Install Package?")
        run.assert_called_once_with(app.backend.build_install_command("htop"),
                                    "Installing htop")

    def test_install_declined_runs_nothing(self):
        app = _controller()
        answer(app, "no")
        with patch.object(app.runner, "run") as run:
            app.packages.install("htop")
        run.assert_not_called()

    def test_remove_is_destructive_and_defaults_to_no(self):
        app = _controller()
        shown = answer(app)  # default answer
        with patch.object(app.runner, "run") as run:
            app.packages.remove("htop")
        self.assertTrue(shown[0].destructive)
        self.assertEqual(shown[0].default, "no")
        run.assert_not_called()
        answer(app, "yes")
        with patch.object(app.runner, "run") as run:
            app.packages.remove("htop")
        run.assert_called_once_with(app.backend.build_remove_command("htop"),
                                    "Removing htop")


class TestUpdatesSecurityFilter(unittest.TestCase):
    def test_security_tags_and_show_filter(self):
        app = _controller()
        info = UpdateInfo(packages=[
            Package(name=n, version="1", status=PackageStatus.UPDATE_AVAILABLE)
            for n in ("firefox", "libheif", "kernel-core")])
        app.updates._on_checked({"dnf": info, "flatpak": [], "security": SecuritySummary(
            total=1, package_severity={"libheif": "important"})})
        updates = app.updates
        self.assertIn("1 security", updates.summary)

        def names():
            view = updates.filtered
            return [view.get(i)["name"] for i in range(view.count)]

        libheif = updates.model.find("name", "libheif")
        self.assertTrue(libheif["security"])
        self.assertEqual(libheif["severity"], "Important")
        self.assertFalse(updates.model.find("name", "firefox")["security"])
        updates.filtered.category = "security"
        self.assertEqual(names(), ["libheif"])
        updates.filtered.category = "major"
        self.assertEqual(names(), ["kernel-core"])


class TestPackagesSearch(unittest.TestCase):
    def test_stale_results_are_ignored(self):
        packages = _controller().packages
        packages._search_generation = 2  # "ht" was 1, "htop" is 2
        packages._on_search(1, [Package(name="old", version="")])
        self.assertEqual(packages.results.count, 0)
        packages._on_search(2, [
            Package(name="htop", version="3.4", status=PackageStatus.INSTALLED),
            Package(name="neohtop", version="")])
        rows = packages.results.rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual([r["name"] for r in rows if r["installed"]], ["htop"])
        self.assertTrue(packages.searchDone)


class TestControllerFeatures(unittest.TestCase):
    def test_clean_up_with_nothing_unneeded_runs_nothing(self):
        app = _controller()
        shown = answer(app)
        with patch.object(app.runner, "run") as run:
            app.updates._confirm_autoremove([])
        self.assertEqual([p.title for p in shown], ["Nothing to Clean Up"])
        self.assertEqual([b for b, _ in shown[0].buttons], ["ok"])
        run.assert_not_called()

    def test_clean_up_lists_packages_before_running(self):
        app = _controller()
        shown = answer(app, "yes")
        with patch.object(app.runner, "run") as run:
            app.updates._confirm_autoremove(["libold-1.0-1.fc44"])
        self.assertIn("libold-1.0-1.fc44", shown[0].details)
        self.assertTrue(shown[0].destructive)
        run.assert_called_once_with(app.backend.build_autoremove_command(), "Autoremove")

    def test_clean_up_declined_runs_nothing(self):
        app = _controller()
        answer(app, "no")
        with patch.object(app.runner, "run") as run:
            app.updates._confirm_autoremove(["libold-1.0-1.fc44"])
        run.assert_not_called()

    def test_notifies_only_when_unfocused(self):
        app = _controller()
        with patch.object(app.notifier, "send") as notify, \
             patch.object(app, "_window_active", return_value=True):
            app._notify_if_unfocused(0, "System Upgrade")
        notify.assert_not_called()
        with patch.object(app.notifier, "send") as notify, \
             patch.object(app, "_window_active", return_value=False):
            app._notify_if_unfocused(1, "System Upgrade")
        sent = notify.call_args.args[0]
        self.assertEqual(sent.title, "System Upgrade")
        self.assertIn("Failed", sent.body)
        self.assertEqual(sent.page, "terminal")  # click shows the output
        self.assertIn(("terminal", "Show Output"), sent.actions)

    def test_success_notification_just_raises_the_window(self):
        app = _controller()
        with patch.object(app.notifier, "send") as notify, \
             patch.object(app, "_window_active", return_value=False):
            app._notify_if_unfocused(0, "System Upgrade")
        sent = notify.call_args.args[0]
        self.assertEqual(sent.page, "")
        self.assertEqual(sent.urgency, "normal")


class TestFlatpakRemotes(unittest.TestCase):
    def test_prefers_flathub_then_the_listed_remote(self):
        from dnf_gui.core.flatpak_backend import FlatpakBackend, pick_remote
        self.assertEqual(pick_remote(""), "flathub")
        self.assertEqual(pick_remote("fedora,flathub"), "flathub")
        self.assertEqual(pick_remote("fedora"), "fedora")
        self.assertEqual(pick_remote("--user"), "flathub")  # never an option
        cmd = FlatpakBackend().build_install_command("org.example.App", "fedora")
        self.assertEqual(cmd[-2:], ["fedora", "org.example.App"])

    def test_search_marks_installed_apps(self):
        from dnf_gui.core.flatpak_backend import FlatpakApp
        flatpak = _controller().flatpak
        flatpak._on_loaded([FlatpakApp(name="A", application_id="org.a.A")])
        flatpak._search_generation = 1
        flatpak._on_search(1, [
            FlatpakApp(name="A", application_id="org.a.A", origin="flathub"),
            FlatpakApp(name="B", application_id="org.b.B", origin="fedora")])
        installed = {r["appId"]: r["installed"] for r in flatpak.results.rows()}
        self.assertEqual(installed, {"org.a.A": True, "org.b.B": False})


class TestVersionEpochs(unittest.TestCase):
    def _transition(self, installed, new):
        row = _update_row(Package(name="akmod-nvidia", version=new,
                                  installed_version=installed,
                                  status=PackageStatus.UPDATE_AVAILABLE))
        return f"{row['fromVersion']} → {row['toVersion']}"

    def test_mismatched_epochs_are_dropped(self):
        # "3:615.71 → 615.78" reads like a downgrade.
        self.assertEqual(self._transition("3:615.71-3.fc44", "615.78-1.fc44"),
                         "615.71-3.fc44 → 615.78-1.fc44")

    def test_matching_epochs_are_kept(self):
        self.assertEqual(self._transition("3:615.71-3.fc44", "3:615.78-1.fc44"),
                         "3:615.71-3.fc44 → 3:615.78-1.fc44")


if __name__ == "__main__":
    unittest.main()
