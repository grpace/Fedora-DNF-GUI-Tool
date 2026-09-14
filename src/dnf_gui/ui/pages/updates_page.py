"""Updates page — check for and apply system updates."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QSizePolicy
)
from PyQt6.QtCore import pyqtSignal, Qt

from dnf_gui.core.package import UpdateInfo, PackageStatus
from dnf_gui.ui.widgets.package_card import PackageCard


class UpdatesPage(QWidget):
    """Page for managing system updates."""

    upgrade_all_clicked = pyqtSignal()
    update_everything_clicked = pyqtSignal()  # DNF + Flatpak in one go
    security_upgrade_clicked = pyqtSignal()  # security-only upgrade
    check_updates_clicked = pyqtSignal()
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

        # ── Header (own left inset, closer to the sidebar) ──
        layout.addWidget(PageHeader(
            "System Updates", "Keep your system secure and up to date"))

        # ── Body ──
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(16, 0, 16, 16)
        body_layout.setSpacing(20)
        layout.addWidget(body, 1)

        # ── Stats Row ──
        stats_row = QHBoxLayout()
        stats_row.setSpacing(16)

        self._total_card = self._create_stat_card("...", "Available Updates", "#3fb950")
        self._security_card = self._create_stat_card("—", "Security", "#f85149")
        self._flatpak_card = self._create_stat_card("—", "Flatpak Updates", "#bc8cff")
        self._last_check_card = self._create_stat_card("—", "Last Checked", "#58a6ff")

        stats_row.addWidget(self._total_card, 1)
        stats_row.addWidget(self._security_card, 1)
        stats_row.addWidget(self._flatpak_card, 1)
        stats_row.addWidget(self._last_check_card, 1)

        body_layout.addLayout(stats_row)

        # ── Action Bar ──
        action_bar = QHBoxLayout()
        action_bar.setSpacing(16)

        self._check_btn = QPushButton("Check for Updates")
        self._check_btn.setObjectName("primary_button")
        self._check_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._check_btn.clicked.connect(self.check_updates_clicked.emit)
        action_bar.addWidget(self._check_btn)

        self._upgrade_btn = QPushButton("Upgrade All")
        self._upgrade_btn.setObjectName("success_button")
        self._upgrade_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._upgrade_btn.setToolTip("Upgrade all system packages (dnf upgrade)")
        self._upgrade_btn.setEnabled(False)
        self._upgrade_btn.clicked.connect(self.upgrade_all_clicked.emit)
        action_bar.addWidget(self._upgrade_btn)

        self._everything_btn = QPushButton("Update Everything")
        self._everything_btn.setObjectName("accent_button")
        self._everything_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._everything_btn.setToolTip(
            "Run DNF system upgrade + Flatpak update back-to-back in one terminal session"
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
        self._autoremove_btn.setObjectName("danger_button")
        self._autoremove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._autoremove_btn.setToolTip("Remove unneeded dependencies (dnf autoremove)")
        self._autoremove_btn.clicked.connect(self.autoremove_clicked.emit)
        action_bar.addWidget(self._autoremove_btn)

        action_bar.addStretch()
        body_layout.addLayout(action_bar)

        # ── Reboot banner (hidden unless a reboot is pending) ──
        self._reboot_banner = QFrame()
        self._reboot_banner.setObjectName("reboot_banner")
        self._reboot_dismissed = False
        banner_layout = QHBoxLayout(self._reboot_banner)
        banner_layout.setContentsMargins(16, 10, 16, 10)
        banner_layout.setSpacing(12)
        banner_label = QLabel(
            "↻  Reboot required — a kernel or core library was updated. "
            "Reboot to finish applying updates.")
        banner_label.setObjectName("reboot_banner_text")
        banner_label.setWordWrap(True)
        banner_layout.addWidget(banner_label, 1)
        self._reboot_btn = QPushButton("Reboot Now")
        self._reboot_btn.setObjectName("warning_button")
        self._reboot_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._reboot_btn.clicked.connect(self.reboot_requested.emit)
        banner_layout.addWidget(self._reboot_btn)
        self._reboot_dismiss = QPushButton("Later")
        self._reboot_dismiss.setObjectName("ghost_button")
        self._reboot_dismiss.setCursor(Qt.CursorShape.PointingHandCursor)
        self._reboot_dismiss.clicked.connect(self._dismiss_reboot_banner)
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
        self._list_layout.setSpacing(12)
        self._list_layout.addStretch()

        self._scroll.setWidget(self._list_container)
        body_layout.addWidget(self._scroll, 1)

        # ── Empty State ──
        self._empty_label = QLabel(
            "Click 'Check for Updates' to scan for available updates\n\n"
            "Tip: visit Settings to make this app your default updater.")
        self._empty_label.setObjectName("loading_label")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        body_layout.addWidget(self._empty_label, 1)
        self._scroll.hide()

    def _create_stat_card(self, value: str, label: str, color: str) -> QFrame:
        """Create a prominent, modern statistics card widget."""
        card = QFrame()
        card.setObjectName("stats_card")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        card.setStyleSheet("""
            QFrame#stats_card {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 12px;
                padding: 16px 20px;
            }
            QFrame#stats_card:hover {
                border-color: #475569;
                background-color: #212e42;
            }
        """)
        
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(8)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        val_label = QLabel(value)
        val_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        val_label.setStyleSheet(f"font-size: 32px; font-weight: 800; color: {color};")
        card_layout.addWidget(val_label)

        desc_label = QLabel(label)
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setStyleSheet("color: #8b949e; font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;")
        card_layout.addWidget(desc_label)

        # Store reference for updates
        card._value_label = val_label
        return card

    def set_loading(self, loading: bool):
        """Show/hide loading state."""
        self._check_btn.setEnabled(not loading)
        self._upgrade_btn.setEnabled(False)
        self._everything_btn.setEnabled(False)
        self._security_btn.setEnabled(False)
        if loading:
            self._empty_label.setText("Checking repositories for system updates...\n(This might take a minute)")
            self._empty_label.setStyleSheet("""
                color: #58a6ff; font-size: 16px; font-weight: 600;
                background-color: #1e293b; border-radius: 12px; border: 1px solid #334155;
            """)
            self._empty_label.show()
            self._scroll.hide()
        else:
            self._empty_label.hide()
            self._scroll.show()

    def display_updates(self, info: UpdateInfo):
        """Display the update check results."""
        self._update_info = info

        # Update stats
        self._total_card._value_label.setText(str(info.total_updates))
        if info.last_checked:
            # last_checked format is "%Y-%m-%d %I:%M %p". Split by space and take the time and AM/PM parts.
            parts = info.last_checked.split(" ")
            time_str = " ".join(parts[1:]) if len(parts) > 1 else info.last_checked
            self._last_check_card._value_label.setText(time_str)

        # Enable/disable upgrade button
        self._upgrade_btn.setEnabled(info.total_updates > 0)
        self._everything_btn.setEnabled(info.total_updates > 0)

        # Clear existing cards safely without removing the stretch
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if info.total_updates == 0:
            self._empty_label.setText("Your system is completely up to date!")
            self._empty_label.setStyleSheet("""
                color: #3fb950; font-size: 20px; font-weight: 700;
                background-color: #1e293b; border-radius: 12px; border: 1px solid #334155;
            """)
            self._empty_label.show()
            self._scroll.hide()
        else:
            self._empty_label.hide()
            self._scroll.show()
            for pkg in info.packages:
                card = PackageCard(pkg)
                card.install_clicked.connect(self.upgrade_package_clicked.emit)
                card.info_clicked.connect(self.details_requested.emit)
                self._list_layout.insertWidget(self._list_layout.count() - 1, card)

    def set_reboot_banner(self, visible: bool) -> None:
        """Show/hide the 'reboot required' banner (honors Later dismissal)."""
        self._reboot_banner.setVisible(bool(visible) and not self._reboot_dismissed)

    def _dismiss_reboot_banner(self) -> None:
        """Hide the banner until the next fresh scan."""
        self._reboot_dismissed = True
        self._reboot_banner.hide()

    def display_combined(self, dnf_info, flatpak_updates, security,
                         preview=None, security_preview=None,
                         reboot: bool = False) -> int:
        """Display DNF + Flatpak + security results. Returns total count."""
        self._reboot_dismissed = False  # fresh scan → banner may show again
        self.display_updates(dnf_info)
        self.upgrade_preview = preview
        self.security_preview = security_preview
        self.set_reboot_banner(bool(reboot))
        flatpak_count = len(flatpak_updates) if flatpak_updates else 0
        self._flatpak_card._value_label.setText(str(flatpak_count))
        if security is not None:
            self._security_card._value_label.setText(str(security.total))
            self._security_btn.setEnabled(security.total > 0)
            if security.urgent:
                self._security_card._value_label.setStyleSheet(
                    "font-size: 32px; font-weight: 800; color: #f85149;"
                )
        total = dnf_info.total_updates + flatpak_count
        self._everything_btn.setEnabled(total > 0)
        if total == 0:
            self._empty_label.setText("Your system is completely up to date!")
        elif flatpak_count and dnf_info.total_updates == 0:
            self._empty_label.setText(
                f"System packages are up to date — {flatpak_count} Flatpak update(s) "
                "available. Use 'Update Everything'."
            )
            self._empty_label.show()
            self._scroll.hide()
        return total
