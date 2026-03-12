"""Navigation sidebar with animated active state."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QFrame, QSizePolicy
)
from PyQt6.QtCore import pyqtSignal, Qt


class SidebarButton(QPushButton):
    """A sidebar navigation button with icon and active state."""

    def __init__(self, icon: str, text: str, parent=None):
        super().__init__(f"  {icon}   {text}", parent)
        self.setObjectName("nav_button")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setCheckable(True)
        self.setProperty("active", False)

    def set_active(self, active: bool):
        """Set the active/selected state."""
        self.setProperty("active", active)
        self.setChecked(active)
        # Force style recalculation
        self.style().unpolish(self)
        self.style().polish(self)


class Sidebar(QWidget):
    """Navigation sidebar with page buttons and app info."""

    page_changed = pyqtSignal(int)  # page index

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

        subtitle = QLabel("by Greg.Tech")
        subtitle.setObjectName("sidebar_subtitle")
        layout.addWidget(subtitle)

        # ── Separator ──
        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        # ── Navigation ──
        nav_items = [
            ("🔄", "Updates"),
            ("📦", "Installed"),
            ("🔍", "Find Software"),
            ("💻", "Terminal"),
        ]

        for i, (icon, text) in enumerate(nav_items):
            btn = SidebarButton(icon, text)
            btn.clicked.connect(lambda checked, idx=i: self._on_button_clicked(idx))
            self._buttons.append(btn)
            layout.addWidget(btn)

        layout.addStretch(1)

        # ── Bottom section ──
        sep2 = QFrame()
        sep2.setObjectName("separator")
        sep2.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep2)

        # Version info
        version_label = QLabel("  v1.0.0")
        version_label.setStyleSheet("""
            color: #6e7681;
            font-size: 11px;
            padding: 8px 16px;
        """)
        layout.addWidget(version_label)

        # Website link
        link_label = QLabel('  <a href="https://greg.tech" style="color: #58a6ff; text-decoration: none;">greg.tech</a>')
        link_label.setOpenExternalLinks(True)
        link_label.setStyleSheet("""
            font-size: 11px;
            padding: 0px 16px 16px 16px;
        """)
        layout.addWidget(link_label)

        # Set first button active
        if self._buttons:
            self._buttons[0].set_active(True)

    def _on_button_clicked(self, index: int):
        """Handle button click — update active state and emit signal."""
        for i, btn in enumerate(self._buttons):
            btn.set_active(i == index)
        self.page_changed.emit(index)

    def set_update_badge(self, count: int):
        """Update the Updates button with a count badge."""
        if count > 0:
            self._buttons[0].setText(f"  🔄   Updates ({count})")
        else:
            self._buttons[0].setText("  🔄   Updates")

    def set_active_page(self, index: int):
        """Programmatically set the active page."""
        for i, btn in enumerate(self._buttons):
            btn.set_active(i == index)
