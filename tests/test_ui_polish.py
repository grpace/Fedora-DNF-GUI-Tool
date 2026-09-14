"""Tests for the UI polish batch: theme system, updates cache, reboot dismiss."""

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


class TestThemeSystem(unittest.TestCase):
    def test_button_variants_exist(self):
        from dnf_gui.ui.styles.theme import get_stylesheet
        sheet = get_stylesheet()
        for name in ("primary_button", "success_button", "accent_button",
                     "warning_button", "danger_button", "ghost_button"):
            self.assertIn(f"QPushButton#{name}", sheet, name)
        self.assertIn('[compact="true"]', sheet)

    def test_checkbox_and_labels_exist(self):
        from dnf_gui.ui.styles.theme import get_stylesheet
        sheet = get_stylesheet()
        self.assertIn("QCheckBox::indicator", sheet)
        self.assertIn("QCheckBox::indicator:checked", sheet)
        for name in ("hint", "section_label", "status_line", "reboot_banner"):
            self.assertIn(name, sheet)

    def test_no_inline_button_styles_remain(self):
        import pathlib
        src = pathlib.Path(__file__).resolve().parent.parent / "src" / "dnf_gui"
        offenders = []
        for path in (src / "ui" / "pages").glob("*.py"):
            text = path.read_text()
            # Inline QPushButton{...} blocks are banned; semantic label
            # colors and card gradients are fine.
            if "QPushButton {" in text or "QPushButton{" in text:
                offenders.append(path.name)
        for path in (src / "ui" / "widgets").glob("*.py"):
            text = path.read_text()
            if "QPushButton {" in text or "QPushButton{" in text:
                offenders.append(f"widgets/{path.name}")
        self.assertEqual(offenders, [])


