"""Tests for the Updates page modes, favorites, and package rows."""

import gc
import unittest
from unittest.mock import patch

from dnf_gui.core.app_settings import UPDATE_MODE_KEYS, AppSettings
from dnf_gui.core.flatpak_backend import FlatpakApp
from dnf_gui.core.package import Package, PackageStatus, UpdateInfo
from dnf_gui.core.security import SecuritySummary, build_security_update_command
from tests.conftest import answer


def _info(*names):
    return UpdateInfo(packages=[
        Package(name=n, version="1", status=PackageStatus.UPDATE_AVAILABLE)
        for n in names])


def _controller(test):
    # Free controllers left by earlier tests now, while none of their
    # threads run: a later processEvents() would otherwise fire their
    # pending start-up timers and GC could destroy a running QThread.
    gc.collect()
    from dnf_gui.ui.controllers.app_controller import AppController
    app = AppController()
    settings = app.settings
    saved = (settings.update_favorite, settings.held_back_patterns)

    def restore():
        settings.update_favorite, settings.held_back_patterns = saved
    test.addCleanup(restore)
    return app


def _scanned(test, flatpaks=(), security=None):
    app = _controller(test)
    app.updates._on_checked({"dnf": _info("kernel-core", "firefox"),
                             "flatpak": list(flatpaks),
                             "security": security or SecuritySummary(total=2)})
    return app


def _mode(app, key):
    return next(m for m in app.updates.modes if m["key"] == key)


class TestUpdateModes(unittest.TestCase):
    def test_modes_match_settings_keys(self):
        from dnf_gui.ui.controllers.updates import UPDATE_MODES
        self.assertEqual(tuple(k for k, _, _ in UPDATE_MODES), UPDATE_MODE_KEYS)
        app = _controller(self)
        self.assertEqual(tuple(m["key"] for m in app.updates.modes), UPDATE_MODE_KEYS)

    def test_main_button_runs_favorite_only_when_enabled(self):
        app = _controller(self)
        updates = app.updates
        updates.setFavorite("security")
        favorite = next(m for m in updates.modes if m["favorite"])
        self.assertEqual(favorite["title"], "Security Only")
        with patch.object(updates, "runMode") as run:
            updates.runFavorite()
        run.assert_not_called()  # nothing to do yet
        updates._on_checked({"dnf": _info("firefox"), "flatpak": [],
                             "security": SecuritySummary(
                                 total=3, package_severity={"firefox": "low"})})
        with patch.object(updates, "runMode") as run:
            updates.runFavorite()
        run.assert_called_once_with("security")

    def test_starring_changes_favorite_and_saves_it(self):
        app = _controller(self)
        app.updates.setFavorite("minor")
        self.assertEqual(app.updates.favorite, "minor")
        self.assertEqual(app.settings.update_favorite, "minor")
        favorite = next(m for m in app.updates.modes if m["favorite"])
        self.assertEqual(favorite["key"], "minor")

    def test_unknown_favorite_is_ignored(self):
        app = _controller(self)
        app.updates.setFavorite("all")
        app.updates.setFavorite("bogus")
        self.assertEqual(app.updates.favorite, "all")
        self.assertEqual(app.settings.update_favorite, "all")


