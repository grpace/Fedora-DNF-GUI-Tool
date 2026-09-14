"""Installed packages page — browse, search, and manage installed software."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QFrame, QComboBox,
)
from PyQt6.QtCore import pyqtSignal, Qt

from dnf_gui.core.package import Package
from dnf_gui.ui.widgets.package_card import PackageCard


class InstalledPage(QWidget):
    """Page for browsing and searching installed packages."""

    remove_clicked = pyqtSignal(str)   # package name
    details_requested = pyqtSignal(str)  # package name
    refresh_clicked = pyqtSignal()
    show_terminal = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._all_packages: list[Package] = []
        self._filtered_packages: list[Package] = []
        self._setup_ui()

    def _setup_ui(self):
        from dnf_gui.ui.widgets.page_header import PageHeader
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Header ──
        layout.addWidget(PageHeader(
            "Installed Packages", "Browse and Manage All System Software"))

        # ── Body ──
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(16, 0, 16, 16)
        body_layout.setSpacing(16)
        layout.addWidget(body, 1)

        # ── Stats ──
        self._count_label = QLabel("Loading...")
        self._count_label.setObjectName("hint")
        body_layout.addWidget(self._count_label)

        # ── Search & Filter Bar ──
        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(12)

        self._search_input = QLineEdit()
        self._search_input.setObjectName("search_input")
        self._search_input.setPlaceholderText("Search Installed Packages...")
        self._search_input.textChanged.connect(self._on_search_changed)
        filter_bar.addWidget(self._search_input, 1)

        self._sort_combo = QComboBox()
        self._sort_combo.addItems(["Name (A-Z)", "Name (Z-A)", "Repository"])
        self._sort_combo.currentIndexChanged.connect(self._apply_filter)
        filter_bar.addWidget(self._sort_combo)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("ghost_button")
        refresh_btn.setProperty("compact", True)
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.clicked.connect(self.refresh_clicked.emit)
        filter_bar.addWidget(refresh_btn)

        body_layout.addLayout(filter_bar)

        # ── Separator ──
        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        body_layout.addWidget(sep)

        # ── Package List ──
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

    def display_packages(self, packages: list[Package]):
        """Display the list of packages."""
        self._all_packages = packages
        self._count_label.setText(f"{len(packages)} packages installed")
        self._apply_filter()

    def _on_search_changed(self, text: str):
        self._apply_filter()

    def _apply_filter(self):
        query = self._search_input.text().strip().lower()

        if query:
            filtered = [
                p for p in self._all_packages
                if query in p.name.lower() or query in p.summary.lower()
            ]
        else:
            filtered = list(self._all_packages)

        # Sort
        sort_idx = self._sort_combo.currentIndex()
        if sort_idx == 0:
            filtered.sort(key=lambda p: p.name.lower())
        elif sort_idx == 1:
            filtered.sort(key=lambda p: p.name.lower(), reverse=True)
        elif sort_idx == 2:
            filtered.sort(key=lambda p: (p.repo, p.name.lower()))

        self._filtered_packages = filtered
        self._render_page(filtered[:100])

        if query:
            self._count_label.setText(
                f"Showing {len(filtered)} of {len(self._all_packages)} packages"
            )
        else:
            self._count_label.setText(f"{len(self._all_packages)} packages installed")

    def _render_page(self, packages: list[Package]):
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for pkg in packages:
            card = PackageCard(pkg)
            card.remove_clicked.connect(self.remove_clicked.emit)
            card.info_clicked.connect(self.details_requested.emit)
            self._list_layout.insertWidget(self._list_layout.count() - 1, card)

    def set_loading(self, loading: bool = True):
        if loading:
            self._count_label.setText("Loading installed packages...")

    def focus_search(self):
        """Focus and select all in search input for keyboard shortcut."""
        self._search_input.setFocus()
        self._search_input.selectAll()