class TestUpdatesCache(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _ensure_app()

    def _window(self):
        from dnf_gui.ui.main_window import MainWindow
        window = MainWindow()
        self.addCleanup(window.close)
        self.addCleanup(window.deleteLater)
        return window

    def _cached_result(self):
        from dnf_gui.core.package import UpdateInfo
        from dnf_gui.core.security import SecuritySummary
        return {
            "dnf": UpdateInfo(total_updates=0, last_checked="2026-09-14 09:44 PM"),
            "flatpak": [],
            "security": SecuritySummary(),
            "preview": None,
            "security_preview": None,
            "reboot": False,
        }

    def test_revisit_reuses_cache_without_rescan(self):
        from dnf_gui.ui.main_window import PAGE_UPDATES
        window = self._window()
        window._stack.setCurrentIndex(PAGE_UPDATES)
        window._updates_cache = self._cached_result()
        with patch.object(window, "_check_updates") as check:
            window._refresh_current()
        check.assert_not_called()
        self.assertIn("up to date", window._updates_page._empty_label.text().lower())

    def test_empty_cache_triggers_scan(self):
        from dnf_gui.ui.main_window import PAGE_UPDATES
        window = self._window()
        window._stack.setCurrentIndex(PAGE_UPDATES)
        window._updates_cache = None
        with patch.object(window, "_check_updates") as check:
            window._refresh_current()
        check.assert_called_once()

    def test_successful_command_invalidates_cache(self):
        window = self._window()
        window._updates_cache = self._cached_result()
        window._on_command_done(0, "System Upgrade")
        self.assertIsNone(window._updates_cache)

    def test_failed_command_keeps_cache(self):
        window = self._window()
        window._updates_cache = self._cached_result()
        window._on_command_done(1, "System Upgrade")
        self.assertIsNotNone(window._updates_cache)


class TestRebootDismiss(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _ensure_app()

    def test_page_header_inset(self):
        """Headings sit at 20px (aligned with body content)."""
        from PyQt6.QtWidgets import QLabel
        from PyQt6.QtCore import QPoint
        from dnf_gui.ui.pages.updates_page import UpdatesPage
        from dnf_gui.ui.pages.settings_page import SettingsPage
        from dnf_gui.ui.pages.history_page import HistoryPage
        for cls in (UpdatesPage, SettingsPage, HistoryPage):
            page = cls()
            page.show()
            page.resize(1100, 750)
            self.addCleanup(page.close)
            self.addCleanup(page.deleteLater)
            title = page.findChild(QLabel, "page_header")
            self.assertIsNotNone(title, cls.__name__)
            title_x = title.mapTo(page, QPoint(0, 0)).x()
            self.assertEqual(title_x, 20, cls.__name__)

    def test_page_header_action_variant(self):
        from dnf_gui.ui.pages.history_page import HistoryPage
        from dnf_gui.ui.widgets.page_header import PageHeader
        page = HistoryPage()
        page.show()
        self.addCleanup(page.close)
        self.addCleanup(page.deleteLater)
        headers = page.findChildren(PageHeader)
        self.assertEqual(len(headers), 1)
        self.assertEqual(headers[0].title_label.text(), "Transaction History")

    def test_dismiss_survives_redisplay_until_fresh_scan(self):
        from dnf_gui.ui.pages.updates_page import UpdatesPage
        from dnf_gui.core.package import UpdateInfo
        page = UpdatesPage()
        page.show()
        self.addCleanup(page.close)
        page.set_reboot_banner(True)
        self.assertFalse(page._reboot_banner.isHidden())
        page._dismiss_reboot_banner()
        page.set_reboot_banner(True)  # e.g. post-upgrade recheck
        self.assertTrue(page._reboot_banner.isHidden())
        # A fresh scan resets the dismissal
        page.display_combined(UpdateInfo(), [], None, reboot=True)
        self.assertFalse(page._reboot_banner.isHidden())


class TestSettingsPolish(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _ensure_app()

    def _page(self):
        from dnf_gui.ui.pages.settings_page import SettingsPage
        page = SettingsPage()
        page.show()
        self.addCleanup(page.close)
        self.addCleanup(page.deleteLater)
        return page

    def test_section_titles_have_no_em_dash(self):
        from PyQt6.QtWidgets import QLabel
        page = self._page()
        sections = [w for w in page.findChildren(QLabel)
                    if w.objectName() == "section_label"]
        self.assertGreater(len(sections), 0)
        for label in sections:
            self.assertNotIn("—", label.text(), label.text)

    def test_advanced_options_hidden_until_toggled(self):
        page = self._page()
        self.assertTrue(page._disc_advanced.isHidden())
        page._btn_disc_advanced.setChecked(True)
        self.assertFalse(page._disc_advanced.isHidden())
        self.assertIn("Hide", page._btn_disc_advanced.text())
        page._btn_disc_advanced.setChecked(False)
        self.assertTrue(page._disc_advanced.isHidden())

    def test_discover_status_is_plain_language(self):
        from types import SimpleNamespace
        page = self._page()

        def show(**kwargs):
            base = dict(discover_installed=True,
                        system_autostart_present=True,
                        per_user_override_present=False,
                        per_user_disabled=False,
                        notifier_running=False,
                        notification_interval="-1",
                        unattended_updates="false",
                        notifications_silenced=True,
                        packagekit_offline_active=False)
            base.update(kwargs)
            page.display_discover_status(SimpleNamespace(**base))

        # Active takeover: banner ok, only Restore offered.
        show(per_user_disabled=True)
        self.assertEqual(page._discover_banner.objectName(), "status_ok")
        self.assertIn("This app handles updates", page._discover_title.text())
        self.assertFalse(page._btn_takeover.isVisibleTo(page))
        self.assertTrue(page._btn_restore.isVisibleTo(page))

        # Discover checking on its own: banner warn, only Takeover offered.
        show(notifier_running=True, packagekit_offline_active=True)
        self.assertEqual(page._discover_banner.objectName(), "status_warn")
        self.assertTrue(page._btn_takeover.isVisibleTo(page))
        self.assertFalse(page._btn_restore.isVisibleTo(page))
        self.assertIn("running right now", page._discover_status.text())
        self.assertIn("restart", page._discover_status.text())

        # Nothing installed: no jargon, no actions.
        show(discover_installed=False, system_autostart_present=False)
        self.assertEqual(page._discover_banner.objectName(), "status_info")
        self.assertFalse(page._btn_takeover.isVisibleTo(page))
        self.assertFalse(page._btn_restore.isVisibleTo(page))

        for widget in (page._discover_title, page._discover_status):
            self.assertNotIn("—", widget.text())
            for jargon in ("PlasmaDiscoverUpdates", "packagekit-offline-update",
                           "DiscoverNotifier", "autostart"):
                self.assertNotIn(jargon, widget.text())

    def test_passwordless_status_has_no_em_dash(self):
        page = self._page()
        for remembered, live in (("off", "off"), ("updates", "updates"),
                                 ("updates", "off"), ("off", "full")):
            page.display_passwordless_status(remembered, live)
            self.assertNotIn("—", page._pw_status.text())


if __name__ == "__main__":
    unittest.main()
