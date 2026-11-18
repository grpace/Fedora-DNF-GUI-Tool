"""The other pages' controllers: Installed (search, install, remove,
details), Flatpak (remotes, search), History (details, undo) and Tools."""

from unittest.mock import patch

from dnf_gui.core.flatpak_backend import FlatpakApp, FlatpakBackend, pick_remote
from dnf_gui.core.package import Package, PackageStatus
from dnf_gui.ui.controllers.pages import describe_actions
from tests.conftest import answer, wait_until


# ── Installed ────────────────────────────────────────────────────────

def test_install_confirms_then_runs_the_exact_command(app):
    shown = answer(app, "yes")
    with patch.object(app.runner, "run") as run:
        app.packages.install("htop")
    assert shown[0].title == "Install Package?"
    run.assert_called_once_with(app.backend.build_install_command("htop"), "Installing htop")


def test_install_declined_runs_nothing(app):
    answer(app, "no")
    with patch.object(app.runner, "run") as run:
        app.packages.install("htop")
    run.assert_not_called()


def test_remove_is_destructive_and_defaults_to_no(app):
    shown = answer(app)  # the default answer
    with patch.object(app.runner, "run") as run:
        app.packages.remove("htop")
    assert shown[0].destructive and shown[0].default == "no"
    run.assert_not_called()
    answer(app, "yes")
    with patch.object(app.runner, "run") as run:
        app.packages.remove("htop")
    run.assert_called_once_with(app.backend.build_remove_command("htop"), "Removing htop")


def test_stale_search_results_are_ignored(app):
    packages = app.packages
    packages._search_generation = 2  # "ht" was 1, "htop" is 2
    packages._on_search(1, [Package(name="old", version="")])
    assert packages.results.count == 0
    packages._on_search(2, [
        Package(name="htop", version="3.4", status=PackageStatus.INSTALLED),
        Package(name="neohtop", version="")])
    rows = packages.results.rows()
    assert [r["name"] for r in rows] == ["htop", "neohtop"]
    assert [r["name"] for r in rows if r["installed"]] == ["htop"]
    assert packages.searchDone


def test_open_details_reload_after_an_operation(app):
    app.packages._details_name = "htop"
    with patch.object(app.packages, "loadDetails") as load:
        app._on_operation_finished(0, "Installing htop", False)
    load.assert_called_once_with("htop")


# ── Flatpak ──────────────────────────────────────────────────────────

def test_install_prefers_flathub_then_the_listed_remote():
    assert pick_remote("") == "flathub"
    assert pick_remote("fedora,flathub") == "flathub"
    assert pick_remote("fedora") == "fedora"
    assert pick_remote("--user") == "flathub"  # never an option
    cmd = FlatpakBackend().build_install_command("org.example.App", "fedora")
    assert cmd[-2:] == ["fedora", "org.example.App"]


def test_search_marks_installed_apps(app):
    flatpak = app.flatpak
    flatpak._on_loaded([FlatpakApp(name="A", application_id="org.a.A")])
    flatpak._search_generation = 1
    flatpak._on_search(1, [
        FlatpakApp(name="A", application_id="org.a.A", origin="flathub"),
        FlatpakApp(name="B", application_id="org.b.B", origin="fedora")])
    installed = {r["appId"]: r["installed"] for r in flatpak.results.rows()}
    assert installed == {"org.a.A": True, "org.b.B": False}


def test_flathub_search_error_is_shown_not_read_as_no_results(app):
    shown = answer(app)
    app.flatpak._search_generation = 3
    app.flatpak._on_search_error(3, "flatpak: network unreachable")
    assert shown[-1].title == "Flathub Search Failed"
    assert app.flatpak.searchError == "flatpak: network unreachable"
    assert app.flatpak.searchDone and not app.flatpak.searching
    app.flatpak.search("")   # clearing the box clears the error
    assert app.flatpak.searchError == ""


# ── History ──────────────────────────────────────────────────────────

def test_history_detail_loads_for_the_selected_transaction(app):
    history = app.history
    with patch.object(app.backend, "history_info", return_value="Line 1\nLine 2"):
        history.loadDetail("42")
        assert history.detailLoading
        assert wait_until(lambda: not history.detailLoading)
    assert history.detailId == "42"
    assert history.detailText == "Line 1\nLine 2"
    history._on_detail("41", "stale")  # an older request finishing late
    assert history.detailText == "Line 1\nLine 2"


def test_undo_confirms_then_runs(app):
    shown = answer(app, "yes")
    with patch.object(app.runner, "run") as run:
        app.history.undo("42")
    assert shown[0].destructive
    run.assert_called_once_with(app.backend.build_history_undo_command("42"),
                                "Undoing transaction #42")
    answer(app, "no")
    with patch.object(app.runner, "run") as run:
        app.history.undo("42")
    run.assert_not_called()


def test_dnf5_history_action_letters_become_words():
    assert describe_actions("E, I, U") == "Removed, Install, Upgrade"
    assert describe_actions("U") == "Upgrade"
    assert describe_actions("Upgrade") == "Upgrade"   # dnf4 words unchanged
    assert describe_actions("") == ""


# ── Tools ────────────────────────────────────────────────────────────

def test_firmware_update_is_confirmed_as_destructive(app):
    shown = answer(app, "no")
    with patch.object(app.runner, "run") as run:
        app.system.runTool("firmware_update")
    assert shown[-1].destructive and "BIOS/UEFI" in shown[-1].text
    run.assert_not_called()
