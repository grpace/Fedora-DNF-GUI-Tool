"""Application entry point — initializes and runs the DNF GUI."""

import os
import sys


DESKTOP_FILE_NAME = "dnf-gui"  # assets/dnf-gui.desktop

# Pages ``--page`` (and notification clicks) can open; sidebar keys.
PAGE_CHOICES = ("updates", "installed", "flatpak", "sysinfo", "tools",
                "repos", "history", "terminal", "settings")


def _parse_args(argv: list[str] | None = None):
    """Our options; anything unknown (e.g. Qt's -platform) is left for Qt."""
    import argparse
    parser = argparse.ArgumentParser(
        prog="dnf-gui",
        description="DNF Package Manager: update and manage Fedora with "
                    "real DNF and Flatpak commands.")
    parser.add_argument("--page", choices=PAGE_CHOICES,
                        help="open this page (or switch the running window to it)")
    check = parser.add_argument_group("background reminder")
    check.add_argument("--check", action="store_true",
                       help="check for updates without opening a window and "
                            "send a reminder if any are waiting")
    check.add_argument("--security-only", action="store_true",
                       help="with --check: only remind about security updates")
    # Run by the systemd timer: the timer's schedule is the interval, so
    # only skip if the app itself checked recently.
    check.add_argument("--scheduled", action="store_true", help=argparse.SUPPRESS)
    check.add_argument("--wait", action="store_true",
                       help="with --check: stay until the reminder is clicked "
                            "or dismissed, so a click can open the Updates page")
    args, _unknown = parser.parse_known_args(
        sys.argv[1:] if argv is None else argv)
    return args


def _run_headless_check(args=None) -> int:
    """Run `dnf-gui --check` — headless reminder run by the background timer.

    Returns process exit code: 0 = no updates, 2 = updates pending,
    1 = error. Never opens a window (a click on the reminder starts the
    app as a separate process).
    """
    args = args or _parse_args()
    if not args.check:
        return -1  # not a check invocation

    # Headless check needs no QApplication.
    from dnf_gui.core.app_settings import (
        AppSettings, notification_server_available, perform_background_check,
        reminder_wait_seconds, wait_for_desktop,
    )
    from dnf_gui.core import notifications
    settings = AppSettings()
    # Respect the configured interval unless forced via env (useful for testing)
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
        notification = notifications.reminder_notification(result)
        if args.wait:
            print("DNF GUI: reminder sent; waiting for it to be clicked "
                  "or dismissed.", flush=True)
            outcome = notifications.notify_and_wait(
                notification,
                reminder_wait_seconds(settings.check_interval_hours))
        else:
            # Nothing would be left to answer a click, so offer none.
            notification.clickable = False
            outcome = notifications.Activation(
                delivered=notifications.send_once(notification))
        if not outcome.delivered:
            # Undelivered: keep the check due so the reminder isn't lost.
            settings.set("reminders/last_check", previous_check or "")
            print("DNF GUI: notification could not be delivered; will retry.")
            return 1
        print(f"Notify: {result.title}: {result.message}")
        if outcome.page is not None:
            print(f"DNF GUI: reminder clicked; opening {outcome.page or 'the app'}.")
            notifications.launch_app(outcome.page, outcome.token)
        return 2
    if result.check_failed:
        return 1
    print("System is up to date.")
    return 0


def _show_load_error(error) -> None:
    """Kirigami (or another QML module) is missing: say which packages."""
    from PyQt6.QtWidgets import QMessageBox
    from dnf_gui.ui.window import REQUIRED_PACKAGES
    QMessageBox.critical(
        None, "DNF Package Manager Can't Start",
        "The app's interface couldn't load. It needs these Fedora packages:\n\n"
        + "\n".join(f"  • {p}" for p in REQUIRED_PACKAGES)
        + "\n\nInstall them with:\n  sudo dnf install " + " ".join(REQUIRED_PACKAGES)
        + f"\n\nDetails: {error}")


def _install_excepthook(controller) -> None:
    """PyQt aborts on an unhandled exception in a slot. QML calls slots
    directly, so log it and tell the user instead."""
    import traceback

    def hook(kind, value, tb):
        traceback.print_exception(kind, value, tb)
        try:
            controller.report_exception(
                f"Something went wrong: {value}. Details were written to the log.")
        except Exception:
            pass
    sys.excepthook = hook


def main():
    """Launch the Fedora DNF GUI application."""
    args = _parse_args()
    check_code = _run_headless_check(args)
    if check_code >= 0:
        sys.exit(check_code)

    # The KDE look for Qt Quick Controls; must be set before Qt loads.
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "org.kde.desktop")

    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt

    from dnf_gui import __version__

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    # QApplication (not QGuiApplication): the desktop style needs widgets.
    app = QApplication(sys.argv)
    app.setApplicationName("DNF Package Manager")
    app.setOrganizationName("Greg.Tech")
    app.setOrganizationDomain("greg.tech")
    app.setApplicationVersion(__version__)
    # The desktop entry's id, without ".desktop" (Qt warns and strips it).
    # Wayland uses it as the app id to match the window to its icon.
    app.setDesktopFileName(DESKTOP_FILE_NAME)
    from PyQt6.QtGui import QIcon
    from dnf_gui.ui.window import APP_ICON
    app.setWindowIcon(QIcon.fromTheme("dnf-gui", QIcon(str(APP_ICON))))

    # One window per user: a second launch (the menu, or a clicked
    # notification) brings the running window to the requested page.
    from dnf_gui.core import single_instance
    request = {"page": args.page or "",
               "token": os.environ.get("XDG_ACTIVATION_TOKEN", "")}
    if single_instance.forward_to_running(request):
        sys.exit(0)

    from dnf_gui.ui import window as ui_window
    from dnf_gui.ui.controllers.app_controller import AppController

    controller = AppController(initial_page=args.page or "")
    _install_excepthook(controller)
    try:
        engine, window = ui_window.load(controller)
    except ui_window.UiLoadError as e:
        print(f"DNF GUI: the interface failed to load:\n{e}", file=sys.stderr)
        _show_load_error(e)
        controller.shutdown_threads()
        sys.exit(1)

    server = single_instance.InstanceServer(app)
    server.request_received.connect(
        lambda req: controller.activate(req.get("page", ""), req.get("token", "")))
    server.listen()
    controller.set_instance_server(server)
    window.show()

    code = app.exec()
    controller.shutdown_threads()
    detached = controller.detached_threads
    ui_window.unload(engine, controller)
    if detached:
        # A background thread (e.g. a long dnf call) outlived the window.
        # Normal interpreter shutdown would destroy it mid-run and abort,
        # so exit hard; its child processes run in their own sessions.
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(code)
    sys.exit(code)


if __name__ == "__main__":
    main()
