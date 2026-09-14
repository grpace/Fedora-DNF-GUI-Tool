"""Navigation sidebar — Breeze-style rail with code-drawn icons.

Design notes:
- Every row is ONE QPushButton (icon + label + count badge inside), so the
  update-count pill can never detach from its row.
- Icons are painted in code (see dnf_gui.ui.icons) with the theme's
  foreground color — distro icon themes have fixed colors that clash on
  light/dark surfaces.
- Sleek brand header with package icon emblem and Fedora KDE branding.
"""

from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QMouseEvent, QColor, QPainter, QPixmap

from dnf_gui.ui.icons import paint_icon

_NAV_ITEMS: list[tuple[str, str, str]] = [
    # (label, section, icon kind)
    ("Updates", "PACKAGES", "updates"),
    ("Installed", "PACKAGES", "installed"),
    ("Flatpak", "PACKAGES", "flatpak"),
    ("System Info", "SYSTEM", "sysinfo"),
    ("Quick Tools", "SYSTEM", "tools"),
    ("Repositories", "SYSTEM", "repos"),
    ("History", "SYSTEM", "history"),
    ("Terminal", "SYSTEM", "terminal"),
    ("Settings", "SYSTEM", "settings"),
]

MAX_BADGE_COUNT = 999


class ClickableLabel(QLabel):
    """QLabel that emits clicked signal on mouse press."""

    clicked = pyqtSignal()

    def mousePressEvent(self, event: QMouseEvent):
        super().mousePressEvent(event)
        self.clicked.emit()


class SidebarButton(QPushButton):
    """One unified nav row: icon + label + optional count badge inside."""

    def __init__(self, text: str, icon_kind: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("nav_button")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setCheckable(True)
        self._icon_kind = icon_kind
        self._active = False
        self._hover = False
        self._fg = QColor("#a2abbb")
        self._fg_active = QColor("#3daee9")

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 0, 10, 0)
        row.setSpacing(10)

        self._icon_label = QLabel()
        self._icon_label.setFixedSize(20, 20)
        self._icon_label.setScaledContents(True)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(self._icon_label)

        self._text_label = QLabel(text)
        self._text_label.setObjectName("nav_label")
        row.addWidget(self._text_label, 1)

        self._badge = QLabel("")
        self._badge.setObjectName("nav_badge")
        self._badge.hide()
        row.addWidget(self._badge)

        self._repaint()

    # ── state ──
    def set_active(self, active: bool):
        self._active = active
        self.setChecked(active)
        self.setProperty("active", active)
        self._polish()
        self._repaint()

    def is_active(self) -> bool:
        return self._active

    def enterEvent(self, event):
        super().enterEvent(event)
        self._hover = True
        self.setProperty("hovered", True)
        self._polish()
        self._repaint()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self._hover = False
        self.setProperty("hovered", False)
        self._polish()
        self._repaint()

    def _polish(self):
        try:
            self.style().unpolish(self)
            self.style().polish(self)
        except Exception:
            pass

    def _repaint(self):
        """Recolor the icon pixmap for the current state."""
        color = QColor(self._fg_active if (self._active or self._hover)
                       else self._fg)
        if self._icon_kind:
            self._icon_label.setPixmap(
                paint_icon(self._icon_kind, color, 20))

    def apply_theme_colors(self, fg: str, fg_active: str):
        self._fg = QColor(fg)
        self._fg_active = QColor(fg_active)
        self._repaint()

    # ── compat / badge ──
    def setText(self, text: str):
        self._text_label.setText(text)

    def text(self) -> str:
        return self._text_label.text()

    def set_count(self, count: int):
        if count > 0:
            shown = str(count) if count <= MAX_BADGE_COUNT else f"{MAX_BADGE_COUNT}+"
            self._badge.setText(shown)
            self._badge.show()
        else:
            self._badge.hide()


