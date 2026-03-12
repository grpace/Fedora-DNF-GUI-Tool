"""Reusable package card widget for displaying package information."""

from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QSizePolicy
)
from PyQt6.QtCore import pyqtSignal, Qt

from dnf_gui.core.package import Package, PackageStatus


class PackageCard(QFrame):
    """A card widget that displays package information with action buttons."""

    install_clicked = pyqtSignal(str)    # package name
    remove_clicked = pyqtSignal(str)     # package name
    info_clicked = pyqtSignal(str)       # package name

    def __init__(self, package: Package, parent=None):
        super().__init__(parent)
        self._package = package
        self.setObjectName("card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        # ── Package info ──
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        # Name row
        name_row = QHBoxLayout()
        name_row.setSpacing(8)

        name_label = QLabel(self._package.name)
        name_label.setStyleSheet("""
            font-size: 14px;
            font-weight: 600;
            color: #e6edf3;
        """)
        name_row.addWidget(name_label)

        # Status badge
        if self._package.status == PackageStatus.INSTALLED:
            badge = QLabel("Installed")
            badge.setObjectName("badge_installed")
            name_row.addWidget(badge)
        elif self._package.status == PackageStatus.UPDATE_AVAILABLE:
            badge = QLabel("Update")
            badge.setObjectName("badge_update")
            name_row.addWidget(badge)

        name_row.addStretch()
        info_layout.addLayout(name_row)

        # Version + repo
        detail_parts = []
        if self._package.version:
            detail_parts.append(self._package.full_version)
        if self._package.arch:
            detail_parts.append(self._package.arch)
        if self._package.repo:
            detail_parts.append(self._package.repo)
        
        if detail_parts:
            detail_label = QLabel(" · ".join(detail_parts))
            detail_label.setStyleSheet("color: #8b949e; font-size: 12px;")
            info_layout.addWidget(detail_label)

        # Summary
        if self._package.summary:
            summary_label = QLabel(self._package.summary)
            summary_label.setStyleSheet("color: #8b949e; font-size: 12px;")
            summary_label.setWordWrap(True)
            summary_label.setMaximumWidth(500)
            info_layout.addWidget(summary_label)

        layout.addLayout(info_layout, 1)

        # ── Action buttons ──
        action_layout = QHBoxLayout()
        action_layout.setSpacing(8)

        if self._package.status == PackageStatus.INSTALLED:
            remove_btn = QPushButton("Remove")
            remove_btn.setObjectName("danger_button")
            remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            remove_btn.clicked.connect(
                lambda: self.remove_clicked.emit(self._package.name)
            )
            action_layout.addWidget(remove_btn)
        elif self._package.status == PackageStatus.AVAILABLE:
            install_btn = QPushButton("Install")
            install_btn.setObjectName("success_button")
            install_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            install_btn.clicked.connect(
                lambda: self.install_clicked.emit(self._package.name)
            )
            action_layout.addWidget(install_btn)
        elif self._package.status == PackageStatus.UPDATE_AVAILABLE:
            update_btn = QPushButton("Update")
            update_btn.setObjectName("primary_button")
            update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            update_btn.setStyleSheet("""
                QPushButton {
                    background-color: #d29922;
                    color: #ffffff;
                    border: none;
                    border-radius: 8px;
                    padding: 8px 16px;
                    font-size: 12px;
                    font-weight: 600;
                    min-width: 80px;
                }
                QPushButton:hover {
                    background-color: #e5b94e;
                }
            """)
            update_btn.clicked.connect(
                lambda: self.install_clicked.emit(self._package.name)
            )
            action_layout.addWidget(update_btn)

        layout.addLayout(action_layout)

    @property
    def package(self) -> Package:
        return self._package
