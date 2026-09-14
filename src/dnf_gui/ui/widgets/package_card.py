"""Package card widget — displays a package with status badge and actions."""

from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
)
from PyQt6.QtCore import pyqtSignal, Qt

from dnf_gui.core.package import Package, PackageStatus


class PackageCard(QFrame):
    """Card representing a single package with actions."""

    action_clicked = pyqtSignal(str, str)  # action, package_name
    details_clicked = pyqtSignal(str)      # package_name
    info_clicked = pyqtSignal(str)         # package_name
    install_clicked = pyqtSignal(str)      # package_name
    remove_clicked = pyqtSignal(str)       # package_name

    def __init__(self, package: Package, parent=None):
        super().__init__(parent)
        self._package = package
        self.setObjectName("card")
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(14)

        # ── Package info ──
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)

        name_label = QLabel(self._package.display_name)
        name_label.setObjectName("card_title")
        title_row.addWidget(name_label)

        # Status badge
        badge = QLabel()
        if self._package.status == PackageStatus.UPDATE_AVAILABLE:
            badge.setText("Update Available")
            badge.setObjectName("badge_update")
        elif self._package.status == PackageStatus.INSTALLED:
            badge.setText("Installed")
            badge.setObjectName("badge_installed")
        else:
            badge.setText("Available")
            badge.setObjectName("badge_muted")
        title_row.addWidget(badge)
        title_row.addStretch()

        info_layout.addLayout(title_row)

        # Version & Architecture details
        detail_parts = []
        if self._package.full_version:
            detail_parts.append(self._package.full_version)
        if self._package.arch:
            detail_parts.append(self._package.arch)
        if self._package.repo:
            detail_parts.append(self._package.repo)

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

        # ── Action buttons ──
        action_layout = QHBoxLayout()
        action_layout.setSpacing(8)

        details_btn = QPushButton("Details")
        details_btn.setObjectName("ghost_button")
        details_btn.setProperty("compact", True)
        details_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        details_btn.setToolTip(f"Show details for {self._package.name}")
        details_btn.clicked.connect(
            lambda: self.info_clicked.emit(self._package.name)
        )
        action_layout.addWidget(details_btn)

        if self._package.status == PackageStatus.INSTALLED:
            remove_btn = QPushButton("Remove")
            remove_btn.setObjectName("danger_button")
            remove_btn.setProperty("compact", True)
            remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            remove_btn.clicked.connect(
                lambda: self.remove_clicked.emit(self._package.name)
            )
            action_layout.addWidget(remove_btn)
        elif self._package.status == PackageStatus.AVAILABLE:
            install_btn = QPushButton("Install")
            install_btn.setObjectName("primary_button")
            install_btn.setProperty("compact", True)
            install_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            install_btn.clicked.connect(
                lambda: self.install_clicked.emit(self._package.name)
            )
            action_layout.addWidget(install_btn)
        elif self._package.status == PackageStatus.UPDATE_AVAILABLE:
            update_btn = QPushButton("Update")
            update_btn.setObjectName("primary_button")
            update_btn.setProperty("compact", True)
            update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            update_btn.clicked.connect(
                lambda: self.install_clicked.emit(self._package.name)
            )
            action_layout.addWidget(update_btn)

        layout.addLayout(action_layout)

    @property
    def package(self) -> Package:
        return self._package
