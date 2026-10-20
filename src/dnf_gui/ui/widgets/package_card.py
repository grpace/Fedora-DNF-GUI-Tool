"""Package card widget — one package row with its actions."""

from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
)
from PyQt6.QtCore import pyqtSignal, Qt

from dnf_gui.core.package import Package, PackageStatus


class PackageCard(QFrame):
    """Card representing a single package with actions.

    Pages list one kind of package each (installed, or with an update), so
    the card doesn't repeat a status badge on every row. ``tags`` add
    badges for the exceptions worth calling out, as
    ``(text, badge_object_name, tooltip)`` tuples.
    """

    info_clicked = pyqtSignal(str)     # package_name
    install_clicked = pyqtSignal(str)  # package_name (install or update)
    remove_clicked = pyqtSignal(str)   # package_name
    hold_clicked = pyqtSignal(str)     # package_name

    def __init__(self, package: Package, tag: str = "",
                 tags: list[tuple[str, str, str]] | None = None,
                 hold_action: tuple[str, str, bool] | None = None, parent=None):
        """``hold_action`` = (button text, tooltip, enabled) for update rows."""
        super().__init__(parent)
        self._package = package
        self._hold_action = hold_action
        self.setObjectName("card")
        self.setToolTip("Double-click for details")
        all_tags = list(tags or [])
        if tag:
            all_tags.append((tag, "badge_muted", ""))
        self._setup_ui(all_tags)

    def _setup_ui(self, tags: list[tuple[str, str, str]]):
        # The card's QSS padding already insets the content.
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 0, 0, 0)
        layout.setSpacing(14)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        name_label = QLabel(self._package.name)
        name_label.setObjectName("card_title")
        name_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        title_row.addWidget(name_label)
        for text, object_name, tooltip in tags:
            badge = QLabel(text)
            badge.setObjectName(object_name)
            badge.setToolTip(tooltip)
            title_row.addWidget(badge)
        title_row.addStretch()
        info_layout.addLayout(title_row)

        version = self._package.full_version
        installed = self._package.installed_version
        if (self._package.status == PackageStatus.UPDATE_AVAILABLE
                and installed and version):
            # Show epochs on both sides or neither ("3:1.0 → 1.1" reads
            # like a downgrade).
            if (":" in installed) != (":" in version):
                installed = installed.split(":", 1)[-1]
                version = version.split(":", 1)[-1]
            version = f"{installed} → {version}"
        detail_parts = [part for part in (
            version, self._package.arch, self._package.repo,
        ) if part]
        if detail_parts:
            detail_label = QLabel(" · ".join(detail_parts))
            detail_label.setObjectName("card_detail")
            info_layout.addWidget(detail_label)

        if self._package.summary:
            summary_label = QLabel(self._package.summary)
            summary_label.setObjectName("card_summary")
            summary_label.setWordWrap(True)
            info_layout.addWidget(summary_label)

        layout.addLayout(info_layout, 1)

        action_layout = QHBoxLayout()
        action_layout.setSpacing(8)

        details_btn = self._button("Details", "ghost_button")
        details_btn.setToolTip(f"Show details for {self._package.name}")
        details_btn.clicked.connect(
            lambda: self.info_clicked.emit(self._package.name))
        action_layout.addWidget(details_btn)

        if self._package.status == PackageStatus.INSTALLED:
            remove_btn = self._button("Remove", "danger_button")
            remove_btn.clicked.connect(
                lambda: self.remove_clicked.emit(self._package.name))
            action_layout.addWidget(remove_btn)
        elif self._package.status == PackageStatus.AVAILABLE:
            install_btn = self._button("Install", "primary_button")
            install_btn.setToolTip(f"Install {self._package.name}")
            install_btn.clicked.connect(
                lambda: self.install_clicked.emit(self._package.name))
            action_layout.addWidget(install_btn)
        elif self._package.status == PackageStatus.UPDATE_AVAILABLE:
            if self._hold_action:
                text, tooltip, enabled = self._hold_action
                hold_btn = self._button(text, "ghost_button")
                # Fixed width (theme) so either label lines up across rows.
                hold_btn.setProperty("major_toggle", True)
                hold_btn.setToolTip(tooltip)
                hold_btn.setEnabled(enabled)
                hold_btn.clicked.connect(
                    lambda: self.hold_clicked.emit(self._package.name))
                action_layout.addWidget(hold_btn)
            update_btn = self._button("Update", "ghost_button")
            update_btn.setToolTip(f"Update only {self._package.name}")
            update_btn.clicked.connect(
                lambda: self.install_clicked.emit(self._package.name))
            action_layout.addWidget(update_btn)

        layout.addLayout(action_layout)

    @staticmethod
    def _button(text: str, style: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setObjectName(style)
        btn.setProperty("compact", True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        return btn

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.info_clicked.emit(self._package.name)
        super().mouseDoubleClickEvent(event)

    @property
    def package(self) -> Package:
        return self._package