class TestUpdateRows(unittest.TestCase):
    def test_row_update_button_confirms_then_runs(self):
        app = _scanned(self)
        shown = answer(app, "yes")
        with patch.object(app.runner, "run") as run:
            app.updates.upgradePackage("firefox")
        self.assertEqual(shown[0].title, "Update Package?")
        run.assert_called_once_with(
            app.backend.build_upgrade_package_command("firefox"), "Updating firefox")
        answer(app, "no")
        with patch.object(app.runner, "run") as run:
            app.updates.upgradePackage("firefox")
        run.assert_not_called()

    def test_flatpak_row_update_button_confirms_then_runs_that_app(self):
        app = _scanned(self, flatpaks=[FlatpakApp(name="Kdenlive", application_id="org.kde.kdenlive",
                                                  branch="stable")])
        row = app.updates.model.find("name", "Kdenlive")
        shown = answer(app, "yes")
        with patch.object(app.runner, "run") as run:
            app.flatpak.updateApp(row["appId"], row["branch"])
        self.assertEqual(shown[0].title, "Update Flatpak App?")
        command = app.flatpak_backend.build_update_command("org.kde.kdenlive", "stable")
        self.assertEqual(command[1:], ["update", "-y", "org.kde.kdenlive//stable"])
        run.assert_called_once_with(command, "Updating Flatpak: org.kde.kdenlive")
        answer(app, "no")
        with patch.object(app.runner, "run") as run:
            app.flatpak.updateApp("org.kde.kdenlive", "stable")
        run.assert_not_called()

    def test_flatpak_update_refuses_option_like_ids(self):
        app = _controller(self)
        backend = app.flatpak_backend
        self.assertEqual(backend.build_update_command("org.a.A")[1:], ["update", "-y", "org.a.A"])
        for bad in (("--system", ""), ("org.a.A", "-x"), ("", ""), ("a b", "")):
            with self.assertRaises(ValueError):
                backend.build_update_command(*bad)
        shown = answer(app, "yes")
        with patch.object(app.runner, "run") as run:
            app.flatpak.updateApp("--user", "")
        self.assertEqual(shown, [])
        run.assert_not_called()

    def test_held_back_rows_are_tagged(self):
        app = _scanned(self)
        model = app.updates.model
        self.assertEqual({r["name"]: r["major"] for r in model.rows()},
                         {"kernel-core": True, "firefox": False})
        self.assertEqual(app.updates.majorCount, 1)
        self.assertIn("skips 1 core", _mode(app, "minor")["detail"])
        reason = model.find("name", "kernel-core")["majorReason"]
        # The tooltip says why it's major and what that means.
        self.assertIn("kernel*", reason)
        self.assertIn("Update Without Core skips it", reason)

    def test_mode_states_follow_scan(self):
        app = _scanned(self, flatpaks=[FlatpakApp(name="A", application_id="org.a.A")],
                       security=SecuritySummary(total=2, package_severity={"firefox": "low"}))
        for key in UPDATE_MODE_KEYS:
            self.assertTrue(_mode(app, key)["enabled"], key)
        self.assertEqual(_mode(app, "everything")["detail"], "2 packages + 1 Flatpak")

    def test_filter_narrows_rows(self):
        app = _scanned(self)
        view = app.updates.filtered
        view.query = "fire"
        self.assertEqual([view.get(i)["name"] for i in range(view.count)], ["firefox"])

    def test_triggered_modes_map_to_actions(self):
        app = _scanned(self)
        fired = []
        with patch.object(app.updates, "upgrade_without_major",
                          side_effect=lambda: fired.append("minor")), \
                patch.object(app.updates, "update_everything",
                             side_effect=lambda: fired.append("everything")), \
                patch.object(app.updates, "upgrade_all",
                             side_effect=lambda: fired.append("all")), \
                patch.object(app.updates, "security_upgrade",
                             side_effect=lambda: fired.append("security")):
            for key in ("minor", "everything", "all", "security"):
                app.updates.runMode(key)
        self.assertEqual(fired, ["minor", "everything", "all", "security"])


class TestModeCommands(unittest.TestCase):
    """Each mode runs the exact argv the passwordless rule lists, only on Yes."""

    def _run(self, action, *choices):
        app = _scanned(self)
        shown = answer(app, *choices)
        with patch.object(app.runner, "run") as run, \
                patch.object(app.runner, "run_chain") as chain:
            getattr(app.updates, action)()
        return app, shown, run, chain

    def test_upgrade_all(self):
        app, shown, run, _ = self._run("upgrade_all", "yes")
        run.assert_called_once_with(app.backend.build_upgrade_command(), "System Upgrade")
        self.assertEqual(shown[0].default, "no")

    def test_update_everything_chains_dnf_then_flatpak(self):
        app, _, run, chain = self._run("update_everything", "yes")
        run.assert_not_called()
        chain.assert_called_once_with(
            [app.backend.build_upgrade_command(),
             app.flatpak_backend.build_update_all_command()],
            "Update Everything (DNF + Flatpak)")

    def test_security_only(self):
        _, shown, run, _ = self._run("security_upgrade", "yes")
        self.assertIn("dnf upgrade --security", shown[0].text)
        run.assert_called_once_with(build_security_update_command(), "Security Upgrade")

    def test_no_runs_nothing(self):
        for action in ("upgrade_all", "update_everything", "security_upgrade",
                       "upgrade_without_major"):
            _, _, run, chain = self._run(action, "no")
            run.assert_not_called()
            chain.assert_not_called()


class TestFavoriteSetting(unittest.TestCase):
    def test_invalid_saved_value_falls_back(self):
        settings = AppSettings()
        with patch.object(settings, "get", return_value="bogus"):
            self.assertEqual(settings.update_favorite, "everything")
        with patch.object(settings, "get", return_value="minor"):
            self.assertEqual(settings.update_favorite, "minor")


if __name__ == "__main__":
    unittest.main()
