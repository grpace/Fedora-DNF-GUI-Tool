"""Packages page — browse installed RPMs and install new ones from the repos."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QFrame, QComboBox, QTabWidget,
)
from PyQt6.QtCore import pyqtSignal, Qt, QTimer

from dnf_gui.core.package import Package, PackageStatus
from dnf_gui.ui.widgets.package_card import PackageCard

MAX_ROWS = 100


class InstalledPage(QWidget):
    """Installed packages tab plus a repository search tab."""

    remove_clicked = pyqtSignal(str)     # package name
    install_clicked = pyqtSignal(str)    # package name
    details_requested = pyqtSignal(str)  # package name
    refresh_clicked = pyqtSignal()
    search_requested = pyqtSignal(str)   # repository search query

    def __init__(self, parent=None):
        super().__init__(parent)
        self._all_packages: list[Package] = []
        self._filtered_packages: list[Package] = []
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(600)
        self._search_timer.timeout.connect(self._do_search)
        self._setup_ui()

    def _setup_ui(self):
        from dnf_gui.ui.widgets.page_header import PageHeader
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(PageHeader(
            "Packages", "Browse Installed Software and Install from Fedora Repositories"))

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(20, 0, 20, 20)
        body_layout.setSpacing(16)
        layout.addWidget(body, 1)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_installed_tab(), "Installed")
        self._tabs.addTab(self._build_search_tab(), "Search Repositories")
        body_layout.addWidget(self._tabs, 1)

    # ─── Tabs ───────────────────────────────────────────────────

    @staticmethod
    def _list_area() -> tuple[QScrollArea, QVBoxLayout]:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        container = QWidget()
        list_layout = QVBoxLayout(container)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(6)
        list_layout.addStretch()
        scroll.setWidget(container)
        return scroll, list_layout

    @staticmethod
    def _separator() -> QFrame:
        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        return sep

    def _build_installed_tab(self) -> QWidget:
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 12, 0, 0)
        tab_layout.setSpacing(12)

        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(12)
        self._search_input = QLineEdit()
        self._search_input.setObjectName("search_input")
        self._search_input.setPlaceholderText("Filter installed packages...")
        self._search_input.setClearButtonEnabled(True)
        self._search_input.textChanged.connect(self._apply_filter)
        filter_bar.addWidget(self._search_input, 1)

        self._sort_combo = QComboBox()
        self._sort_combo.addItems(["Name (A-Z)", "Name (Z-A)", "Repository"])
        self._sort_combo.currentIndexChanged.connect(self._apply_filter)
        filter_bar.addWidget(self._sort_combo)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("ghost_button")
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.clicked.connect(self.refresh_clicked.emit)
        filter_bar.addWidget(refresh_btn)
        tab_layout.addLayout(filter_bar)

        self._count_label = QLabel("Loading...")
        self._count_label.setObjectName("hint")
        tab_layout.addWidget(self._count_label)
        tab_layout.addWidget(self._separator())

        scroll, self._list_layout = self._list_area()
        tab_layout.addWidget(scroll, 1)
        return tab

    def _build_search_tab(self) -> QWidget:
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 12, 0, 0)
        tab_layout.setSpacing(12)

        search_bar = QHBoxLayout()
        search_bar.setSpacing(12)
        self._repo_search_input = QLineEdit()
        self._repo_search_input.setObjectName("search_input")
        self._repo_search_input.setPlaceholderText(
            "Search Fedora repositories by name or description (e.g. 'htop', 'video editor')...")
        self._repo_search_input.setClearButtonEnabled(True)
        self._repo_search_input.textChanged.connect(
            lambda text: self._search_timer.start() if len(text.strip()) >= 2 else None)
        self._repo_search_input.returnPressed.connect(self._do_search)
        search_bar.addWidget(self._repo_search_input, 1)

        search_btn = QPushButton("Search")
        search_btn.setObjectName("primary_button")
        search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        search_btn.clicked.connect(self._do_search)
        search_bar.addWidget(search_btn)
        tab_layout.addLayout(search_bar)

        self._search_count = QLabel("")
        self._search_count.setObjectName("hint")
        tab_layout.addWidget(self._search_count)
        tab_layout.addWidget(self._separator())

        scroll, self._search_layout = self._list_area()
        self._search_status = QLabel(
            "Search every enabled repository, including RPM Fusion and COPRs you've added.")
        self._search_status.setObjectName("loading_label")
        self._search_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._search_status.setWordWrap(True)
        self._search_layout.insertWidget(0, self._search_status)
        tab_layout.addWidget(scroll, 1)
        return tab

    # ─── Installed ──────────────────────────────────────────────

    def display_packages(self, packages: list[Package]):
        """Display the list of installed packages."""
        self._all_packages = packages
        self._apply_filter()

    def _apply_filter(self):
        query = self._search_input.text().strip().lower()
        if query:
            filtered = [p for p in self._all_packages
                        if query in p.name.lower() or query in p.summary.lower()]
        else:
            filtered = list(self._all_packages)

        sort_idx = self._sort_combo.currentIndex()
        if sort_idx == 0:
            filtered.sort(key=lambda p: p.name.lower())
        elif sort_idx == 1:
            filtered.sort(key=lambda p: p.name.lower(), reverse=True)
        elif sort_idx == 2:
            filtered.sort(key=lambda p: (p.repo, p.name.lower()))
        self._filtered_packages = filtered

        total = len(self._all_packages)
        if query:
            text = f"{len(filtered)} of {total} packages match"
        else:
            text = f"{total} packages installed"
        if len(filtered) > MAX_ROWS:
            text += f" · showing the first {MAX_ROWS}, filter to narrow down"
        self._count_label.setText(text)
        self._render(self._list_layout, filtered[:MAX_ROWS])

    def _render(self, list_layout: QVBoxLayout, packages: list[Package],
                keep: QWidget | None = None):
        while list_layout.count() > 1:
            item = list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None and widget is not keep:
                widget.deleteLater()
        for pkg in packages:
            installed = pkg.status == PackageStatus.INSTALLED
            card = PackageCard(
                pkg, tag="Installed" if installed and list_layout is self._search_layout else "")
            card.remove_clicked.connect(self.remove_clicked.emit)
            card.install_clicked.connect(self.install_clicked.emit)
            card.info_clicked.connect(self.details_requested.emit)
            list_layout.insertWidget(list_layout.count() - 1, card)

    def set_loading(self, loading: bool = True):
        if loading:
            self._count_label.setText("Loading installed packages...")

    # ─── Repository search ──────────────────────────────────────

    def _do_search(self):
        self._search_timer.stop()
        query = self._repo_search_input.text().strip()
        if len(query) >= 2:
            self.search_requested.emit(query)

    def set_search_loading(self):
        self._render(self._search_layout, [], keep=self._search_status)
        self._search_status.setText("Searching repositories...")
        self._search_layout.insertWidget(0, self._search_status)
        self._search_status.show()
        self._search_count.setText("")

    def display_search_results(self, query: str, packages: list[Package]):
        # Ignore results for a query the user has already typed past.
        if query != self._repo_search_input.text().strip():
            return
        self._render(self._search_layout, packages, keep=self._search_status)
        if packages:
            self._search_status.hide()
            installed = sum(p.status == PackageStatus.INSTALLED for p in packages)
            text = f"{len(packages)} results for “{query}”"
            if installed:
                text += f" · {installed} already installed"
            self._search_count.setText(text)
        else:
            self._search_layout.insertWidget(0, self._search_status)
            self._search_status.setText(f"No packages found for “{query}”.")
            self._search_status.show()
            self._search_count.setText("")

    def focus_search(self):
        """Focus the active tab's input (Ctrl+F)."""
        target = (self._search_input if self._tabs.currentIndex() == 0
                  else self._repo_search_input)
        target.setFocus()
        target.selectAll()
