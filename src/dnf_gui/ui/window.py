"""Load the Kirigami UI for an :class:`AppController`."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QUrl
from PyQt6.QtQml import QQmlApplicationEngine

QML_DIR = Path(__file__).resolve().parent / "qml"
MAIN_QML = QML_DIR / "Main.qml"
# The app icon (also installed as the dnf-gui theme icon by the RPM and install.sh).
APP_ICON = Path(__file__).resolve().parent / "app_icon.svg"

# What a missing QML import means on Fedora.
REQUIRED_PACKAGES = ("kf6-kirigami", "kf6-kirigami-addons", "kf6-qqc2-desktop-style",
                     "qt6-qtdeclarative")


class UiLoadError(RuntimeError):
    """The QML couldn't load (usually a missing Kirigami package)."""


def load(controller, warnings: list | None = None) -> tuple[QQmlApplicationEngine, object]:
    """Create the engine and window. Raises :class:`UiLoadError`."""
    from PyQt6 import sip
    from PyQt6.QtQuick import QQuickWindow

    engine = QQmlApplicationEngine()
    collected = warnings if warnings is not None else []
    engine.warnings.connect(lambda ws: collected.extend(w.toString() for w in ws))
    from dnf_gui.ui.i18n import LocalizedContext
    i18n = LocalizedContext(engine)  # parented: lives as long as the engine
    engine.rootContext().setContextObject(i18n)
    engine.rootContext().setContextProperty("App", controller)
    engine.load(QUrl.fromLocalFile(str(MAIN_QML)))
    roots = engine.rootObjects()
    if not roots:
        detail = "\n".join(collected[-5:])
        raise UiLoadError(detail or "Main.qml produced no window")
    window = sip.cast(roots[0], QQuickWindow)
    controller.set_window(window)
    return engine, window


def unload(engine, controller) -> None:
    """Tear down the UI before the controller, so no binding sees a dead App."""
    controller.set_window(None)
    for root in engine.rootObjects():
        root.deleteLater()
    engine.deleteLater()
    from PyQt6.QtCore import QCoreApplication, QEvent
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
