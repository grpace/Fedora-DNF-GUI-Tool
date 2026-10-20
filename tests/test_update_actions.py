"""Tests for the Updates page main button, favorites, and package rows."""

import unittest
from unittest.mock import patch

from PyQt6.QtWidgets import QApplication, QLabel

from dnf_gui.core.app_settings import UPDATE_MODE_KEYS, AppSettings
from dnf_gui.core.package import Package, PackageStatus, UpdateInfo
from dnf_gui.core.security import SecuritySummary
from dnf_gui.ui.widgets.package_card import PackageCard
from dnf_gui.ui.widgets.update_action_button import (
    MODES_BY_KEY, UpdateActionButton,
)


def _info(*names):
    return UpdateInfo(packages=[
        Package(name=n, version="1", status=PackageStatus.UPDATE_AVAILABLE)
        for n in names])


class TestUpdateActionButton(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_modes_match_settings_keys(self):
        self.assertEqual(tuple(MODES_BY_KEY), UPDATE_MODE_KEYS)

    def test_main_button_runs_favorite_only_when_enabled(self):
        button = UpdateActionButton()
        fired = []
        button.mode_triggered.connect(fired.append)
        button.set_favorite("security")
        self.assertEqual(button._main.text(), "Security Only")
        button.trigger_favorite()
        self.assertEqual(fired, [])  # nothing to do yet
        button.set_mode_state("security", True, "3 advisories")
        button._main.click()
        self.assertEqual(fired, ["security"])

    def test_starring_changes_favorite_and_emits(self):
        button = UpdateActionButton()
        changed = []
        button.favorite_changed.connect(changed.append)
        button._rows["minor"].starred.emit("minor")
        self.assertEqual(changed, ["minor"])
        self.assertEqual(button.favorite, "minor")
        self.assertEqual(button._main.text(), "Update without Major")

    def test_unknown_favorite_falls_back_to_default(self):
        button = UpdateActionButton()
        button.set_favorite("bogus")
        self.assertEqual(button.favorite, "all")


class TestUpdatesPageRows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _page(self):
        from dnf_gui.ui.pages.updates_page import UpdatesPage
        page = UpdatesPage()
        page.display_combined(_info("kernel-core", "firefox"), [object()],
                              SecuritySummary(total=2))
        return page

    def test_row_buttons_reach_page_signals(self):
        page = self._page()
        upgraded, details = [], []
        page.upgrade_package_clicked.connect(upgraded.append)
        page.details_requested.connect(details.append)
        card = page._list_container.findChildren(PackageCard)[0]
        card.install_clicked.emit(card.package.name)
        card.info_clicked.emit(card.package.name)
        self.assertEqual(upgraded, [card.package.name])
        self.assertEqual(details, [card.package.name])

    def test_held_back_rows_are_tagged(self):
        page = self._page()
        tags = {card.package.name: [l.text() for l in card.findChildren(QLabel)
                                    if l.objectName() == "badge_muted"]
                for card in page._list_container.findChildren(PackageCard)}
        self.assertEqual(tags, {"kernel-core": ["Major"], "firefox": []})
        self.assertIn("1 major (Update without Major skips these)", page._list_summary.text())
        card = [c for c in page._list_container.findChildren(PackageCard)
                if c.package.name == "kernel-core"][0]
        badge = [l for l in card.findChildren(QLabel) if l.objectName() == "badge_muted"][0]
        # The tooltip says why it's major and what that means.
        self.assertIn("kernel*", badge.toolTip())
        self.assertIn("Update without Major skips it", badge.toolTip())

    def test_mode_states_follow_scan(self):
        page = self._page()
        button = page._action_button
        for key in UPDATE_MODE_KEYS:
            self.assertTrue(button.is_mode_enabled(key), key)
        self.assertEqual(button._counts["everything"], "2 packages + 1 Flatpak")

    def test_filter_narrows_rows(self):
        page = self._page()
        page._filter_input.setText("fire")
        layout = page._list_layout
        names = [layout.itemAt(i).widget().package.name for i in range(layout.count())
                 if isinstance(layout.itemAt(i).widget(), PackageCard)]
        self.assertEqual(names, ["firefox"])

    def test_triggered_modes_map_to_signals(self):
        page = self._page()
        fired = []
        page.upgrade_without_major_clicked.connect(lambda: fired.append("minor"))
        page.update_everything_clicked.connect(lambda: fired.append("everything"))
        page._action_button.mode_triggered.emit("minor")
        page._action_button.mode_triggered.emit("everything")
        self.assertEqual(fired, ["minor", "everything"])


class TestFavoriteSetting(unittest.TestCase):
    def test_invalid_saved_value_falls_back(self):
        settings = AppSettings()
        with patch.object(settings, "get", return_value="bogus"):
            self.assertEqual(settings.update_favorite, "all")
        with patch.object(settings, "get", return_value="minor"):
            self.assertEqual(settings.update_favorite, "minor")


if __name__ == "__main__":
    unittest.main()


class TestSidebarHighlight(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_only_active_label_is_highlighted(self):
        from dnf_gui.ui.sidebar import Sidebar
        from dnf_gui.ui.styles.theme import get_palette, get_stylesheet
        self.app.setStyleSheet(get_stylesheet("dark"))
        sidebar = Sidebar()
        sidebar.show()
        sidebar.set_active_page(0)
        sidebar.set_active_page(1)
        self.app.processEvents()
        accent = get_palette("dark")["accent"].lower()
        colors = [b._text_label.palette().windowText().color().name()
                  for b in sidebar._buttons[:2]]
        self.assertNotEqual(colors[0], accent)
        self.assertEqual(colors[1], accent)
        self.app.setStyleSheet("")
