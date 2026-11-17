"""Keyboard shortcuts: the QML Shortcut items call these AppController slots
(Ctrl+1..9 → navigateIndex, Ctrl+F → focusSearch, Ctrl+U → runFavoriteUpdate,
Ctrl+R → refreshCurrent)."""

import gc
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# v1's page order (main_window.PAGE_UPDATES..PAGE_SETTINGS = Ctrl+1..9).
V1_ORDER = ("updates", "installed", "flatpak", "sysinfo", "tools", "repos",
            "history", "terminal", "settings")


def _controller():
    # Free controllers left by earlier tests now, while none of their
    # threads run: a later processEvents() would otherwise fire their
    # pending start-up timers and GC could destroy a running QThread.
    gc.collect()
    from dnf_gui.ui.controllers.app_controller import AppController
    return AppController()


class TestNavigationShortcuts(unittest.TestCase):
    def test_ctrl_numbers_follow_v1_page_order(self):
        from dnf_gui.ui.controllers.app_controller import PAGES
        self.assertEqual(PAGES, V1_ORDER)
        app = _controller()
        with patch.object(app, "refreshCurrent"):  # no real dnf queries
            for index, key in enumerate(V1_ORDER):
                if key == "terminal":
                    continue
                app.navigateIndex(index)
                self.assertEqual(app.currentPage, key, index)

    def test_terminal_opens_activity_panel_instead_of_a_page(self):
        app = _controller()
        with patch.object(app, "refreshCurrent"):
            app.navigateIndex(V1_ORDER.index("installed"))
            app.navigateIndex(V1_ORDER.index("terminal"))
            self.assertTrue(app.activityExpanded)
            self.assertTrue(app.activityVisible)
            self.assertEqual(app.currentPage, "installed")  # page unchanged
            app.navigateIndex(V1_ORDER.index("terminal"))  # pressed again: collapse
            self.assertFalse(app.activityExpanded)
            app.navigate("terminal")
            self.assertTrue(app.activityExpanded)
            self.assertEqual(app.currentPage, "installed")

    def test_out_of_range_index_is_ignored(self):
        app = _controller()
        with patch.object(app, "refreshCurrent") as refresh:
            app.navigateIndex(9)
            app.navigateIndex(-1)
        refresh.assert_not_called()
        self.assertEqual(app.currentPage, "updates")


class TestFocusSearch(unittest.TestCase):
    def test_ctrl_f_asks_qml_to_focus_search(self):
        app = _controller()
        fired = []
        app.focusSearchRequested.connect(lambda: fired.append(True))
        app.focusSearch()
        self.assertEqual(fired, [True])


class TestRunFavorite(unittest.TestCase):
    def test_ctrl_u_shows_updates_and_runs_favorite(self):
        app = _controller()
        with patch.object(app, "refreshCurrent"):
            app.navigate("settings")
            with patch.object(app.updates, "runFavorite") as run:
                app.runFavoriteUpdate()
        self.assertEqual(app.currentPage, "updates")
        run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
