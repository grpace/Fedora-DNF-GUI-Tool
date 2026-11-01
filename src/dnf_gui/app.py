"""Application entry point — initializes and runs the DNF GUI."""

import sys


def _run_headless_check() -> int:
    """Run `dnf-gui --check` — headless reminder run by the background timer.

    Returns process exit code: 0 = no updates, 2 = updates pending,
    1 = error. Never opens a window.
    """
    import argparse
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--security-only", action="store_true")
    # Run by the systemd timer: the timer's schedule is the interval, so
    # only skip if the app itself checked recently.
    parser.add_argument("--scheduled", action="store_true")
    args, _ = parser.parse_known_args()
    if not args.check:
        return -1  # not a check invocation

    # Headless check needs no QApplication.
    from dnf_gui.core.app_settings import (
        AppSettings, notification_server_available, perform_background_check,
        send_desktop_notification, wait_for_desktop,
    )
    settings = AppSettings()
    # Respect the configured interval unless forced via env (useful for testing)
    import os
    force = os.environ.get("DNF_GUI_FORCE_CHECK") == "1"
    if not force:
        if not settings.reminders_enabled:
            print("DNF GUI: reminders are off, skipping.")
            return 0
        if not settings.is_check_due(0.5 if args.scheduled else 1.0):
            print("DNF GUI: checked recently, skipping.")
            return 0
        # Right after login or resume, Plasma's notification server or the
        # network may not be up yet. Wait briefly rather than fail.
        ready = (wait_for_desktop() if args.scheduled
                 else notification_server_available())
        if not ready:
            print("DNF GUI: no notification server or network yet; will retry.")
            return 1
    previous_check = settings.get("reminders/last_check", "")
    print("DNF GUI: checking for updates (DNF + Flatpak + security)...")
    result = perform_background_check(
        settings, security_only=True if args.security_only else None)
    if result.check_failed:
        print("DNF GUI: dnf couldn't check for updates (offline?). "
              "Will retry.")
    print(f"DNF updates: {result.dnf_updates}, "
          f"Flatpak: {result.flatpak_updates}, "
          f"security: {result.security_total}")
    if result.should_notify:
        title = ("Security updates pending!"
                 if result.security_urgent else "System updates available")
        if not send_desktop_notification(title, result.message,
                                         urgent=result.security_urgent):
            # Undelivered: keep the check due so the reminder isn't lost.
            settings.set("reminders/last_check", previous_check or "")
            print("DNF GUI: notification could not be delivered; will retry.")
            return 1
        print(f"Notify: {result.message}")
        return 2
    if result.check_failed:
        return 1
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
    from dnf_gui.ui.styles.theme import get_stylesheet, resolve_mode

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

    # Apply theme (follows KDE light/dark unless the user toggled it)
    app.setStyleSheet(get_stylesheet(resolve_mode()))

    # Create and show main window
    window = MainWindow()
    window.show()

    code = app.exec()
    if getattr(window, "_detached_threads", None):
        # A background thread (e.g. a long dnf call) outlived the window.
        # Normal interpreter shutdown would destroy it mid-run and abort,
        # so exit hard; its child processes run in their own sessions.
        import os
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(code)
    sys.exit(code)


if __name__ == "__main__":
    main()
