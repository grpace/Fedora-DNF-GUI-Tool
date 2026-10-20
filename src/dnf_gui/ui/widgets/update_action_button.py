"""Split button for the Updates page.

The main half runs the user's favorite update mode; the arrow opens a menu
that explains every mode, shows what each would install, and lets the user
star a different one as the favorite.
"""

from dataclasses import dataclass

from PyQt6.QtCore import QPoint, QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMenu, QPushButton, QToolButton,
    QVBoxLayout, QWidget, QWidgetAction,
)

from dnf_gui.core.app_settings import UPDATE_MODE_KEYS
from dnf_gui.ui.icons import make_icon
from dnf_gui.ui.polish import make_translucent
from dnf_gui.ui.styles.theme import get_palette


@dataclass(frozen=True)
class UpdateMode:
    key: str
    title: str
    description: str


UPDATE_MODES = (
    UpdateMode("all", "Upgrade All",
               "Every system package (dnf upgrade)"),
    UpdateMode("everything", "Update Everything",
               "System packages, then all Flatpak apps"),
    UpdateMode("minor", "Update without Major",
               "Skips major updates: kernel, graphics drivers, firmware, bootloader"),
    UpdateMode("security", "Security Only",
               "Only packages with security advisories"),
)
MODES_BY_KEY = {mode.key: mode for mode in UPDATE_MODES}
DEFAULT_MODE = UPDATE_MODE_KEYS[0]


def _repolish(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class _ModeRow(QFrame):
    """One menu row: star, title + description, and what it would install."""

    triggered = pyqtSignal(str)
    starred = pyqtSignal(str)

    def __init__(self, mode: UpdateMode, parent=None):
        super().__init__(parent)
        self._mode = mode
        self._enabled = False
        self.setObjectName("update_menu_row")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 8, 12, 8)
        layout.setSpacing(8)

        self._star = QToolButton()
        self._star.setObjectName("star_button")
        self._star.setIconSize(QSize(18, 18))
        self._star.setCursor(Qt.CursorShape.PointingHandCursor)
        self._star.clicked.connect(lambda: self.starred.emit(self._mode.key))
        layout.addWidget(self._star)

        text = QVBoxLayout()
        text.setSpacing(1)
        self._title = QLabel(mode.title)
        self._title.setObjectName("menu_row_title")
        self._desc = QLabel(mode.description)
        self._desc.setObjectName("menu_row_desc")
        text.addWidget(self._title)
        text.addWidget(self._desc)
        layout.addLayout(text, 1)

        self._count = QLabel()
        self._count.setObjectName("menu_row_count")
        self._count.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._count)

    def set_state(self, enabled: bool, count_text: str, favorite: bool) -> None:
        self._enabled = enabled
        for label in (self._title, self._desc, self._count):
            label.setEnabled(enabled)
        self._count.setText(count_text if enabled else "Nothing to do")
        self.setCursor(Qt.CursorShape.PointingHandCursor if enabled
                       else Qt.CursorShape.ArrowCursor)
        pal = get_palette()
        self._star.setIcon(make_icon(
            "star_filled" if favorite else "star",
            pal["amber"] if favorite else pal["text_faint"], 18))
        self._star.setToolTip(
            "This is your main update button" if favorite
            else "Make this the main update button")

    def enterEvent(self, event):
        self.setProperty("hover", self._enabled)
        _repolish(self)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setProperty("hover", False)
        _repolish(self)
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._enabled and event.button() == Qt.MouseButton.LeftButton:
            self.triggered.emit(self._mode.key)
        super().mouseReleaseEvent(event)


class UpdateActionButton(QWidget):
    """[ Favorite mode | ▾ ] with a menu of every update mode."""

    mode_triggered = pyqtSignal(str)   # mode key
    favorite_changed = pyqtSignal(str)  # mode key

    def __init__(self, parent=None):
        super().__init__(parent)
        self._favorite = DEFAULT_MODE
        self._enabled = {mode.key: False for mode in UPDATE_MODES}
        self._counts = {mode.key: "" for mode in UPDATE_MODES}

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._main = QPushButton()
        self._main.setObjectName("primary_button")
        self._main.setProperty("split", "main")
        self._main.setCursor(Qt.CursorShape.PointingHandCursor)
        self._main.clicked.connect(self.trigger_favorite)
        layout.addWidget(self._main)

        self._arrow = QPushButton()
        self._arrow.setObjectName("primary_button")
        self._arrow.setProperty("split", "arrow")
        self._arrow.setCursor(Qt.CursorShape.PointingHandCursor)
        self._arrow.setToolTip("All update options")
        self._arrow.setIconSize(QSize(16, 16))
        self._arrow.clicked.connect(self._show_menu)
        layout.addWidget(self._arrow)

        self._menu = QMenu(self)
        self._menu.setObjectName("update_menu")
        make_translucent(self._menu)  # rounded corners, not black ones
        self._menu.setMinimumWidth(460)
        self._rows: dict[str, _ModeRow] = {}
        for mode in UPDATE_MODES:
            row = _ModeRow(mode)
            row.triggered.connect(self._on_row_triggered)
            row.starred.connect(self.set_favorite_by_user)
            action = QWidgetAction(self._menu)
            action.setDefaultWidget(row)
            self._menu.addAction(action)
            self._rows[mode.key] = row
        footer = QLabel("The starred option is the main button. Ctrl+U runs it.")
        footer.setObjectName("menu_footer")
        footer_action = QWidgetAction(self._menu)
        footer_action.setDefaultWidget(footer)
        self._menu.addSeparator()
        self._menu.addAction(footer_action)

        self.apply_theme()
        self._refresh()

    # ─── State ──────────────────────────────────────────────────

    @property
    def favorite(self) -> str:
        return self._favorite

    def is_mode_enabled(self, key: str) -> bool:
        return self._enabled.get(key, False)

    def set_mode_state(self, key: str, enabled: bool, count_text: str = "") -> None:
        self._enabled[key] = bool(enabled)
        self._counts[key] = count_text
        self._refresh()

    def set_favorite(self, key: str) -> None:
        self._favorite = key if key in MODES_BY_KEY else DEFAULT_MODE
        self._refresh()

    def set_favorite_by_user(self, key: str) -> None:
        self.set_favorite(key)
        self.favorite_changed.emit(self._favorite)

    def trigger_favorite(self) -> None:
        if self._enabled[self._favorite]:
            self.mode_triggered.emit(self._favorite)

    def apply_theme(self) -> None:
        self._arrow.setIcon(make_icon("chevron_down", get_palette()["on_accent"], 16))
        self._refresh()

    # ─── Internals ──────────────────────────────────────────────

    def _refresh(self) -> None:
        mode = MODES_BY_KEY[self._favorite]
        self._main.setText(mode.title)
        self._main.setToolTip(f"{mode.description}. Use the arrow for other options.")
        self._main.setEnabled(self._enabled[self._favorite])
        for key, row in self._rows.items():
            row.set_state(self._enabled[key], self._counts[key], key == self._favorite)

    def _show_menu(self) -> None:
        self._refresh()
        self._menu.popup(self.mapToGlobal(QPoint(0, self.height() + 6)))

    def _on_row_triggered(self, key: str) -> None:
        self._menu.close()
        self.mode_triggered.emit(key)
