"""Updates page — check, view, and apply system and Flatpak updates."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame,
)
from PyQt6.QtCore import pyqtSignal, Qt

from dnf_gui.core.package import UpdateInfo
from dnf_gui.core.security import SecuritySummary
from dnf_gui.core.flatpak_backend import FlatpakApp
from dnf_gui.ui.widgets.package_card import PackageCard


class UpdatesPage(QWidget):
    """Page displaying available system updates."""

    check_updates_clicked = pyqtSignal()
    upgrade_all_clicked = pyqtSignal()
    update_everything_clicked = pyqtSignal()
    security_upgrade_clicked = pyqtSignal()
    upgrade_package_clicked = pyqtSignal(str)
    details_requested = pyqtSignal(str)  # package name
    autoremove_clicked = pyqtSignal()
    reboot_requested = pyqtSignal()
    show_terminal = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._update_info = None
        self.upgrade_preview = None
        self.security_preview = None
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

        stats_row.addWidget(self._total_card, 1)
        stats_row.addWidget(self._security_card, 1)
        stats_row.addWidget(self._flatpak_card, 1)
        stats_row.addWidget(self._last_check_card, 1)

        body_layout.addLayout(stats_row)

        # ── Action Bar ──
        action_bar = QHBoxLayout()
        action_bar.setSpacing(8)

        self._check_btn = QPushButton("Check for Updates")
        self._check_btn.setObjectName("ghost_button")
        self._check_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._check_btn.clicked.connect(self.check_updates_clicked.emit)
        action_bar.addWidget(self._check_btn)

        self._upgrade_btn = QPushButton("Upgrade All")
        self._upgrade_btn.setObjectName("primary_button")
        self._upgrade_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._upgrade_btn.setToolTip("Upgrade all system packages (dnf upgrade)")
        self._upgrade_btn.setEnabled(False)
        self._upgrade_btn.clicked.connect(self.upgrade_all_clicked.emit)
        action_bar.addWidget(self._upgrade_btn)

        self._everything_btn = QPushButton("Update Everything")
        self._everything_btn.setObjectName("ghost_button")
        self._everything_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._everything_btn.setToolTip(
            "Run DNF system upgrade and Flatpak update back-to-back in one terminal session"
        )
        self._everything_btn.setEnabled(False)
        self._everything_btn.clicked.connect(self.update_everything_clicked.emit)
        action_bar.addWidget(self._everything_btn)

        self._security_btn = QPushButton("Security Only")
        self._security_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._security_btn.setToolTip("Install only security advisories (dnf upgrade --security)")
        self._security_btn.setObjectName("ghost_button")
        self._security_btn.setEnabled(False)
        self._security_btn.clicked.connect(self.security_upgrade_clicked.emit)
        action_bar.addWidget(self._security_btn)

        self._autoremove_btn = QPushButton("Clean Up")
        self._autoremove_btn.setObjectName("ghost_button")
        self._autoremove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._autoremove_btn.setToolTip("Remove unneeded dependencies (dnf autoremove)")
        self._autoremove_btn.clicked.connect(self.autoremove_clicked.emit)
        action_bar.addWidget(self._autoremove_btn)

        action_bar.addStretch()
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

        # ── Separator ──
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
        self._list_layout.setSpacing(8)
        self._list_layout.addStretch()

        self._scroll.setWidget(self._list_container)
        body_layout.addWidget(self._scroll, 1)

        # ── Empty State ──
        self._empty_label = QLabel(
            "Click 'Check for Updates' to scan for available updates\n\n"
            "Keyboard shortcuts:\n"
            "Ctrl+R  Refresh / Check updates\n"
            "Ctrl+U  Upgrade all packages\n"
            "Ctrl+F  Search packages\n"
            "Ctrl+T  Open live terminal"
        )
        self._empty_label.setObjectName("loading_label")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._list_layout.insertWidget(0, self._empty_label)

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
        card._value_label = val_label  # backward compat for tests
        card._text_label = lbl
        return card

    def set_reboot_banner(self, visible: bool) -> None:
        """Show/hide the reboot required banner (honors Later dismissal)."""
        self._reboot_banner.setVisible(bool(visible) and not self._reboot_dismissed)

    def _dismiss_reboot_banner(self) -> None:
        """Hide the banner until the next fresh scan."""
        self._reboot_dismissed = True
        self._reboot_banner.hide()

    def reset_reboot_dismissal(self) -> None:
        self._reboot_dismissed = False

    def display_updates(self, info: UpdateInfo):
        """Display available updates."""
        self._update_info = info

        # Clear existing cards
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            if item.widget() and item.widget() != self._empty_label:
                item.widget().deleteLater()

        if info and info.last_checked:
            raw = str(info.last_checked).strip()
            val = raw.split(" ")[0] if (" " in raw and "-" in raw) else raw
            self._last_check_card._val_label.setText(val)

        if not info or not info.packages:
            self._empty_label.setText("Your system is completely up to date!")
            self._empty_label.show()
            self._total_card._val_label.setText("0")
            self._upgrade_btn.setEnabled(False)
            self._everything_btn.setEnabled(False)
            self._security_btn.setEnabled(False)
            return

        self._empty_label.hide()
        self._total_card._val_label.setText(str(len(info.packages)))
        self._upgrade_btn.setEnabled(True)
        self._everything_btn.setEnabled(True)

        for pkg in info.packages:
            card = PackageCard(pkg)
            card.action_clicked.connect(self._on_package_action)
            card.details_clicked.connect(self.details_requested.emit)
            self._list_layout.insertWidget(self._list_layout.count() - 1, card)

    def display_combined(self, dnf_info: UpdateInfo | None,
                         flatpaks: list[FlatpakApp] | None,
                         security: SecuritySummary | None,
                         preview=None, security_preview=None,
                         reboot: bool = False) -> int:
        """Update stat cards from combined scan results. Returns total count."""
        self._reboot_dismissed = False
        self.upgrade_preview = preview
        self.security_preview = security_preview
        self.set_reboot_banner(bool(reboot))

        dnf_count = len(dnf_info.packages) if dnf_info and dnf_info.packages else 0
        self._total_card._val_label.setText(str(dnf_count))

        if security and security.total > 0:
            self._security_card._val_label.setText(str(security.total))
            self._security_btn.setEnabled(True)
        elif security:
            self._security_card._val_label.setText("0")
            self._security_btn.setEnabled(False)
        else:
            self._security_card._val_label.setText("—")
            self._security_btn.setEnabled(False)

        fp_count = len(flatpaks) if flatpaks else 0
        self._flatpak_card._val_label.setText(str(fp_count))

        if dnf_info and dnf_info.last_checked:
            raw = str(dnf_info.last_checked).strip()
            val = raw.split(" ")[0] if (" " in raw and "-" in raw) else raw
            self._last_check_card._val_label.setText(val)
        else:
            self._last_check_card._val_label.setText("Just now")

        total = dnf_count + fp_count
        self._everything_btn.setEnabled(total > 0)

        if dnf_info:
            self.display_updates(dnf_info)

        if total == 0:
            self._empty_label.setText("Your system is completely up to date!")
            self._empty_label.show()
        elif fp_count and dnf_count == 0:
            self._empty_label.setText(
                f"System packages are up to date — {fp_count} Flatpak update(s) "
                "available. Use 'Update Everything'."
            )
            self._empty_label.show()

        return total

    def set_loading(self, loading: bool = True):
        """Set loading state."""
        self._check_btn.setEnabled(not loading)
        if loading:
            self._empty_label.setText("Checking for updates...")
            self._empty_label.show()

    def _on_package_action(self, action: str, package_name: str):
        if action == "upgrade":
            self.upgrade_package_clicked.emit(package_name)
