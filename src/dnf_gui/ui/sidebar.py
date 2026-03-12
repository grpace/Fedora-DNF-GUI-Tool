"""Navigation sidebar with animated active state — expanded with all feature pages."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QFrame, QSizePolicy
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QMouseEvent


class ClickableLabel(QLabel):
    """QLabel that emits clicked signal on mouse press."""

    clicked = pyqtSignal()

    def mousePressEvent(self, event: QMouseEvent):
        super().mousePressEvent(event)
        self.clicked.emit()


class SidebarButton(QPushButton):
    """A sidebar navigation button with icon and active state."""

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setObjectName("nav_button")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setCheckable(True)
        self.setProperty("active", False)

    def set_active(self, active: bool):
        """Set the active/selected state."""
        self.setProperty("active", active)
        self.setChecked(active)
        self.style().unpolish(self)
        self.style().polish(self)


class Sidebar(QWidget):
    """Navigation sidebar with page buttons and app info."""

    page_changed = pyqtSignal(int)  # page index
    update_clicked = pyqtSignal()  # when version/update area is clicked

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self._buttons: list[SidebarButton] = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── App Title ──
        title = QLabel("DNF Package\nManager")
        title.setObjectName("sidebar_title")
        layout.addWidget(title)

        # No subtitle

        # ── Separator ──
        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        # ── Navigation — grouped by category ──

        # Package Management section label
        section1 = QLabel("PACKAGE MANAGEMENT")
        section1.setStyleSheet("""
            color: #64748b; font-size: 11px; font-weight: 700;
            letter-spacing: 1px; padding: 16px 16px 8px 16px;
        """)
        layout.addWidget(section1)

        pm_items = [
            ("Updates", "Updates"),
            ("Installed", "Installed"),
            ("Flatpak", "Flatpak"),
        ]

        for _, text in pm_items:
            btn = SidebarButton(text)
            btn.clicked.connect(lambda checked, idx=len(self._buttons): self._on_button_clicked(idx))
            self._buttons.append(btn)
            layout.addWidget(btn)

        # System section label
        section2 = QLabel("SYSTEM")
        section2.setStyleSheet("""
            color: #64748b; font-size: 11px; font-weight: 700;
            letter-spacing: 1px; padding: 16px 16px 8px 16px;
        """)
        layout.addWidget(section2)

        system_items = [
            ("System Info", "System Info"),
            ("Quick Tools", "Quick Tools"),
            ("Repositories", "Repositories"),
            ("History", "History"),
            ("Terminal", "Terminal"),
        ]

        for _, text in system_items:
            btn = SidebarButton(text)
            btn.clicked.connect(lambda checked, idx=len(self._buttons): self._on_button_clicked(idx))
            self._buttons.append(btn)
            layout.addWidget(btn)


        layout.addStretch(1)

        # ── Bottom section ──
        sep2 = QFrame()
        sep2.setObjectName("separator")
        sep2.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep2)

        from dnf_gui import __version__
        self._version_label = ClickableLabel(f"v{__version__} — Greg.Tech")
        self._version_label.setStyleSheet("""
            color: #64748b; font-size: 12px; padding: 16px;
        """)
        self._version_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self._version_label.clicked.connect(self.update_clicked.emit)
        layout.addWidget(self._version_label)

        # Set first button active
        if self._buttons:
            self._buttons[0].set_active(True)

    def _on_button_clicked(self, index: int):
        """Handle button click — update active state and emit signal."""
        try:
            for i, btn in enumerate(self._buttons):
                btn.set_active(i == index)
            self.page_changed.emit(index)
        except Exception as e:
            import traceback
            traceback.print_exc()

    def set_update_badge(self, count: int):
        """Update the Updates button with a count badge."""
        if count > 0:
            self._buttons[0].setText(f"Updates ({count})")
        else:
            self._buttons[0].setText("Updates")

    def set_active_page(self, index: int):
        """Programmatically set the active page."""
        for i, btn in enumerate(self._buttons):
            btn.set_active(i == index)

    def set_update_available(self, latest_version: str):
        """Show that an update is available in the version label."""
        self._version_label.setText(f"New version v{latest_version} available — Click to update")
        self._version_label.setToolTip(f"Open the GitHub releases page for v{latest_version}")
        self._version_label.setStyleSheet("""
            color: #22c55e; font-size: 12px; padding: 16px;
        """)
