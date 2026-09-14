"""Tests for Ctrl+F search focus (README-promised shortcut)."""

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

_app = None


def _ensure_app():
    global _app
    if _app is None:
        _app = QApplication([])
    return _app


class TestFocusSearch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _ensure_app()

    def test_installed_focuses_search(self):
        from dnf_gui.ui.pages.installed_page import InstalledPage
        page = InstalledPage()
        with patch.object(page._search_input, "setFocus") as focus, \
             patch.object(page._search_input, "selectAll") as select:
            page.focus_search()
        focus.assert_called_once()
        select.assert_called_once()

    def test_flatpak_focuses_active_tab_input(self):
        from dnf_gui.ui.pages.flatpak_page import FlatpakPage
        page = FlatpakPage()
        page._tabs.setCurrentIndex(0)
        with patch.object(page._filter_input, "setFocus") as focus:
            page.focus_search()
        focus.assert_called_once()
        page._tabs.setCurrentIndex(1)
        with patch.object(page._search_input, "setFocus") as focus:
            page.focus_search()
        focus.assert_called_once()

    def test_repos_focuses_filter(self):
        from dnf_gui.ui.pages.repo_manager_page import RepoManagerPage
        page = RepoManagerPage()
        with patch.object(page._filter_input, "setFocus") as focus:
            page.focus_search()
        focus.assert_called_once()

    def test_main_window_dispatch(self):
        from dnf_gui.ui.main_window import (
            MainWindow, PAGE_INSTALLED, PAGE_UPDATES,
        )
        window = MainWindow()
        try:
            window._stack.setCurrentIndex(PAGE_INSTALLED)
            with patch.object(window._installed_page, "focus_search") as focus:
                window._focus_search()
            focus.assert_called_once()
            # Pages without search are a harmless no-op
            window._stack.setCurrentIndex(PAGE_UPDATES)
            window._focus_search()
        finally:
            window.close()
            window.deleteLater()


if __name__ == "__main__":
    unittest.main()