class Sidebar(QWidget):
    """Navigation sidebar with page buttons and app info."""

    page_changed = pyqtSignal(int)  # page index
    update_clicked = pyqtSignal()  # when version/update area is clicked
    theme_toggle_requested = pyqtSignal()  # footer theme button

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._buttons: list[SidebarButton] = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Brand Header ──
        brand_widget = QWidget()
        brand_layout = QHBoxLayout(brand_widget)
        brand_layout.setContentsMargins(16, 18, 16, 14)
        brand_layout.setSpacing(12)

        # Brand Icon Emblem
        self._logo_label = QLabel()
        self._logo_label.setFixedSize(36, 36)
        self._logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._logo_label.setScaledContents(True)
        self._logo_label.setPixmap(self._render_app_logo(36))
        brand_layout.addWidget(self._logo_label)

        # Title + Subtitle Column
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title_col.setContentsMargins(0, 0, 0, 0)
        title_col.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        title = QLabel("DNF Manager")
        title.setObjectName("sidebar_title")
        title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        title_col.addWidget(title)

        subtitle = QLabel("Fedora KDE")
        subtitle.setObjectName("sidebar_subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignLeft)
        title_col.addWidget(subtitle)

        brand_layout.addLayout(title_col, 1)
        layout.addWidget(brand_widget)

        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        # ── Navigation Items ──
        current_section: str | None = None
        for idx, (label, section, icon_kind) in enumerate(_NAV_ITEMS):
            if section != current_section:
                sec = QLabel(section)
                sec.setObjectName("nav_section")
                layout.addWidget(sec)
                current_section = section
            btn = SidebarButton(label, icon_kind)
            btn.clicked.connect(
                lambda checked=False, i=idx: self._on_button_clicked(i))
            self._buttons.append(btn)
            layout.addWidget(btn)

        layout.addStretch(1)

        # ── Footer ──
        footer = QWidget()
        footer.setObjectName("sidebar_footer")
        footer.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(0, 8, 0, 8)
        footer_layout.setSpacing(4)

        from dnf_gui import __version__
        from dnf_gui.ui.styles.theme import get_saved_theme_mode, resolve_mode
        saved = get_saved_theme_mode()
        current = resolve_mode(saved if saved != "auto" else None)

        self._theme_btn = QPushButton(
            "Light Mode" if current == "dark" else "Dark Mode")
        self._theme_btn.setObjectName("theme_toggle")
        self._theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._theme_btn.setToolTip("Toggle light / dark theme")
        self._theme_btn.clicked.connect(self.theme_toggle_requested.emit)
        footer_layout.addWidget(self._theme_btn)

        self._version_label = ClickableLabel(f"v{__version__} · Greg.Tech")
        self._version_label.setObjectName("sidebar_version")
        self._version_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self._version_label.clicked.connect(self.update_clicked.emit)
        footer_layout.addWidget(self._version_label)
        layout.addWidget(footer)

        if self._buttons:
            self._buttons[0].set_active(True)

        self.apply_theme(current)

    def _render_app_logo(self, size: int = 36) -> QPixmap:
        """Render high-res app icon or fallback."""
        base = Path(__file__).resolve().parent.parent.parent.parent
        svg_path = base / "assets" / "icons" / "app_icon.svg"
        if svg_path.exists():
            try:
                from PyQt6.QtSvg import QSvgRenderer
                renderer = QSvgRenderer(str(svg_path))
                if renderer.isValid():
                    scale = 2
                    pix = QPixmap(size * scale, size * scale)
                    pix.fill(Qt.GlobalColor.transparent)
                    p = QPainter(pix)
                    p.setRenderHint(QPainter.RenderHint.Antialiasing)
                    renderer.render(p)
                    p.end()
                    return pix
            except Exception:
                pass
        from dnf_gui.ui.styles.theme import get_palette
        pal = get_palette()
        return paint_icon("installed", pal["accent"], size)

    def _on_button_clicked(self, index: int):
        """Handle button click — update active state and emit signal."""
        try:
            for i, btn in enumerate(self._buttons):
                btn.set_active(i == index)
            self.page_changed.emit(index)
        except Exception:
            import traceback
            traceback.print_exc()

    def set_update_badge(self, count: int):
        """Update the Updates button with a count badge."""
        if self._buttons:
            self._buttons[0].set_count(count)

    def set_active_page(self, index: int):
        """Programmatically set the active page."""
        for i, btn in enumerate(self._buttons):
            btn.set_active(i == index)

    def set_update_available(self, latest_version: str):
        """Show that an update is available in the version label."""
        self._version_label.setText(
            f"v{latest_version} available · update")
        self._version_label.setToolTip(
            f"Open the GitHub releases page for v{latest_version}")

    def refresh_theme_button(self, mode: str):
        """Update the footer toggle label and vector icon after a theme change."""
        from dnf_gui.ui.icons import make_icon
        from dnf_gui.ui.styles.theme import get_palette
        pal = get_palette(mode)
        target_text = "Light Mode" if mode == "dark" else "Dark Mode"
        icon_kind = "sun" if mode == "dark" else "moon"
        self._theme_btn.setText(target_text)
        self._theme_btn.setIcon(make_icon(icon_kind, pal["btn_neutral_text"], 16))

    def apply_theme(self, mode: str):
        """Apply icon/text colors for a theme mode (called on toggle)."""
        from dnf_gui.ui.styles.theme import get_palette
        pal = get_palette(mode)
        self._logo_label.setPixmap(self._render_app_logo(36))
        for btn in self._buttons:
            btn.apply_theme_colors(pal["text_dim"], pal["accent"])
        self.refresh_theme_button(mode)
