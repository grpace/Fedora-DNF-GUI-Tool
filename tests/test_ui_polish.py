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




class TestAlignmentAndPolish(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _ensure_app()

    def test_repolist_parsing_status(self):
        from dnf_gui.core.dnf_backend import DNFBackend
        from unittest.mock import patch
        sample_output = "\n".join([
            "repo id                                            repo name                                                  status",
            "brave-browser                                      Brave Browser                                              enabled",
            "copr:copr.fedorainfracloud.org:avengemedia:dms     Copr repo for dms owned by avengemedia                     disabled",
            "fedora                                             Fedora 43 - x86_64                                         enabled",
        ])
        b = DNFBackend()
        with patch.object(b, "_run", return_value=sample_output):
            repos = b.list_repos(show_all=True)
            self.assertEqual(len(repos), 3)
            self.assertEqual(repos[0]["id"], "brave-browser")
            self.assertEqual(repos[0]["name"], "Brave Browser")
            self.assertTrue(repos[0]["enabled"])
            self.assertEqual(repos[1]["id"], "copr:copr.fedorainfracloud.org:avengemedia:dms")
            self.assertEqual(repos[1]["name"], "Copr repo for dms owned by avengemedia")
            self.assertFalse(repos[1]["enabled"])

    def test_history_parsing_packagekit(self):
        from dnf_gui.core.dnf_backend import DNFBackend
        from unittest.mock import patch
        sample_output = "\n".join([
            "    ID Command line                         Date and time       Action(s) Altered",
            "   242 /usr/bin/dnf5 upgrade -y --refresh   2026-09-09 13:03:56               126",
            "   238                                      2026-09-05 05:51:10                 2",
        ])
        b = DNFBackend()
        with patch.object(b, "_run", return_value=sample_output):
            txns = b.history()
            self.assertEqual(len(txns), 2)
            self.assertEqual(txns[0]["id"], "242")
            self.assertEqual(txns[0]["altered"], "126")
            self.assertEqual(txns[1]["id"], "238")
            self.assertEqual(txns[1]["command"], "System / PackageKit")
            self.assertEqual(txns[1]["altered"], "2")

    def test_toolkit_buttons_uniform_width(self):
        from dnf_gui.ui.pages.toolkit_page import ToolkitPage, ToolCard
        from PyQt6.QtWidgets import QPushButton
        page = ToolkitPage()
        page.show()
        self.addCleanup(page.close)
        self.addCleanup(page.deleteLater)
        cards = page.findChildren(ToolCard)
        self.assertGreater(len(cards), 0)
        for card in cards:
            btn = card.findChild(QPushButton)
            self.assertIsNotNone(btn)
            self.assertEqual(btn.width(), 120)

    def test_history_card_altered_alignment(self):
        from dnf_gui.ui.pages.history_page import HistoryCard
        from PyQt6.QtWidgets import QLabel
        from PyQt6.QtCore import Qt
        card = HistoryCard({"id": "242", "command": "upgrade", "date": "2026-09-09", "altered": "12"})
        card.show()
        self.addCleanup(card.close)
        self.addCleanup(card.deleteLater)
        labels = card.findChildren(QLabel, "card_detail")
        altered_label = next((lbl for lbl in labels if "12 packages altered" in lbl.text()), None)
        self.assertIsNotNone(altered_label)
        self.assertEqual(altered_label.width(), 160)
        self.assertTrue(altered_label.alignment() & Qt.AlignmentFlag.AlignRight)


    def test_repo_card_uniform_dimensions(self):
        from dnf_gui.ui.pages.repo_manager_page import RepoCard
        from PyQt6.QtWidgets import QPushButton, QLabel
        card_on = RepoCard({'id': 'fedora', 'name': 'Fedora', 'enabled': True})
        card_off = RepoCard({'id': 'copr:bar', 'name': 'Bar', 'enabled': False})
        for c in (card_on, card_off):
            c.show()
            self.addCleanup(c.close)
            self.addCleanup(c.deleteLater)
        btn_on = card_on.findChild(QPushButton)
        btn_off = card_off.findChild(QPushButton)
        badge_on = card_on.findChild(QLabel, 'badge_ok')
        badge_off = card_off.findChild(QLabel, 'badge_muted')
        self.assertEqual(btn_on.width(), 84)
        self.assertEqual(btn_off.width(), 84)
        self.assertEqual(btn_on.height(), btn_off.height())
        self.assertEqual(badge_on.width(), 96)
        self.assertEqual(badge_off.width(), 96)
        self.assertIn('Enabled', badge_on.text())
        self.assertIn('Disabled', badge_off.text())

    def test_history_detail_is_scrollable_text_edit(self):
        from dnf_gui.ui.pages.history_page import HistoryPage
        from PyQt6.QtWidgets import QPlainTextEdit
        page = HistoryPage()
        page.show()
        self.addCleanup(page.close)
        self.addCleanup(page.deleteLater)
        self.assertIsInstance(page._detail_text, QPlainTextEdit)
        self.assertTrue(page._detail_text.isReadOnly())
        page.show_detail("Line 1\nLine 2", txn_id="42")
        self.assertEqual(page._drawer_title.text(), 'Transaction #42 Details')
        self.assertEqual(page._detail_text.toPlainText(), "Line 1\nLine 2")

    def test_sidebar_brand_alignment(self):
        from dnf_gui.ui.sidebar import Sidebar
        from PyQt6.QtWidgets import QLabel
        from PyQt6.QtCore import QPoint
        sb = Sidebar()
        sb.show()
        self.addCleanup(sb.close)
        self.addCleanup(sb.deleteLater)
        t = sb.findChild(QLabel, "sidebar_title")
        sub = sb.findChild(QLabel, "sidebar_subtitle")
        self.assertIsNotNone(t)
        self.assertIsNotNone(sub)
        tx = t.mapTo(sb, QPoint(0, 0)).x()
        subx = sub.mapTo(sb, QPoint(0, 0)).x()
        self.assertEqual(tx, subx)


if __name__ == "__main__":
    unittest.main()
