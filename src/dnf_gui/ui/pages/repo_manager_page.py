"""Repository manager page — view, enable, disable repos and add COPRs."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QLineEdit, QInputDialog
)
from PyQt6.QtCore import pyqtSignal, Qt


class RepoCard(QFrame):
    """Card displaying a repository."""

    enable_clicked = pyqtSignal(str)
    disable_clicked = pyqtSignal(str)

    def __init__(self, repo: dict, parent=None):
        super().__init__(parent)
        self._repo = repo
        self.setObjectName("card")
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        # Status indicator  
        enabled = self._repo.get("enabled", True)
        status = QLabel("●")
        status.setFixedWidth(20)
        status.setStyleSheet(f"color: {'#3fb950' if enabled else '#6e7681'}; font-size: 14px;")
        layout.addWidget(status)

        # Info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        repo_id = self._repo.get("id", "unknown")
        id_label = QLabel(repo_id)
        id_label.setStyleSheet("font-size: 14px; font-weight: 600; color: #e6edf3;")
        info_layout.addWidget(id_label)

        name = self._repo.get("name", "")
        if name and name != repo_id:
            name_label = QLabel(name)
            name_label.setStyleSheet("color: #8b949e; font-size: 12px;")
            name_label.setWordWrap(True)
            info_layout.addWidget(name_label)

        layout.addLayout(info_layout, 1)

        # Badge
        badge = QLabel("Enabled" if enabled else "Disabled")
        badge.setStyleSheet(f"""
            background-color: {'#3fb95020' if enabled else '#6e768120'};
            color: {'#3fb950' if enabled else '#6e7681'};
            border: 1px solid {'#3fb95040' if enabled else '#6e768140'};
            border-radius: 10px;
            padding: 4px 10px;
            font-size: 11px;
            font-weight: 600;
        """)
        layout.addWidget(badge)

        # Toggle button
        if enabled:
            btn = QPushButton("Disable")
            btn.setObjectName("danger_button")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda: self.disable_clicked.emit(repo_id))
        else:
            btn = QPushButton("Enable")
            btn.setObjectName("success_button")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda: self.enable_clicked.emit(repo_id))

        layout.addWidget(btn)


class RepoManagerPage(QWidget):
    """Page for managing DNF repositories."""

    refresh_clicked = pyqtSignal()
    enable_repo_clicked = pyqtSignal(str)
    disable_repo_clicked = pyqtSignal(str)
    add_copr_clicked = pyqtSignal(str)
    remove_copr_clicked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._all_repos: list[dict] = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 16)
        layout.setSpacing(16)

        # ── Header ──
        header = QLabel("Repository Manager")
        header.setObjectName("page_header")
        layout.addWidget(header)

        subheader = QLabel("Manage DNF package repositories, enable/disable repos, and add COPRs")
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

        add_copr_btn = QPushButton("Add COPR")
        add_copr_btn.setObjectName("primary_button")
        add_copr_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_copr_btn.setStyleSheet("""
            QPushButton {
                background-color: #bc8cff; color: #ffffff; border: none;
                border-radius: 8px; padding: 10px 20px; font-size: 13px;
                font-weight: 600; min-width: 120px;
            }
            QPushButton:hover { background-color: #d2b3ff; }
        """)
        add_copr_btn.clicked.connect(self._prompt_add_copr)
        action_bar.addWidget(add_copr_btn)

        action_bar.addStretch()
        layout.addLayout(action_bar)

        # ── Filter ──
        self._filter_input = QLineEdit()
        self._filter_input.setObjectName("search_input")
        self._filter_input.setPlaceholderText("Filter repositories...")
        self._filter_input.textChanged.connect(self._filter_repos)
        layout.addWidget(self._filter_input)

        self._count_label = QLabel("")
        self._count_label.setStyleSheet("color: #8b949e; font-size: 13px;")
        layout.addWidget(self._count_label)

        # ── Separator ──
        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        # ── Repo List ──
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

        self._status_label = QLabel("Click 'Refresh' to load repositories")
        self._status_label.setObjectName("loading_label")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._list_layout.insertWidget(0, self._status_label)

    def _prompt_add_copr(self):
        """Open dialog to add a COPR repository."""
        text, ok = QInputDialog.getText(
            self,
            "Add COPR Repository",
            "Enter the COPR repository (e.g., user/project):",
            QLineEdit.EchoMode.Normal,
        )
        if ok and text.strip():
            self.add_copr_clicked.emit(text.strip())

    def _filter_repos(self):
        query = self._filter_input.text().lower().strip()
        self._render_repos(query)

    def _render_repos(self, query: str = ""):
        # Clear
        while self._list_layout.count() > 2:
            item = self._list_layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()

        filtered = self._all_repos
        if query:
            filtered = [r for r in self._all_repos
                        if query in r.get("id", "").lower() or query in r.get("name", "").lower()]

        if not filtered:
            self._status_label.setText("No repositories match your filter" if query else "No repositories found")
            self._status_label.show()
            self._count_label.setText("")
        else:
            self._status_label.hide()
            enabled_count = sum(1 for r in filtered if r.get("enabled", True))
            self._count_label.setText(
                f"{len(filtered)} repositories ({enabled_count} enabled)"
            )
            for repo in filtered:
                card = RepoCard(repo)
                card.enable_clicked.connect(self.enable_repo_clicked.emit)
                card.disable_clicked.connect(self.disable_repo_clicked.emit)
                self._list_layout.insertWidget(self._list_layout.count() - 1, card)

    def set_loading(self, loading: bool):
        if loading:
            self._status_label.setText("Loading repositories...")
            self._status_label.show()

    def display_repos(self, repos: list[dict]):
        self._all_repos = repos
        self._render_repos()
