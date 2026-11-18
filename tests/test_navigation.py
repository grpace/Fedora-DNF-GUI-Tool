"""Getting to a page: the stable page keys (Ctrl+1..9, ``--page``,
notification clicks and the single-instance socket all use them), the
"terminal" key that opens the output instead of a page, and a second launch
handing its request to the running app.

The real key presses are in test_qml_window.py.
"""

import os
from unittest.mock import patch

from dnf_gui.app import DESKTOP_FILE_NAME, PAGE_CHOICES, _parse_args
from dnf_gui.ui.controllers.app_controller import PAGES
from tests.conftest import new_controller

# Ctrl+1..9, in order. "terminal" is a stable key, not a page: it opens the
# output (notifications' Show Output and `--page terminal` use it too).
ORDER = ("updates", "installed", "flatpak", "sysinfo", "tools", "repos",
         "history", "terminal", "settings")


def test_page_keys_keep_their_order():
    assert PAGES == ORDER


def test_ctrl_numbers_open_pages_in_order(app):
    with patch.object(app, "refreshCurrent"):  # no real dnf queries
        for index, key in enumerate(ORDER):
            if key != "terminal":
                app.navigateIndex(index)
                assert app.currentPage == key, index


def test_terminal_opens_the_output_instead_of_a_page(app):
    terminal = ORDER.index("terminal")
    with patch.object(app, "refreshCurrent"):
        app.navigateIndex(ORDER.index("installed"))
        app.navigateIndex(terminal)
        assert app.activityExpanded and app.activityVisible
        assert app.currentPage == "installed"  # the page stays
        app.navigateIndex(terminal)            # pressed again: collapse
        assert not app.activityExpanded
        app.navigate("terminal")
        assert app.activityExpanded
        assert app.currentPage == "installed"


def test_out_of_range_index_is_ignored(app):
    with patch.object(app, "refreshCurrent") as refresh:
        app.navigateIndex(9)
        app.navigateIndex(-1)
    refresh.assert_not_called()
    assert app.currentPage == "updates"


def test_ctrl_u_shows_updates_and_runs_the_favorite(app):
    with patch.object(app, "refreshCurrent"):
        app.navigate("settings")
        with patch.object(app.updates, "runFavorite") as run:
            app.runFavoriteUpdate()
    assert app.currentPage == "updates"
    run.assert_called_once()


# ── --page and activation ────────────────────────────────────────────

def test_page_argument_ignores_qt_options():
    args = _parse_args(["-platform", "offscreen", "--page", "terminal"])
    assert args.page == "terminal"
    assert not args.check


def test_every_page_choice_exists_in_the_window():
    assert set(PAGE_CHOICES) == set(PAGES)


def test_desktop_file_name_has_no_suffix():
    from pathlib import Path
    assert not DESKTOP_FILE_NAME.endswith(".desktop")
    root = Path(__file__).resolve().parent.parent
    assert (root / "assets" / f"{DESKTOP_FILE_NAME}.desktop").exists()


def test_activating_updates_rescans(monkeypatch):
    monkeypatch.delenv("XDG_ACTIVATION_TOKEN", raising=False)
    app = new_controller(initial_page="terminal")
    assert app.activityExpanded  # "terminal" opens the output
    app.updates._cache = {"dnf": None}
    with patch.object(app.updates, "check") as check:
        app.activate("updates", "tok")
    assert app.currentPage == "updates"
    check.assert_called_once()  # the cached scan predates the reminder
    assert os.environ.pop("XDG_ACTIVATION_TOKEN", "") == "tok"


def test_activating_another_page_switches_to_it(app):
    with patch.object(app, "refreshCurrent"):
        app.activate("settings")
    assert app.currentPage == "settings"
    app.activate("terminal")
    assert app.activityExpanded
    assert app.currentPage == "settings"


# ── single instance ──────────────────────────────────────────────────

def test_requests_keep_only_known_strings():
    from dnf_gui.core.single_instance import parse_request
    assert parse_request(b'{"page": "updates", "token": "t", "x": 1}') == \
        {"page": "updates", "token": "t"}
    assert parse_request(b'{"page": ["rm"]}') is None
    assert parse_request(b"not json") is None


def test_second_launch_reaches_the_first(tmp_path, monkeypatch):
    import gc
    from PyQt6.QtCore import QThread
    from dnf_gui.core import single_instance
    from tests.conftest import wait_until
    gc.collect()  # free earlier tests' controllers before pumping events
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    assert not single_instance.forward_to_running({"page": "x"}, 200)
    server = single_instance.InstanceServer()
    assert server.listen()
    got = []
    server.request_received.connect(got.append)

    class Client(QThread):
        ok = None

        def run(self):
            self.ok = single_instance.forward_to_running({"page": "updates", "token": "t"}, 3000)

    client = Client()
    client.start()
    assert wait_until(client.isFinished)
    client.wait()
    assert client.ok
    assert wait_until(lambda: got)
    assert got == [{"page": "updates", "token": "t"}]
