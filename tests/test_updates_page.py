"""The Updates page: the scan result, the four update modes and the
favorite main button, the rows and their filters, single-package and
single-Flatpak updates, Clean Up, and the scan cache.

Core updates are in test_core_updates.py, security waits in
test_security.py, and the restart notice in test_reboot.py.
"""

from unittest.mock import patch

import pytest

from dnf_gui.core.app_settings import UPDATE_MODE_KEYS, AppSettings
from dnf_gui.core.flatpak_backend import FlatpakApp
from dnf_gui.core.package import Package, PackageStatus, UpdateInfo
from dnf_gui.core.security import SecuritySummary, build_security_update_command
from tests.conftest import answer


def _info(*names):
    return UpdateInfo(packages=[
        Package(name=n, version="1", status=PackageStatus.UPDATE_AVAILABLE)
        for n in names])


def _scan(app, dnf=None, flatpaks=(), security=None):
    app.updates._on_checked({"dnf": dnf if dnf is not None else _info("kernel-core", "firefox"),
                             "flatpak": list(flatpaks),
                             "security": security})
    return app


@pytest.fixture
def scanned(app):
    """After a scan: kernel-core and firefox, 2 security advisories."""
    return _scan(app, security=SecuritySummary(total=2))


def _mode(app, key):
    return next(m for m in app.updates.modes if m["key"] == key)


def _names(view):
    return [view.get(i)["name"] for i in range(view.count)]


# ── the scan ─────────────────────────────────────────────────────────

def test_failed_check_is_not_up_to_date(app):
    app.set_update_badge(5)
    app.updates._on_checked({"dnf": UpdateInfo(check_failed=True),
                             "flatpak": [], "security": None})
    updates = app.updates
    assert updates.phase == "failed"
    assert "Couldn't Check" in updates.headline
    assert "up to date" not in (updates.headline + updates.summary).lower()
    assert app.updateBadge == 5  # unknown, not zero
    assert updates._cache is None  # the next visit rescans


class TestScanCache:
    @pytest.fixture
    def cached(self, app):
        app.updates._cache = {
            "dnf": UpdateInfo(total_updates=0, last_checked="2026-09-14 09:44 PM"),
            "flatpak": [], "security": SecuritySummary(), "preview": None,
            "security_preview": None, "reboot": False}
        return app

    def test_revisit_reuses_the_cache(self, cached):
        assert cached.currentPage == "updates"
        with patch.object(cached.updates, "check") as check:
            cached.refreshCurrent(revisit=True)  # a page visit
        check.assert_not_called()
        assert "up to date" in cached.updates.headline.lower()

    def test_navigating_back_reuses_the_cache(self, cached):
        with patch.object(cached.updates, "check") as check, \
                patch.object(cached.settings_controller, "show"):
            cached.navigate("settings")
            cached.navigate("updates")
        check.assert_not_called()

    def test_no_cache_scans(self, app):
        app.updates._cache = None
        with patch.object(app.updates, "check") as check:
            app.refreshCurrent(revisit=True)
        check.assert_called_once()

    def test_successful_command_invalidates_the_cache(self, cached):
        with patch.object(cached, "refreshCurrent"), \
                patch.object(cached.updates, "recheck_reboot"):
            cached._on_operation_finished(0, "System Upgrade", False)
        assert cached.updates._cache is None

    def test_failed_command_keeps_the_cache(self, cached):
        cached._on_operation_finished(1, "System Upgrade", False)
        assert cached.updates._cache is not None


# ── modes and the favorite ───────────────────────────────────────────

