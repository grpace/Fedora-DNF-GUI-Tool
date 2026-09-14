"""Application entry point — initializes and runs the DNF GUI."""

import sys


def _run_headless_check() -> int:
    """Run `dnf-gui --check` — headless reminder used by autostart.

    Returns process exit code: 0 = no updates, 2 = updates pending,
    1 = error. Never opens a window.
    """
    import argparse
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--security-only", action="store_true")
    args, _ = parser.parse_known_args()
    if not args.check:
        return -1  # not a check invocation

    # Headless check needs no QApplication.
    from dnf_gui.core.app_settings import (
        AppSettings, perform_background_check, send_desktop_notification,
    )
    settings = AppSettings()
    if args.security_only:
        settings.security_only = True
    # Respect the configured interval unless forced via env (useful for testing)
    import os
    force = os.environ.get("DNF_GUI_FORCE_CHECK") == "1"
    if not force and not settings.is_check_due() and settings.get_last_check() is not None:
        print("DNF GUI: check not due yet, skipping.")
        return 0
    print("DNF GUI: checking for updates (DNF + Flatpak + security)...")
    result = perform_background_check(settings)
    print(f"DNF updates: {result.dnf_updates}, "
          f"Flatpak: {result.flatpak_updates}, "
          f"security: {result.security_total}")
    if result.should_notify:
        title = ("Security updates pending!"
                 if result.security_urgent else "System updates available")
        send_desktop_notification(title, result.message,
                                  urgent=result.security_urgent)
        print(f"Notify: {result.message}")
        return 2
    print("System is up to date.")
    return 0


def main():
    """Launch the Fedora DNF GUI application."""
    check_code = _run_headless_check()
    if check_code >= 0:
        sys.exit(check_code)

    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QFont

    from dnf_gui import __version__
    from dnf_gui.ui.main_window import MainWindow
    from dnf_gui.ui.styles.theme import get_stylesheet

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
