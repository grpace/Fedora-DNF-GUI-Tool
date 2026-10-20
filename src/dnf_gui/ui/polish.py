"""App-wide visual polish that stylesheets alone can't do.

* **Popups.** The theme sets ``QWidget { background-color: transparent }``.
  A dropdown's popup is its own top-level window, and an opaque window with
  transparent regions paints them black: the dark bars around rounded
  combo popups. Translucent popup windows let the rounded panel float.
* **Scroll fades.** Rows scrolling out of a list are cut by a hard edge.
  A short gradient at the top (once scrolled) and bottom (while more is
  below) lets them fade into the page instead.
"""

from PyQt6 import sip
from PyQt6.QtCore import QEvent, QObject, QRect, Qt
from PyQt6.QtGui import QColor, QLinearGradient, QPainter
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QScrollArea, QStyledItemDelegate, QWidget,
)

FADE_HEIGHT = 18


def make_translucent(window: QWidget) -> None:
    """Must run before the window is first shown (native window creation)."""
    if not window.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground):
        window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        window.setWindowFlag(Qt.WindowType.NoDropShadowWindowHint, True)


def polish_combo(combo: QComboBox) -> None:
    # The default combo delegate ignores QSS ::item rules; a styled
    # delegate lets item padding, hover and selection come from the theme.
    if type(combo.itemDelegate()) is not QStyledItemDelegate:
        combo.setItemDelegate(QStyledItemDelegate(combo))
    container = combo.view().window()
    if container is not combo.window():
        make_translucent(container)


class _ScrollFade(QWidget):
    """Gradient overlay on one edge of a scroll area's viewport."""

    def __init__(self, scroll: QScrollArea, top: bool):
        super().__init__(scroll)  # not the viewport, so it doesn't scroll
        self._scroll = scroll
        self._top = top
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.hide()

    def reposition(self, *_args) -> None:
        if sip.isdeleted(self._scroll):
            return
        viewport = self._scroll.viewport().geometry()
        y = viewport.top() if self._top else viewport.bottom() - FADE_HEIGHT + 1
        self.setGeometry(QRect(viewport.left(), y, viewport.width(), FADE_HEIGHT))
        bar = self._scroll.verticalScrollBar()
        visible = bar.value() > bar.minimum() if self._top else bar.value() < bar.maximum()
        self.setVisible(visible)
        self.raise_()

    def paintEvent(self, event):
        from dnf_gui.ui.styles.theme import get_palette
        solid = QColor(get_palette()["bg_app"])
        clear = QColor(solid)
        clear.setAlpha(0)
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0.0, solid if self._top else clear)
        gradient.setColorAt(1.0, clear if self._top else solid)
        QPainter(self).fillRect(self.rect(), gradient)


def add_scroll_fades(scroll: QScrollArea) -> None:
    if getattr(scroll, "_dnf_gui_fades", None):
        return
    fades = (_ScrollFade(scroll, top=True), _ScrollFade(scroll, top=False))
    scroll._dnf_gui_fades = fades
    bar = scroll.verticalScrollBar()
    for fade in fades:
        # Bound QObject slots: PyQt disconnects them when the fade is
        # destroyed, so a dying scroll area can't call into freed widgets.
        bar.valueChanged.connect(fade.reposition)
        bar.rangeChanged.connect(fade.reposition)
        fade.reposition()


class _UiPolisher(QObject):
    def eventFilter(self, obj, event):
        etype = event.type()
        if etype not in (QEvent.Type.Show, QEvent.Type.Resize):
            return False  # this filter sees every event in the app
        # A combo is always shown before its popup can open, so this runs
        # in time to configure the popup window.
        if etype == QEvent.Type.Show and isinstance(obj, QComboBox):
            polish_combo(obj)
        elif isinstance(obj, QScrollArea):
            if etype == QEvent.Type.Show:
                add_scroll_fades(obj)
            elif etype == QEvent.Type.Resize:
                for fade in getattr(obj, "_dnf_gui_fades", ()):
                    fade.reposition()
        return False


def install_ui_polish(app: QApplication | None = None) -> None:
    app = app or QApplication.instance()
    if app is None or getattr(app, "_dnf_gui_polisher", None):
        return
    polisher = _UiPolisher(app)
    app.installEventFilter(polisher)
    app._dnf_gui_polisher = polisher