class TestModes:
    def test_modes_match_settings_keys(self, app):
        from dnf_gui.ui.controllers.updates import UPDATE_MODES
        assert tuple(k for k, _, _ in UPDATE_MODES) == UPDATE_MODE_KEYS
        assert tuple(m["key"] for m in app.updates.modes) == UPDATE_MODE_KEYS

    def test_main_button_runs_the_favorite_only_when_enabled(self, app):
        updates = app.updates
        updates.setFavorite("security")
        assert next(m for m in updates.modes if m["favorite"])["title"] == "Security Only"
        with patch.object(updates, "runMode") as run:
            updates.runFavorite()
        run.assert_not_called()  # nothing to do yet
        _scan(app, _info("firefox"),
              security=SecuritySummary(total=3, package_severity={"firefox": "low"}))
        with patch.object(updates, "runMode") as run:
            updates.runFavorite()
        run.assert_called_once_with("security")

    def test_main_button_falls_back_when_the_favorite_has_nothing_to_do(self, app):
        app.updates.setFavorite("all")
        _scan(app, UpdateInfo(), [FlatpakApp("Kdenlive", "org.kde.kdenlive")])
        assert app.updates.mainMode == "everything"   # only Flatpak updates are waiting
        with patch.object(app.updates, "runMode") as run:
            app.updates.runFavorite()
        run.assert_called_once_with("everything")

    def test_starring_changes_the_favorite_and_saves_it(self, app):
        app.updates.setFavorite("minor")
        assert app.updates.favorite == "minor"
        assert app.settings.update_favorite == "minor"
        assert next(m for m in app.updates.modes if m["favorite"])["key"] == "minor"

    def test_unknown_favorite_is_ignored(self, app):
        app.updates.setFavorite("all")
        app.updates.setFavorite("bogus")
        assert app.updates.favorite == "all"
        assert app.settings.update_favorite == "all"

    def test_invalid_saved_favorite_falls_back(self):
        settings = AppSettings()
        with patch.object(settings, "get", return_value="bogus"):
            assert settings.update_favorite == "everything"
        with patch.object(settings, "get", return_value="minor"):
            assert settings.update_favorite == "minor"

    def test_mode_states_follow_the_scan(self, app):
        _scan(app, flatpaks=[FlatpakApp(name="A", application_id="org.a.A")],
              security=SecuritySummary(total=2, package_severity={"firefox": "low"}))
        for key in UPDATE_MODE_KEYS:
            assert _mode(app, key)["enabled"], key
        assert _mode(app, "everything")["detail"] == "2 packages + 1 Flatpak"

    def test_each_mode_runs_its_action(self, scanned):
        fired = []
        actions = {"minor": "upgrade_without_major", "everything": "update_everything",
                   "all": "upgrade_all", "security": "security_upgrade"}
        patches = [patch.object(scanned.updates, method,
                                side_effect=lambda key=key: fired.append(key))
                   for key, method in actions.items()]
        for p in patches:
            p.start()
        try:
            for key in actions:
                scanned.updates.runMode(key)
        finally:
            for p in patches:
                p.stop()
        assert fired == list(actions)


class TestModeCommands:
    """Each mode runs the exact argv the passwordless rule lists, only on Yes,
    and its confirmation defaults to Cancel."""

    def _run(self, app, action, *choices):
        shown = answer(app, *choices)
        with patch.object(app.runner, "run") as run, \
                patch.object(app.runner, "run_chain") as chain:
            getattr(app.updates, action)()
        return shown, run, chain

    def test_upgrade_all(self, scanned):
        shown, run, _ = self._run(scanned, "upgrade_all", "yes")
        run.assert_called_once_with(scanned.backend.build_upgrade_command(), "System Upgrade")
        assert shown[0].default == "no"

    def test_update_everything_chains_dnf_then_flatpak(self, scanned):
        shown, run, chain = self._run(scanned, "update_everything", "yes")
        run.assert_not_called()
        chain.assert_called_once_with(
            [scanned.backend.build_upgrade_command(),
             scanned.flatpak_backend.build_update_all_command()],
            "Update Everything (DNF + Flatpak)")
        assert shown[0].default == "no"

    def test_security_only(self, scanned):
        shown, run, _ = self._run(scanned, "security_upgrade", "yes")
        assert "dnf upgrade --security" in shown[0].text
        run.assert_called_once_with(build_security_update_command(), "Security Upgrade")

    @pytest.mark.parametrize("action", ["upgrade_all", "update_everything",
                                        "security_upgrade", "upgrade_without_major"])
    def test_no_runs_nothing(self, scanned, action):
        _, run, chain = self._run(scanned, action, "no")
        run.assert_not_called()
        chain.assert_not_called()


# ── rows ─────────────────────────────────────────────────────────────

def _row(app, pkg):
    _scan(app, UpdateInfo(packages=[pkg]))
    return app.updates.model.find("name", pkg.name)


def test_row_shows_the_version_change(app):
    row = _row(app, Package(name="firefox", version="146.0", release="1.fc44",
                            installed_version="145.0-1.fc44",
                            status=PackageStatus.UPDATE_AVAILABLE))
    assert (row["fromVersion"], row["toVersion"]) == ("145.0-1.fc44", "146.0-1.fc44")


@pytest.mark.parametrize("installed, new, shown", [
    # "3:615.71 → 615.78" would read like a downgrade.
    ("3:615.71-3.fc44", "615.78-1.fc44", "615.71-3.fc44 → 615.78-1.fc44"),
    ("3:615.71-3.fc44", "3:615.78-1.fc44", "3:615.71-3.fc44 → 3:615.78-1.fc44"),
])
def test_row_epochs(app, installed, new, shown):
    row = _row(app, Package(name="akmod-nvidia", version=new, installed_version=installed,
                            status=PackageStatus.UPDATE_AVAILABLE))
    assert f"{row['fromVersion']} → {row['toVersion']}" == shown


