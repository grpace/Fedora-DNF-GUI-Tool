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
    check_updates_clicked = pyqtSignal()
    upgrade_package_clicked = pyqtSignal(str)
    autoremove_clicked = pyqtSignal()
    show_terminal = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._update_info = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 16)
        layout.setSpacing(16)

        # ── Header ──
        header = QLabel("System Updates")
        header.setObjectName("page_header")
        layout.addWidget(header)

        subheader = QLabel("Keep your system secure and up to date")
        subheader.setObjectName("page_subheader")
        layout.addWidget(subheader)

        # ── Stats Row ──
        stats_row = QHBoxLayout()
        stats_row.setSpacing(16)

        self._total_card = self._create_stat_card("...", "Available Updates", "#3fb950")
        self._last_check_card = self._create_stat_card("—", "Last Checked", "#58a6ff")

        stats_row.addWidget(self._total_card, 1)
        stats_row.addWidget(self._last_check_card, 1)

        layout.addLayout(stats_row)

        # ── Action Bar ──
        action_bar = QHBoxLayout()
        action_bar.setSpacing(12)

        self._check_btn = QPushButton("Check for Updates")
        self._check_btn.setObjectName("primary_button")
        self._check_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._check_btn.clicked.connect(self.check_updates_clicked.emit)
        action_bar.addWidget(self._check_btn)

        self._upgrade_btn = QPushButton("Upgrade All")
        self._upgrade_btn.setObjectName("primary_button")
        self._upgrade_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._upgrade_btn.setStyleSheet("""
            QPushButton {
                background-color: #3fb950;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: 600;
                min-width: 120px;
            }
            QPushButton:hover { background-color: #56d364; }
            QPushButton:disabled { background-color: #21262d; color: #6e7681; }
        """)
        self._upgrade_btn.setEnabled(False)
        self._upgrade_btn.clicked.connect(self.upgrade_all_clicked.emit)
        action_bar.addWidget(self._upgrade_btn)

        self._autoremove_btn = QPushButton("Clean Up")
        self._autoremove_btn.setObjectName("danger_button")
        self._autoremove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._autoremove_btn.setToolTip("Remove unneeded dependencies (dnf autoremove)")
        self._autoremove_btn.clicked.connect(self.autoremove_clicked.emit)
        action_bar.addWidget(self._autoremove_btn)

        action_bar.addStretch()
        layout.addLayout(action_bar)

        # ── Separator ──
        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

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
        layout.addWidget(self._scroll, 1)

        # ── Empty State ──
        self._empty_label = QLabel("Click 'Check for Updates' to scan for available updates")
        self._empty_label.setObjectName("loading_label")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self._empty_label, 1)
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
                self._list_layout.insertWidget(self._list_layout.count() - 1, card)
