"""Search page — find and install new packages from repositories."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QScrollArea, QFrame, QPushButton
)
from PyQt6.QtCore import pyqtSignal, Qt, QTimer

from src.dnf_gui.core.package import Package
from src.dnf_gui.ui.widgets.package_card import PackageCard


class SearchPage(QWidget):
    """Page for searching and installing new packages."""

    search_requested = pyqtSignal(str)
    install_clicked = pyqtSignal(str)
    show_terminal = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(500)
        self._search_timer.timeout.connect(self._do_search)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 0, 32, 24)
        layout.setSpacing(16)

        # ── Header ──
        header = QLabel("Find Software")
        header.setObjectName("page_header")
        header.setContentsMargins(0, 24, 0, 0)
        layout.addWidget(header)

        subheader = QLabel("Search the Fedora repositories for new packages to install")
        subheader.setObjectName("page_subheader")
        layout.addWidget(subheader)

        # ── Search Bar ──
        search_bar = QHBoxLayout()
        search_bar.setSpacing(12)

        self._search_input = QLineEdit()
        self._search_input.setObjectName("search_input")
        self._search_input.setPlaceholderText("🔍  Search packages (e.g., 'firefox', 'vlc', 'gimp')...")
        self._search_input.textChanged.connect(self._on_search_changed)
        self._search_input.returnPressed.connect(self._do_search)
        search_bar.addWidget(self._search_input, 1)

        search_btn = QPushButton("Search")
        search_btn.setObjectName("primary_button")
        search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        search_btn.clicked.connect(self._do_search)
        search_bar.addWidget(search_btn)

        layout.addLayout(search_bar)

        # ── Result Count ──
        self._result_label = QLabel("")
        self._result_label.setStyleSheet("color: #8b949e; font-size: 13px;")
        layout.addWidget(self._result_label)

        # ── Separator ──
        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        # ── Results List ──
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

        # ── Empty State ──
        self._status_label = QLabel("Start typing to search the Fedora repositories")
        self._status_label.setObjectName("loading_label")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._list_layout.insertWidget(0, self._status_label)

    def _on_search_changed(self, text: str):
        """Debounce search input."""
        if len(text) >= 2:
            self._search_timer.start()
        elif not text:
            self._clear_results()

    def _do_search(self):
        """Execute the search."""
        query = self._search_input.text().strip()
        if len(query) >= 2:
            self.search_requested.emit(query)

    def _clear_results(self):
        """Clear search results."""
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._status_label.setText("Start typing to search the Fedora repositories")
        self._status_label.show()
        self._list_layout.insertWidget(0, self._status_label)
        self._result_label.setText("")

    def set_loading(self, loading: bool):
        """Show loading state."""
        if loading:
            self._status_label.setText("⏳  Searching...")
            self._status_label.show()

    def display_results(self, packages: list[Package]):
        """Display search results."""
        # Clear existing
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not packages:
            self._status_label.setText("No packages found matching your search")
            self._status_label.show()
            self._list_layout.insertWidget(0, self._status_label)
            self._result_label.setText("0 results")
        else:
            self._status_label.hide()
            self._result_label.setText(f"{len(packages)} results found")

            for pkg in packages[:100]:
                card = PackageCard(pkg)
                card.install_clicked.connect(self.install_clicked.emit)
                self._list_layout.insertWidget(self._list_layout.count() - 1, card)

    def focus_search(self):
        """Focus the search input field."""
        self._search_input.setFocus()
        self._search_input.selectAll()
