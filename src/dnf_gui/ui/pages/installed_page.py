"""Installed packages page — browse and manage installed software."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QScrollArea, QFrame, QComboBox, QPushButton, QSizePolicy
)
from PyQt6.QtCore import pyqtSignal, Qt, QTimer

from dnf_gui.core.package import Package, PackageStatus
from dnf_gui.ui.widgets.package_card import PackageCard


class InstalledPage(QWidget):
    """Page for browsing and managing installed packages."""

    remove_clicked = pyqtSignal(str)
    refresh_clicked = pyqtSignal()
    show_terminal = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._all_packages: list[Package] = []
        self._displayed_packages: list[Package] = []
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self._apply_filter)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 16)
        layout.setSpacing(16)

        # ── Header ──
        header = QLabel("Installed Packages")
        header.setObjectName("page_header")
        layout.addWidget(header)

        subheader = QLabel("Browse and manage all packages on your system")
        subheader.setObjectName("page_subheader")
        layout.addWidget(subheader)

        # ── Stats ──
        self._count_label = QLabel("Loading...")
        self._count_label.setStyleSheet("color: #8b949e; font-size: 13px; padding: 0 0 8px 0;")
        layout.addWidget(self._count_label)

        # ── Search & Filter Bar ──
        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(12)

        self._search_input = QLineEdit()
        self._search_input.setObjectName("search_input")
        self._search_input.setPlaceholderText("Search installed packages...")
        self._search_input.textChanged.connect(self._on_search_changed)
        filter_bar.addWidget(self._search_input, 1)

        self._sort_combo = QComboBox()
        self._sort_combo.addItems(["Name (A-Z)", "Name (Z-A)", "Repository"])
        self._sort_combo.currentIndexChanged.connect(self._apply_filter)
        filter_bar.addWidget(self._sort_combo)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("primary_button")
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.clicked.connect(self.refresh_clicked.emit)
        filter_bar.addWidget(refresh_btn)

        layout.addLayout(filter_bar)

        # ── Separator ──
        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        # ── Package List ──
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(6)
        self._list_layout.addStretch()

        self._scroll.setWidget(self._list_container)
        layout.addWidget(self._scroll, 1)

        # ── Loading / Empty State ──
        self._status_label = QLabel("Loading installed packages...")
        self._status_label.setObjectName("loading_label")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._list_layout.insertWidget(0, self._status_label)

    def _on_search_changed(self, text: str):
        """Debounce search input."""
        self._search_timer.start()

    def _apply_filter(self):
        """Filter and sort the package list based on current inputs."""
        query = self._search_input.text().lower().strip()
        sort_mode = self._sort_combo.currentIndex()

        # Filter
        if query:
            filtered = [p for p in self._all_packages if query in p.name.lower()]
        else:
            filtered = list(self._all_packages)

        # Sort
        if sort_mode == 0:  # Name A-Z
            filtered.sort(key=lambda p: p.name.lower())
        elif sort_mode == 1:  # Name Z-A
            filtered.sort(key=lambda p: p.name.lower(), reverse=True)
        elif sort_mode == 2:  # Repository
            filtered.sort(key=lambda p: (p.repo, p.name.lower()))

        self._displayed_packages = filtered
        self._render_list()

    def _render_list(self):
        """Render the filtered package list."""
        # Clear existing
        while self._list_layout.count() > 2:
            item = self._list_layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()

        # Show up to 200 packages for performance
        display_list = self._displayed_packages[:200]
        
        if not display_list:
            self._status_label.setText("No packages match your search")
            self._status_label.show()
        else:
            self._status_label.hide()
            for pkg in display_list:
                card = PackageCard(pkg)
                card.remove_clicked.connect(self.remove_clicked.emit)
                self._list_layout.insertWidget(self._list_layout.count() - 1, card)

        # Update count
        total = len(self._all_packages)
        shown = len(display_list)
        filtered = len(self._displayed_packages)

        if shown < filtered:
            self._count_label.setText(
                f"Showing {shown} of {filtered} matches ({total} total installed)"
            )
        elif self._search_input.text():
            self._count_label.setText(f"{filtered} matches found ({total} total installed)")
        else:
            self._count_label.setText(f"{total} packages installed")

    def set_loading(self, loading: bool):
        """Show/hide loading state."""
        if loading:
            self._status_label.setText("Loading installed packages...")
            self._status_label.show()

    def display_packages(self, packages: list[Package]):
        """Set the full package list and render."""
        self._all_packages = packages
        self._apply_filter()
