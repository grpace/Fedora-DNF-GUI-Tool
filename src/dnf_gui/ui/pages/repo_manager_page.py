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

        # Status dot (plain colored dot — never a pill, so it can't squish)
        enabled = self._repo.get("enabled", True)
        status = QLabel("●")
        status.setFixedWidth(22)
        status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status.setObjectName("repo_dot_on" if enabled else "repo_dot_off")
        layout.addWidget(status)

        # Info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        repo_id = self._repo.get("id", "unknown")
        id_label = QLabel(repo_id)
        id_label.setObjectName("card_title")
        info_layout.addWidget(id_label)

        name = self._repo.get("name", "")
        if name and name != repo_id:
            name_label = QLabel(name)
            name_label.setObjectName("card_detail")
            name_label.setWordWrap(True)
            info_layout.addWidget(name_label)

        layout.addLayout(info_layout, 1)

        # Badge (fixed width so the column lines up across rows)
        badge = QLabel("Enabled" if enabled else "Disabled")
        badge.setObjectName("badge_ok" if enabled else "badge_muted")
        badge.setMinimumWidth(84)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(badge)

        # Toggle button (fixed width so the badge column never shifts)
        if enabled:
            btn = QPushButton("Disable")
            btn.setObjectName("danger_button")
            btn.setMinimumWidth(88)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda: self.disable_clicked.emit(repo_id))
        else:
            btn = QPushButton("Enable")
            btn.setObjectName("success_button")
            btn.setMinimumWidth(88)
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
        from dnf_gui.ui.widgets.page_header import PageHeader
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Header (own left inset, closer to the sidebar) ──
        layout.addWidget(PageHeader(
            "Repository Manager",
            "Manage DNF package repositories, enable/disable repos, and add COPRs"))

        # ── Body ──
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(20, 0, 20, 20)
        body_layout.setSpacing(20)
        layout.addWidget(body, 1)

        # ── Action Bar ──
        action_bar = QHBoxLayout()
        action_bar.setSpacing(16)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("primary_button")
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.clicked.connect(self.refresh_clicked.emit)
        action_bar.addWidget(refresh_btn)

        add_copr_btn = QPushButton("Add COPR")
        add_copr_btn.setObjectName("accent_button")
        add_copr_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_copr_btn.clicked.connect(self._prompt_add_copr)
        action_bar.addWidget(add_copr_btn)

        action_bar.addStretch()
        body_layout.addLayout(action_bar)

        # ── Filter ──
        self._filter_input = QLineEdit()
        self._filter_input.setObjectName("search_input")
        self._filter_input.setPlaceholderText("Filter repositories...")
        self._filter_input.textChanged.connect(self._filter_repos)
        body_layout.addWidget(self._filter_input)

        self._count_label = QLabel("")
        self._count_label.setObjectName("hint")
        body_layout.addWidget(self._count_label)

        # ── Separator ──
        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        body_layout.addWidget(sep)

        # ── Repo List ──
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

    def focus_search(self) -> None:
        """Focus the filter input (Ctrl+F target)."""
        self._filter_input.setFocus()
        self._filter_input.selectAll()
