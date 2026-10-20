"""Quick Tools page — common post-install tasks and system utilities."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame,
)
from PyQt6.QtCore import pyqtSignal, Qt

from dnf_gui.ui.icons import paint_icon
from dnf_gui.ui.styles.theme import get_palette


class ToolCard(QFrame):
    """Card for a quick-action tool."""

    clicked = pyqtSignal(str)  # tool_id

    def __init__(self, tool_id: str, title: str, description: str,
                 color_key: str, button_text: str = "Run", danger: bool = False,
                 parent=None):
        super().__init__(parent)
        self._tool_id = tool_id
        self._color_key = color_key  # palette key, so icons follow the theme
        self.setObjectName("card")
        self._setup_ui(title, description, button_text, danger)

    def _setup_ui(self, title, description, button_text, danger):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(16)

        # Icon container with vector painted glyph
        icon_label = QLabel()
        icon_label.setFixedSize(36, 36)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setObjectName("tool_icon")
        self._icon_label = icon_label
        self.apply_theme()
        layout.addWidget(icon_label)

        # Text
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        title_label = QLabel(title)
        title_label.setObjectName("tool_title")
        text_layout.addWidget(title_label)

        desc_label = QLabel(description)
        desc_label.setObjectName("tool_desc")
        desc_label.setWordWrap(True)
        text_layout.addWidget(desc_label)

        layout.addLayout(text_layout, 1)

        self._btn = QPushButton(button_text)
        if danger:
            self._btn.setObjectName("danger_button")
        else:
            self._btn.setObjectName("ghost_button")
        self._btn.setFixedWidth(100)
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.clicked.connect(lambda: self.clicked.emit(self._tool_id))
        layout.addWidget(self._btn)

    def apply_theme(self, mode: str | None = None):
        color = get_palette(mode)[self._color_key]
        self._icon_label.setPixmap(paint_icon(self._tool_id, color, 24))

    def set_installed(self, is_installed: bool):
        """Hide tools that are already installed/enabled."""
        if is_installed:
            self.hide()


class ToolkitPage(QWidget):
    """Page with one-click tools for common Fedora tasks."""

    tool_clicked = pyqtSignal(str)  # tool_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards = {}
        self._setup_ui()

    def _setup_ui(self):
        from dnf_gui.ui.widgets.page_header import PageHeader
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Header ──
        layout.addWidget(PageHeader(
            "Quick Tools", "Common Maintenance Tasks and System Utilities"))

        # ── Body ──
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(20, 0, 20, 20)
        body_layout.setSpacing(16)
        layout.addWidget(body, 1)

        # ── Scrollable Content ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        scroll_content = QWidget()
        content = QVBoxLayout(scroll_content)
        content.setContentsMargins(0, 0, 16, 0)
        content.setSpacing(12)

        # ─── Section: Repositories ───
        content.addWidget(self._section_label("Repositories & Sources"))

        self._repos_empty_label = QLabel("All repository tools in this section are currently active.")
        self._repos_empty_label.setObjectName("hint")
        self._repos_empty_label.hide()
        content.addWidget(self._repos_empty_label)

        tools_repos = [
            ("rpmfusion_free", "RPM Fusion (Free)",
             "Enable the RPM Fusion Free repository for open-source packages not shipped by Fedora",
             "green", "Enable"),
            ("rpmfusion_nonfree", "RPM Fusion (Non-Free)",
             "Enable the RPM Fusion Non-Free repository for proprietary drivers and codecs",
             "amber", "Enable"),
            ("add_flathub", "Add Flathub Repository",
             "Add the Flathub remote to Flatpak for access to thousands of applications",
             "violet", "Add"),
        ]

        for args in tools_repos:
            card = ToolCard(*args)
            card.clicked.connect(self.tool_clicked.emit)
            self._cards[args[0]] = card
            content.addWidget(card)

        # ─── Section: System ───
        content.addWidget(self._section_label("System Maintenance"))

        tools_system = [
            ("firmware_check", "Check Firmware Updates",
             "Check for available system firmware and BIOS/UEFI updates using fwupd",
             "accent", "Check"),
            ("firmware_update", "Apply Firmware Updates",
             "Download and install available device firmware updates (may require restart)",
             "amber", "Update"),
            ("clean_cache", "Clean DNF Cache",
             "Remove cached package metadata, packages, and temporary storage files",
             "danger", "Clean"),
            ("rebuild_cache", "Rebuild Metadata Cache",
             "Rebuild DNF repository metadata index for faster and more reliable search",
             "accent", "Rebuild"),
            ("distro_sync", "Distribution Sync",
             "Synchronize all installed packages with the latest distribution repositories",
             "violet", "Sync"),
        ]

        for args in tools_system:
            card = ToolCard(*args, danger=(args[0] == "clean_cache"))
            card.clicked.connect(self.tool_clicked.emit)
            self._cards[args[0]] = card
            content.addWidget(card)

        content.addStretch()
        scroll.setWidget(scroll_content)
        body_layout.addWidget(scroll, 1)

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("section_label")
        return lbl

    def apply_theme(self, mode: str):
        for card in self._cards.values():
            card.apply_theme(mode)

    def _check_section_emptiness(self):
        """Show message if all repository tools are installed."""
        repo_tools = ["rpmfusion_free", "rpmfusion_nonfree", "add_flathub"]
        all_hidden = all(
            tool_id in self._cards and self._cards[tool_id].isHidden()
            for tool_id in repo_tools
        )
        self._repos_empty_label.setVisible(all_hidden)

    def update_card_statuses(self, statuses: dict):
        """Update the UI based on whether tools are installed."""
        for tool_id, is_installed in statuses.items():
            if tool_id in self._cards:
                self._cards[tool_id].set_installed(is_installed)
        self._check_section_emptiness()