def test_security_tags_and_filters(app):
    _scan(app, _info("firefox", "libheif", "kernel-core"),
          security=SecuritySummary(total=1, package_severity={"libheif": "important"}))
    updates = app.updates
    assert "1 security" in updates.summary
    libheif = updates.model.find("name", "libheif")
    assert libheif["security"] and libheif["severity"] == "Important"
    assert not updates.model.find("name", "firefox")["security"]
    updates.filtered.category = "security"
    assert _names(updates.filtered) == ["libheif"]
    updates.filtered.category = "major"
    assert _names(updates.filtered) == ["kernel-core"]
    updates.filtered.category = "all"
    updates.filtered.query = "fire"
    assert _names(updates.filtered) == ["firefox"]


def test_flatpak_update_pill_matches_app_id_and_branch(app):
    _scan(app, UpdateInfo(), [FlatpakApp("KDE Application Platform", "org.kde.Platform", "", "6.9")])
    assert app.updates.flatpakHasUpdate("org.kde.Platform", "6.9")
    assert not app.updates.flatpakHasUpdate("org.kde.Platform", "6.8")
    assert not app.updates.flatpakHasUpdate("org.kde.Sdk", "6.9")


class TestSingleUpdates:
    def test_package_row_confirms_then_runs(self, scanned):
        shown = answer(scanned, "yes")
        with patch.object(scanned.runner, "run") as run:
            scanned.updates.upgradePackage("firefox")
        assert shown[0].title == "Update Package?"
        run.assert_called_once_with(
            scanned.backend.build_upgrade_package_command("firefox"), "Updating firefox")
        answer(scanned, "no")
        with patch.object(scanned.runner, "run") as run:
            scanned.updates.upgradePackage("firefox")
        run.assert_not_called()

    def test_flatpak_row_confirms_then_runs_that_app(self, app):
        _scan(app, flatpaks=[FlatpakApp(name="Kdenlive", application_id="org.kde.kdenlive",
                                        branch="stable")])
        row = app.updates.model.find("name", "Kdenlive")
        shown = answer(app, "yes")
        with patch.object(app.runner, "run") as run:
            app.flatpak.updateApp(row["appId"], row["branch"])
        assert shown[0].title == "Update Flatpak App?"
        command = app.flatpak_backend.build_update_command("org.kde.kdenlive", "stable")
        assert command[1:] == ["update", "-y", "org.kde.kdenlive//stable"]
        run.assert_called_once_with(command, "Updating Flatpak: org.kde.kdenlive")
        answer(app, "no")
        with patch.object(app.runner, "run") as run:
            app.flatpak.updateApp("org.kde.kdenlive", "stable")
        run.assert_not_called()

    def test_flatpak_update_refuses_option_like_ids(self, app):
        backend = app.flatpak_backend
        assert backend.build_update_command("org.a.A")[1:] == ["update", "-y", "org.a.A"]
        for bad in (("--system", ""), ("org.a.A", "-x"), ("", ""), ("a b", "")):
            with pytest.raises(ValueError):
                backend.build_update_command(*bad)
        shown = answer(app, "yes")
        with patch.object(app.runner, "run") as run:
            app.flatpak.updateApp("--user", "")
        assert shown == []
        run.assert_not_called()


# ── Clean Up ─────────────────────────────────────────────────────────

class TestCleanUp:
    def test_nothing_unneeded_runs_nothing(self, app):
        shown = answer(app)
        with patch.object(app.runner, "run") as run:
            app.updates._confirm_autoremove([])
        assert [p.title for p in shown] == ["Nothing to Clean Up"]
        assert [b for b, _ in shown[0].buttons] == ["ok"]
        run.assert_not_called()

    def test_lists_packages_before_running(self, app):
        shown = answer(app, "yes")
        with patch.object(app.runner, "run") as run:
            app.updates._confirm_autoremove(["libold-1.0-1.fc44"])
        assert "libold-1.0-1.fc44" in shown[0].details
        assert shown[0].destructive
        run.assert_called_once_with(app.backend.build_autoremove_command(), "Autoremove")

    def test_declined_runs_nothing(self, app):
        answer(app, "no")
        with patch.object(app.runner, "run") as run:
            app.updates._confirm_autoremove(["libold-1.0-1.fc44"])
        run.assert_not_called()

    def test_one_preview_at_a_time(self, app):
        app.updates._autoremove_worker = type("W", (), {"isRunning": lambda self: True})()
        with patch("dnf_gui.ui.controllers.updates.CallWorker") as worker:
            app.updates.autoremove()
        worker.assert_not_called()
