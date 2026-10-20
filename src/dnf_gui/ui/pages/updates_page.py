"""Updates page — check, view, and apply system and Flatpak updates."""

from datetime import date

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QFrame, QComboBox,
)
from PyQt6.QtCore import pyqtSignal, Qt

from dnf_gui.core.dnf_backend import DEFAULT_HELD_BACK_PATTERNS, is_held_back
from dnf_gui.core.release_upgrade import ReleaseUpgrade
from dnf_gui.core.package import UpdateInfo
from dnf_gui.core.security import SecuritySummary
from dnf_gui.core.flatpak_backend import FlatpakApp
from dnf_gui.ui.widgets.package_card import PackageCard
from dnf_gui.ui.widgets.update_action_button import UpdateActionButton

# Building hundreds of card widgets is slow; the filter finds the rest.
MAX_ROWS = 150


def _format_day(iso_day: str) -> str:
    """Format an ISO day such as 2027-06-02 as "June 2, 2027" ('' if invalid)."""
    try:
        day = date.fromisoformat(iso_day)
    except (TypeError, ValueError):
        return ""
    return f"{day:%B} {day.day}, {day.year}"


class UpdatesPage(QWidget):
    """Page displaying available system updates."""

    check_updates_clicked = pyqtSignal()
    upgrade_all_clicked = pyqtSignal()
    update_everything_clicked = pyqtSignal()
    security_upgrade_clicked = pyqtSignal()
    upgrade_without_major_clicked = pyqtSignal()
    favorite_changed = pyqtSignal(str)  # update mode key
    upgrade_package_clicked = pyqtSignal(str)
    details_requested = pyqtSignal(str)  # package name
    autoremove_clicked = pyqtSignal()
    reboot_requested = pyqtSignal()
    hold_toggled = pyqtSignal(str, bool)       # package name, hold?
    release_upgrade_clicked = pyqtSignal(int)  # target Fedora release
    release_install_clicked = pyqtSignal(int)  # reboot into downloaded upgrade
    release_cancel_clicked = pyqtSignal()      # discard downloaded upgrade
    release_dismissed = pyqtSignal(int)        # "Not now" for this release
    release_notes_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._update_info = None
        self._flatpak_count = 0
        self._security_total = 0
        self._package_severity: dict[str, str] = {}
        self._release_upgrade: ReleaseUpgrade | None = None
        self._dismissed_release = 0
        self.upgrade_preview = None
        self.security_preview = None
        self._held_back_patterns = list(DEFAULT_HELD_BACK_PATTERNS)
        self._setup_ui()

    def _setup_ui(self):
        from dnf_gui.ui.widgets.page_header import PageHeader
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(PageHeader(
            "System Updates", "Keep Your System Secure and Up to Date"))

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(20, 0, 20, 20)
        body_layout.setSpacing(14)
        layout.addWidget(body, 1)

        # ── Stats Row ──
        stats_row = QHBoxLayout()
        stats_row.setSpacing(12)
        self._total_card = self._create_stat_card("...", "Available Updates")
        self._security_card = self._create_stat_card("—", "Security Advisories")
        self._flatpak_card = self._create_stat_card("—", "Flatpak Updates")
        self._last_check_card = self._create_stat_card("—", "Last Checked")
        for card in (self._total_card, self._security_card,
                     self._flatpak_card, self._last_check_card):
            stats_row.addWidget(card, 1)
        body_layout.addLayout(stats_row)

        # ── Action Bar: one main update button, a rescan, and cleanup ──
        action_bar = QHBoxLayout()
        action_bar.setSpacing(10)

        self._action_button = UpdateActionButton()
        self._action_button.mode_triggered.connect(self._on_mode_triggered)
        self._action_button.favorite_changed.connect(self.favorite_changed.emit)
        action_bar.addWidget(self._action_button)

        self._check_btn = QPushButton("Check for Updates")
        self._check_btn.setObjectName("ghost_button")
        self._check_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._check_btn.setToolTip("Refresh metadata and scan for updates (Ctrl+R)")
        self._check_btn.clicked.connect(self.check_updates_clicked.emit)
        action_bar.addWidget(self._check_btn)

        action_bar.addStretch()

        self._autoremove_btn = QPushButton("Clean Up")
        self._autoremove_btn.setObjectName("ghost_button")
        self._autoremove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._autoremove_btn.setToolTip("Remove unneeded dependencies (dnf autoremove)")
        self._autoremove_btn.clicked.connect(self.autoremove_clicked.emit)
        action_bar.addWidget(self._autoremove_btn)
        body_layout.addLayout(action_bar)

        # ── Reboot Banner ──
        self._reboot_banner = QFrame()
        self._reboot_banner.setObjectName("reboot_banner")
        self._reboot_dismissed = False
        banner_layout = QHBoxLayout(self._reboot_banner)
        banner_layout.setContentsMargins(16, 10, 16, 10)
        banner_layout.setSpacing(12)
        banner_label = QLabel(
            "Reboot Required — A kernel or core library was updated. "
            "Reboot to finish applying updates.")
        banner_label.setObjectName("reboot_banner_text")
        banner_label.setWordWrap(True)
        banner_layout.addWidget(banner_label, 1)
        self._reboot_btn = QPushButton("Reboot Now")
        self._reboot_btn.setObjectName("warning_button")
        self._reboot_btn.setProperty("compact", True)
        self._reboot_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._reboot_btn.clicked.connect(self.reboot_requested.emit)
        banner_layout.addWidget(self._reboot_btn)
        self._reboot_dismiss = QPushButton("Later")
        self._reboot_dismiss.setObjectName("ghost_button")
        self._reboot_dismiss.setProperty("compact", True)
        self._reboot_dismiss.setCursor(Qt.CursorShape.PointingHandCursor)
        self._reboot_dismiss.clicked.connect(self._dismiss_reboot_banner)
        banner_layout.addWidget(self._reboot_dismiss)
        body_layout.addWidget(self._reboot_banner)
        self._reboot_banner.hide()

        # ── Fedora Release Upgrade Banner ──
        self._release_banner = QFrame()
        self._release_banner.setObjectName("status_info")
        release_layout = QHBoxLayout(self._release_banner)
        release_layout.setContentsMargins(4, 0, 0, 0)
        release_layout.setSpacing(12)
        release_text = QVBoxLayout()
        release_text.setSpacing(2)
        self._release_title = QLabel("")
        self._release_title.setObjectName("status_title")
        self._release_detail = QLabel("")
        self._release_detail.setObjectName("status_detail")
        self._release_detail.setWordWrap(True)
        release_text.addWidget(self._release_title)
        release_text.addWidget(self._release_detail)
        release_layout.addLayout(release_text, 1)
        self._release_primary = self._compact_button("", "primary_button")
        self._release_primary.clicked.connect(self._on_release_primary)
        self._release_notes = self._compact_button("What's New", "ghost_button")
        self._release_notes.clicked.connect(self.release_notes_clicked.emit)
        self._release_secondary = self._compact_button("", "ghost_button")
        self._release_secondary.clicked.connect(self._on_release_secondary)
        for button in (self._release_primary, self._release_notes, self._release_secondary):
            release_layout.addWidget(button)
        body_layout.addWidget(self._release_banner)
        self._release_banner.hide()

        # ── List Header: summary + filter ──
        list_header = QHBoxLayout()
        list_header.setSpacing(12)
        self._list_summary = QLabel("")
        self._list_summary.setObjectName("hint")
        list_header.addWidget(self._list_summary, 1)
        self._filter_input = QLineEdit()
        self._filter_input.setObjectName("search_input")
        self._filter_input.setPlaceholderText("Filter updates...")
        self._filter_input.setClearButtonEnabled(True)
        self._filter_input.setFixedWidth(260)
        self._filter_input.textChanged.connect(self._render_list)
        list_header.addWidget(self._filter_input)
        self._show_combo = QComboBox()
        self._show_combo.addItem("All updates", "all")
        self._show_combo.addItem("Security updates", "security")
        self._show_combo.addItem("Major updates", "held")
        self._show_combo.setToolTip("Show only some of the pending updates")
        self._show_combo.currentIndexChanged.connect(self._render_list)
        list_header.addWidget(self._show_combo)
        body_layout.addLayout(list_header)

        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        body_layout.addWidget(sep)

        # ── Updates List ──
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(6)
        self._list_layout.addStretch()
        self._scroll.setWidget(self._list_container)
        body_layout.addWidget(self._scroll, 1)

        # ── Empty State ──
        self._empty_label = QLabel(
            "Click 'Check for Updates' to scan for available updates\n\n"
            "Keyboard shortcuts:\n"
            "Ctrl+R  Check for updates\n"
            "Ctrl+U  Run your main update option\n"
            "Ctrl+F  Filter the update list\n"
            "Ctrl+T  Open the live terminal"
        )
        self._empty_label.setObjectName("loading_label")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._list_layout.insertWidget(0, self._empty_label)

        self._more_label = QLabel("")
        self._more_label.setObjectName("caption")
        self._more_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._more_label.hide()

    @staticmethod
    def _compact_button(text: str, style: str) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName(style)
        button.setProperty("compact", True)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        return button

    def _create_stat_card(self, value: str, label: str) -> QFrame:
        """Create an elevated stat card."""
        card = QFrame()
        card.setObjectName("stats_card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(2)

        val_label = QLabel(value)
        val_label.setObjectName("stats_number")
        layout.addWidget(val_label)

        lbl = QLabel(label)
        lbl.setObjectName("stats_label")
        layout.addWidget(lbl)

        card._val_label = val_label
        card._text_label = lbl
        return card

    # ─── Main update button ─────────────────────────────────────

    def _on_mode_triggered(self, key: str) -> None:
        {
            "all": self.upgrade_all_clicked,
            "everything": self.update_everything_clicked,
            "minor": self.upgrade_without_major_clicked,
            "security": self.security_upgrade_clicked,
        }[key].emit()

    def set_favorite(self, key: str) -> None:
        self._action_button.set_favorite(key)

    def trigger_favorite(self) -> None:
        """Run the starred update option (Ctrl+U)."""
        self._action_button.trigger_favorite()

    def apply_theme(self) -> None:
        self._action_button.apply_theme()

    def focus_search(self) -> None:
        self._filter_input.setFocus()
        self._filter_input.selectAll()

    def _update_action_states(self) -> None:
        dnf = len(self._update_info.packages) if self._update_info else 0
        flatpak = self._flatpak_count
        minor = len(self.minor_package_names())
        held = len(self.held_back_package_names())
        button = self._action_button
        button.set_mode_state("all", dnf > 0, f"{dnf} packages")
        button.set_mode_state(
            "everything", dnf + flatpak > 0,
            f"{dnf} packages + {flatpak} Flatpak" if flatpak else f"{dnf} packages")
        button.set_mode_state(
            "minor", minor > 0,
            f"{minor} packages (skips {held} major)" if held else f"{minor} packages")
        button.set_mode_state(
            "security", self._security_total > 0, f"{self._security_total} advisories")

    # ─── Reboot banner ──────────────────────────────────────────

    def set_reboot_banner(self, visible: bool) -> None:
        """Show/hide the reboot required banner (honors Later dismissal)."""
        self._reboot_banner.setVisible(bool(visible) and not self._reboot_dismissed)

    def _dismiss_reboot_banner(self) -> None:
        """Hide the banner until the next fresh scan."""
        self._reboot_dismissed = True
        self._reboot_banner.hide()

    # ─── Fedora release upgrade banner ──────────────────────────

    def set_release_upgrade(self, upgrade: ReleaseUpgrade | None,
                            dismissed_release: int = 0) -> None:
        self._release_upgrade = upgrade
        self._dismissed_release = dismissed_release
        if upgrade is None or (not upgrade.downloaded
                               and upgrade.target <= dismissed_release):
            self._release_banner.hide()
            return
        target, current = upgrade.target, upgrade.current
        if upgrade.downloaded:
            self._release_title.setText(f"Fedora {target} is downloaded and ready to install")
            self._release_detail.setText(
                "Restart to install it. Installation runs before you log in, takes "
                "roughly 15–60 minutes, and must not be interrupted. Save your work first.")
            self._release_primary.setText("Restart && Install")
            self._release_secondary.setText("Cancel Upgrade")
            self._release_notes.hide()
        else:
            self._release_title.setText(f"Fedora {target} is available")
            detail = f"Upgrade from Fedora {current} to get the latest Fedora release."
            eol = _format_day(upgrade.current_eol)
            if eol:
                detail += f" Fedora {current} gets updates until {eol}."
            self._release_detail.setText(detail)
            self._release_primary.setText(f"Upgrade to Fedora {target}…")
            self._release_secondary.setText("Not Now")
            self._release_notes.show()
        self._release_banner.show()

    def _on_release_primary(self) -> None:
        upgrade = self._release_upgrade
        if upgrade is None:
            return
        if upgrade.downloaded:
            self.release_install_clicked.emit(upgrade.target)
        else:
            self.release_upgrade_clicked.emit(upgrade.target)

    def _on_release_secondary(self) -> None:
        upgrade = self._release_upgrade
        if upgrade is None:
            return
        if upgrade.downloaded:
            self.release_cancel_clicked.emit()
        else:
            self._release_banner.hide()
            self.release_dismissed.emit(upgrade.target)

    # ─── Results ────────────────────────────────────────────────

    @staticmethod
    def _format_checked(raw) -> str:
        text = str(raw).strip()
        day = text.split(" ")[0] if (" " in text and "-" in text) else text
        return "Today" if day == date.today().isoformat() else day

    def display_updates(self, info: UpdateInfo):
        """Display available system updates."""
        self._update_info = info
        if info and info.last_checked:
            self._last_check_card._val_label.setText(
                self._format_checked(info.last_checked))
        count = len(info.packages) if info and info.packages else 0
        self._total_card._val_label.setText(str(count))
        self._update_action_states()
        self._render_list()

    def display_combined(self, dnf_info: UpdateInfo | None,
                         flatpaks: list[FlatpakApp] | None,
                         security: SecuritySummary | None,
                         preview=None, security_preview=None,
                         reboot: bool = False) -> int:
        """Update the page from combined scan results. Returns total count."""
        self._reboot_dismissed = False
        self.upgrade_preview = preview
        self.security_preview = security_preview
        self.set_reboot_banner(bool(reboot))

        self._security_total = security.total if security else 0
        self._package_severity = dict(security.package_severity) if security else {}
        self._security_card._val_label.setText(
            str(self._security_total) if security else "—")
        self._flatpak_count = len(flatpaks) if flatpaks else 0
        self._flatpak_card._val_label.setText(str(self._flatpak_count))
        if not (dnf_info and dnf_info.last_checked):
            self._last_check_card._val_label.setText("Today")

        self.display_updates(dnf_info)
        dnf_count = len(dnf_info.packages) if dnf_info and dnf_info.packages else 0
        return dnf_count + self._flatpak_count

    def _render_list(self) -> None:
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None and widget not in (self._empty_label, self._more_label):
                widget.deleteLater()

        packages = (self._update_info.packages
                    if self._update_info and self._update_info.packages else [])
        held = set(self.held_back_package_names())
        security = self._package_severity
        if packages:
            summary = f"{len(packages)} system updates"
            security_count = sum(p.name in security for p in packages)
            if security_count:
                summary += f" · {security_count} security"
            if held:
                summary += f" · {len(held)} major (Update without Major skips these)"
            self._list_summary.setText(summary)
        else:
            self._list_summary.setText("")

        if not packages:
            if self._flatpak_count:
                self._empty_label.setText(
                    f"System packages are up to date. {self._flatpak_count} "
                    "Flatpak update(s) available: choose Update Everything.")
            elif self._update_info is not None:
                self._empty_label.setText("Your system is completely up to date!")
            self._list_layout.insertWidget(0, self._empty_label)
            self._empty_label.show()
            self._more_label.hide()
            return
        self._empty_label.hide()

        query = self._filter_input.text().strip().lower()
        show = self._show_combo.currentData()
        shown = [p for p in packages
                 if (not query or query in p.name.lower())
                 and (show != "security" or p.name in security)
                 and (show != "held" or p.name in held)]
        for pkg in shown[:MAX_ROWS]:
            card = PackageCard(pkg, tags=self._row_tags(pkg.name, held),
                               hold_action=self._hold_action(pkg.name))
            card.install_clicked.connect(self.upgrade_package_clicked.emit)
            card.hold_clicked.connect(self._on_hold_clicked)
            card.info_clicked.connect(self.details_requested.emit)
            self._list_layout.insertWidget(self._list_layout.count() - 1, card)

        if len(shown) > MAX_ROWS:
            self._more_label.setText(
                f"Showing {MAX_ROWS} of {len(shown)}. Use the filter to find others.")
        elif not shown:
            self._more_label.setText("No updates match the current filter.")
        else:
            self._more_label.setText("")
        self._more_label.setVisible(bool(self._more_label.text()))
        self._list_layout.insertWidget(self._list_layout.count() - 1, self._more_label)

    def _major_pattern(self, name: str) -> str | None:
        """The pattern that makes ``name`` count as major (None if none)."""
        return next((p for p in self._held_back_patterns
                     if is_held_back(name, [p])), None)

    def _hold_action(self, name: str) -> tuple[str, str, bool]:
        """Per-row Mark Major / Unmark Major button."""
        if name in self._held_back_patterns:
            return ("Unmark Major", "Stop treating this as a major update. "
                    "Update without Major will install it again.", True)
        pattern = self._major_pattern(name)
        if pattern:
            return ("Unmark Major", f"Counts as major because it matches "
                    f"“{pattern}”. Change the patterns under Settings → "
                    "Update without Major.", False)
        return ("Mark Major", "Treat this as a major update: Update without "
                "Major will skip it. Upgrade All still installs it.", True)

    def _on_hold_clicked(self, name: str) -> None:
        self.hold_toggled.emit(name, name not in self._held_back_patterns)

    def _row_tags(self, name: str, held: set[str]) -> list[tuple[str, str, str]]:
        tags = []
        if name in self._package_severity:
            severity = self._package_severity[name]
            label = f"Security · {severity.title()}" if severity else "Security"
            tags.append((label, "badge_security",
                         f"Fixes a {severity or 'security'} advisory. "
                         "Included in Security Only."))
        if name in held:
            pattern = self._major_pattern(name)
            why = ("You marked this as major." if pattern == name
                   else f"Core package (matches “{pattern}”).")
            tags.append(("Major", "badge_muted",
                         f"{why} Update without Major skips it; Upgrade All "
                         "and Update Everything install it."))
        return tags

    def set_loading(self, loading: bool = True):
        """Set loading state."""
        self._check_btn.setEnabled(not loading)
        if loading:
            self._empty_label.setText("Checking for updates...")
            if not (self._update_info and self._update_info.packages):
                self._empty_label.show()

    # ─── Update without Major ───────────────────────────────────

    def set_held_back_patterns(self, patterns: list[str]) -> None:
        self._held_back_patterns = list(patterns)
        if self._update_info is not None:
            self._update_action_states()
            self._render_list()

    @property
    def held_back_patterns(self) -> list[str]:
        return list(self._held_back_patterns)

    def held_back_package_names(self) -> list[str]:
        """Pending updates the 'without Major' upgrade will skip."""
        return self._names_where(True)

    def minor_package_names(self) -> list[str]:
        """Pending updates the 'without Major' upgrade will install."""
        return self._names_where(False)

    def _names_where(self, held: bool) -> list[str]:
        if not self._update_info or not self._update_info.packages:
            return []
        names = []
        for pkg in self._update_info.packages:
            if is_held_back(pkg.name, self._held_back_patterns) == held \
                    and pkg.name not in names:
                names.append(pkg.name)
        return names
