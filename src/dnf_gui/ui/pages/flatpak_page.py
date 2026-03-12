"""Flatpak manager page — browse, install, remove, and update Flatpak apps."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QLineEdit, QTabWidget, QSizePolicy
)
from PyQt6.QtCore import pyqtSignal, Qt, QTimer

from dnf_gui.core.flatpak_backend import FlatpakApp


class FlatpakCard(QFrame):
    """Card displaying a Flatpak application."""

    install_clicked = pyqtSignal(str)   # app_id
    remove_clicked = pyqtSignal(str)    # app_id

    def __init__(self, app: FlatpakApp, installed: bool = True, parent=None):
        super().__init__(parent)
        self._app = app
        self._installed = installed
        self.setObjectName("card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        # Info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        name_row = QHBoxLayout()
        name_row.setSpacing(8)

        name = QLabel(self._app.name or self._app.application_id)
        name.setStyleSheet("font-size: 14px; font-weight: 600; color: #e6edf3;")
        name_row.addWidget(name)

        if self._installed:
            badge = QLabel("Installed")
            badge.setObjectName("badge_installed")
            name_row.addWidget(badge)

        name_row.addStretch()
        info_layout.addLayout(name_row)

        # App ID
        id_label = QLabel(self._app.application_id)
        id_label.setStyleSheet("color: #6e7681; font-size: 11px; font-family: monospace;")
        info_layout.addWidget(id_label)

        # Details
        details = []
        if self._app.version:
            details.append(self._app.version)
        if self._app.branch:
            details.append(self._app.branch)
        if self._app.origin:
            details.append(self._app.origin)
        if self._app.size:
            details.append(self._app.size)

        if details:
            detail_label = QLabel(" · ".join(details))
            detail_label.setStyleSheet("color: #8b949e; font-size: 12px;")
            info_layout.addWidget(detail_label)

        if self._app.description:
            desc = QLabel(self._app.description)
            desc.setStyleSheet("color: #8b949e; font-size: 12px;")
            desc.setWordWrap(True)
            desc.setMaximumWidth(450)
            info_layout.addWidget(desc)

        layout.addLayout(info_layout, 1)

        # Actions
        if self._installed:
            remove_btn = QPushButton("Remove")
            remove_btn.setObjectName("danger_button")
            remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            remove_btn.clicked.connect(
                lambda: self.remove_clicked.emit(self._app.application_id)
            )
            layout.addWidget(remove_btn)
        else:
            install_btn = QPushButton("Install")
            install_btn.setObjectName("success_button")
            install_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            install_btn.clicked.connect(
                lambda: self.install_clicked.emit(self._app.application_id)
            )
            layout.addWidget(install_btn)


class FlatpakPage(QWidget):
    """Page for managing Flatpak applications."""

    install_clicked = pyqtSignal(str)
    remove_clicked = pyqtSignal(str)
    update_all_clicked = pyqtSignal()
    remove_unused_clicked = pyqtSignal()
    repair_clicked = pyqtSignal()
    refresh_clicked = pyqtSignal()
    search_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._all_apps: list[FlatpakApp] = []
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(500)
        self._search_timer.timeout.connect(self._do_search)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 16)
        layout.setSpacing(16)

        # ── Header ──
        header = QLabel("Flatpak Manager")
        header.setObjectName("page_header")
        layout.addWidget(header)

        subheader = QLabel("Install, update, and manage Flatpak applications from Flathub")
        subheader.setObjectName("page_subheader")
        layout.addWidget(subheader)

        # ── Action Bar ──
        action_bar = QHBoxLayout()
        action_bar.setSpacing(12)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("primary_button")
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.clicked.connect(self.refresh_clicked.emit)
        action_bar.addWidget(refresh_btn)

        update_btn = QPushButton("Update All Flatpaks")
        update_btn.setObjectName("primary_button")
        update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        update_btn.setStyleSheet("""
            QPushButton {
                background-color: #3fb950; color: #ffffff; border: none;
                border-radius: 8px; padding: 10px 20px; font-size: 13px;
                font-weight: 600; min-width: 120px;
            }
            QPushButton:hover { background-color: #56d364; }
        """)
        update_btn.clicked.connect(self.update_all_clicked.emit)
        action_bar.addWidget(update_btn)

        cleanup_btn = QPushButton("Remove Unused")
        cleanup_btn.setObjectName("danger_button")
        cleanup_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cleanup_btn.setToolTip("Remove unused Flatpak runtimes and extensions")
        cleanup_btn.clicked.connect(self.remove_unused_clicked.emit)
        action_bar.addWidget(cleanup_btn)

        repair_btn = QPushButton("Repair")
        repair_btn.setObjectName("danger_button")
        repair_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        repair_btn.setToolTip("Repair Flatpak installation")
        repair_btn.clicked.connect(self.repair_clicked.emit)
        action_bar.addWidget(repair_btn)

        action_bar.addStretch()
        layout.addLayout(action_bar)

        # ── Tabs: Installed / Search ──
        self._tabs = QTabWidget()

        # --- Installed Tab ---
        installed_widget = QWidget()
        installed_layout = QVBoxLayout(installed_widget)
        installed_layout.setContentsMargins(0, 12, 0, 0)

        self._installed_count = QLabel("")
        self._installed_count.setStyleSheet("color: #8b949e; font-size: 13px;")
        installed_layout.addWidget(self._installed_count)

        # Filter
        self._filter_input = QLineEdit()
        self._filter_input.setObjectName("search_input")
        self._filter_input.setPlaceholderText("Filter installed Flatpak apps...")
        self._filter_input.textChanged.connect(self._filter_installed)
        installed_layout.addWidget(self._filter_input)

        self._installed_scroll = QScrollArea()
        self._installed_scroll.setWidgetResizable(True)
        self._installed_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._installed_container = QWidget()
        self._installed_layout = QVBoxLayout(self._installed_container)
        self._installed_layout.setContentsMargins(0, 0, 0, 0)
        self._installed_layout.setSpacing(6)
        self._installed_layout.addStretch()

        self._installed_scroll.setWidget(self._installed_container)
        installed_layout.addWidget(self._installed_scroll, 1)

        self._installed_status = QLabel("Click 'Refresh' to load installed Flatpak apps")
        self._installed_status.setObjectName("loading_label")
        self._installed_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._installed_layout.insertWidget(0, self._installed_status)

        self._tabs.addTab(installed_widget, "Installed Apps")

        # --- Search Tab ---
        search_widget = QWidget()
        search_layout = QVBoxLayout(search_widget)
        search_layout.setContentsMargins(0, 12, 0, 0)

        search_bar = QHBoxLayout()
        self._search_input = QLineEdit()
        self._search_input.setObjectName("search_input")
        self._search_input.setPlaceholderText("Search Flathub for apps (e.g., 'Spotify', 'Discord')...")
        self._search_input.textChanged.connect(lambda t: self._search_timer.start() if len(t) >= 2 else None)
        self._search_input.returnPressed.connect(self._do_search)
        search_bar.addWidget(self._search_input, 1)

        search_btn = QPushButton("Search")
        search_btn.setObjectName("primary_button")
        search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        search_btn.clicked.connect(self._do_search)
        search_bar.addWidget(search_btn)
        search_layout.addLayout(search_bar)

        self._search_count = QLabel("")
        self._search_count.setStyleSheet("color: #8b949e; font-size: 13px;")
        search_layout.addWidget(self._search_count)

        self._search_scroll = QScrollArea()
        self._search_scroll.setWidgetResizable(True)
        self._search_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._search_container = QWidget()
        self._search_layout = QVBoxLayout(self._search_container)
        self._search_layout.setContentsMargins(0, 0, 0, 0)
        self._search_layout.setSpacing(6)
        self._search_layout.addStretch()

        self._search_scroll.setWidget(self._search_container)
        search_layout.addWidget(self._search_scroll, 1)

        self._search_status = QLabel("Search Flathub for applications")
        self._search_status.setObjectName("loading_label")
        self._search_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._search_layout.insertWidget(0, self._search_status)

        self._tabs.addTab(search_widget, "Search Flathub")

        layout.addWidget(self._tabs, 1)

    def _do_search(self):
        query = self._search_input.text().strip()
        if len(query) >= 2:
            self.search_requested.emit(query)

    def _filter_installed(self):
        query = self._filter_input.text().lower().strip()
        self._render_installed(query)

    def _render_installed(self, query: str = ""):
        # Clear
        while self._installed_layout.count() > 2:
            item = self._installed_layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()

        filtered = self._all_apps
        if query:
            filtered = [a for a in self._all_apps
                        if query in a.name.lower() or query in a.application_id.lower()]

        if not filtered:
            self._installed_status.setText(
                "No Flatpak apps match your filter" if query else "No Flatpak apps installed"
            )
            self._installed_status.show()
        else:
            self._installed_status.hide()
            for app in filtered:
                card = FlatpakCard(app, installed=True)
                card.remove_clicked.connect(self.remove_clicked.emit)
                self._installed_layout.insertWidget(self._installed_layout.count() - 1, card)

        self._installed_count.setText(
            f"{len(filtered)} apps" + (f" (filtered from {len(self._all_apps)})" if query else "")
        )

    def set_loading(self, loading: bool):
        if loading:
            self._installed_status.setText("Loading Flatpak apps...")
            self._installed_status.show()

    def set_search_loading(self, loading: bool):
        if loading:
            self._search_status.setText("Searching Flathub...")
            self._search_status.show()

    def display_installed(self, apps: list[FlatpakApp]):
        self._all_apps = apps
        self._render_installed()

    def display_search_results(self, apps: list[FlatpakApp]):
        # Clear
        while self._search_layout.count() > 2:
            item = self._search_layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()

        if not apps:
            self._search_status.setText("No Flatpak apps found")
            self._search_status.show()
            self._search_count.setText("0 results")
        else:
            self._search_status.hide()
            self._search_count.setText(f"{len(apps)} results")
            for app in apps[:80]:
                card = FlatpakCard(app, installed=False)
                card.install_clicked.connect(self.install_clicked.emit)
                self._search_layout.insertWidget(self._search_layout.count() - 1, card)

    def set_unavailable(self):
        """Show message when Flatpak is not installed."""
        self._installed_status.setText(
            "Flatpak is not installed on your system.\n\n"
            "Install it with: sudo dnf install flatpak"
        )
        self._installed_status.show()
