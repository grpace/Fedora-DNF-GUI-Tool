"""Application entry point — initializes and runs the DNF GUI."""

import sys

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from dnf_gui import __version__
from dnf_gui.ui.main_window import MainWindow
from dnf_gui.ui.styles.theme import get_stylesheet


def main():
    """Launch the Fedora DNF GUI application."""
    # Enable high-DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("DNF Package Manager")
    app.setOrganizationName("Greg.Tech")
    app.setOrganizationDomain("greg.tech")
    app.setApplicationVersion(__version__)
    if hasattr(app, "setDesktopFileName"):
        app.setDesktopFileName("dnf-gui.desktop")

    # Set default font
    font = QFont("Inter", 10)
    font.setStyleHint(QFont.StyleHint.SansSerif)
    app.setFont(font)

    # Apply theme
    app.setStyleSheet(get_stylesheet())

    # Create and show main window
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
