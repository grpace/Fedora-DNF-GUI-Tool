"""Package details dialog — shows `dnf info` for one package."""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QGridLayout
)
from PyQt6.QtCore import Qt


class PackageDetailsDialog(QDialog):
    """Modal dialog showing metadata for a single package."""

    _FIELDS = (
        ("Version", "full_version"),
        ("Architecture", "arch"),
        ("Repository", "repo"),
        ("Summary", "summary"),
        ("Size", "size"),
        ("Installed size", "installed_size"),
        ("License", "license"),
        ("Homepage", "url"),
    )

    def __init__(self, package_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Details — {package_name}")
        self.setMinimumSize(520, 420)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title = QLabel(package_name)
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: #e6edf3;")
        title.setWordWrap(True)
        layout.addWidget(title)

        self._status = QLabel("Loading package details…")
        self._status.setStyleSheet("color: #8b949e; font-size: 13px;")
        layout.addWidget(self._status)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        self._grid = QGridLayout(body)
        self._grid.setSpacing(8)
        self._grid.setColumnMinimumWidth(0, 130)
        self._grid.setColumnStretch(1, 1)
        scroll.setWidget(body)
        layout.addWidget(scroll, 1)

        self._desc_label = QLabel("")
        self._desc_label.setWordWrap(True)
        self._desc_label.setStyleSheet("color: #8b949e; font-size: 12px;")
        self._desc_label.hide()
        layout.addWidget(self._desc_label)

        buttons = QHBoxLayout()
        buttons.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setObjectName("primary_button")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.accept)
        close_btn.setDefault(True)
        buttons.addWidget(close_btn)
        layout.addLayout(buttons)

        self._value_labels: dict[str, QLabel] = {}

    def display_package(self, pkg) -> None:
        """Fill the dialog from a Package (or show 'not found')."""
        # Clear previous rows
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._value_labels.clear()

        if pkg is None:
            self._status.setText("No information available for this package.")
            return
        self._status.setText(
            "Installed package" if "installed" in str(getattr(pkg, "status", "")).lower()
            else "Available package")

        row = 0
        for label, attr in self._FIELDS:
            if attr == "full_version":
                value = pkg.full_version
            else:
                value = getattr(pkg, attr, "") or ""
            if not value:
                continue
            key = QLabel(label)
            key.setStyleSheet("color: #8b949e; font-size: 13px;")
            val = QLabel(str(value))
            val.setStyleSheet("color: #e6edf3; font-size: 13px;")
            val.setWordWrap(True)
            val.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse)
            self._grid.addWidget(key, row, 0)
            self._grid.addWidget(val, row, 1)
            self._value_labels[attr] = val
            row += 1

        if pkg.description:
            self._desc_label.setText(pkg.description)
            self._desc_label.show()
        else:
            self._desc_label.hide()
