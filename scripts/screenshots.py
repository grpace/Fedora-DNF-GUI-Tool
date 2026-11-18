#!/usr/bin/env python3
"""Render the app's pages offscreen to PNGs (docs, PR screenshots, design QA).

    PYTHONPATH=src python3 scripts/screenshots.py OUT_DIR [--theme light|dark|both]
        [--size 1280x800] [--pages updates,installed,...] [--demo]

``--demo`` fills every page with built-in sample data and stubs all
workers, so nothing touches dnf, Flatpak or the network. Without it the
pages load real data from this system (read-only commands only).

Colors follow the Breeze Light/Dark schemes from a scratch config dir, so
your own Plasma settings are never read or changed.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

SCHEMES = {"light": "BreezeLight", "dark": "BreezeDark"}
ALL_PAGES = ("updates", "updates-details", "running", "installed", "flatpak", "sysinfo",
             "tools", "repos", "history", "settings", "settings-discover", "activity", "prompt")


def _scratch_config(theme: str) -> str:
    scheme = Path(f"/usr/share/color-schemes/{SCHEMES[theme]}.colors")
    config = tempfile.mkdtemp(prefix=f"dnf-gui-shots-{theme}-")
    text = scheme.read_text() if scheme.exists() else ""
    icons = "breeze-dark" if theme == "dark" else "breeze"
    Path(config, "kdeglobals").write_text(
        text + f"\n[General]\nColorScheme={SCHEMES[theme]}\n\n[Icons]\nTheme={icons}\n")
    return config


def _child(args) -> int:
    """Render one theme (runs in its own process: the theme is per process)."""
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "org.kde.desktop")
    from PyQt6.QtCore import QtMsgType, QTimer, qInstallMessageHandler
    from PyQt6.QtWidgets import QApplication

    messages: list[str] = []

    def handler(kind, _context, text):
        if kind != QtMsgType.QtDebugMsg:
            messages.append(text)
    qInstallMessageHandler(handler)

    app = QApplication([sys.argv[0]])
    app.setDesktopFileName("dnf-gui")
    # Never touch the real desktop: no notifications, no systemd units.
    from dnf_gui.core import app_settings, notifications
    app_settings._systemctl_user = lambda *a: True
    notifications.Notifier._dbus_notify = lambda self, n, replaces_id=0: 0
    notifications._notify_send = lambda n: False
    if args.demo:
        import demo_data
        demo_data.stub_workers()
    else:
        # Real, read-only data; no reminder checks or app-update downloads.
        from dnf_gui.core import worker
        worker.ReminderCheckWorker.run = lambda self: None
    from dnf_gui.ui.controllers.app_controller import AppController
    from dnf_gui.ui import window as ui_window

    controller = AppController()
    if args.demo:
        demo_data.fill(controller)
    warnings: list[str] = []
    engine, win = ui_window.load(controller, warnings)
    width, height = (int(v) for v in args.size.split("x"))
    win.resize(width, height)
    win.show()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    pages = [p for p in args.pages.split(",") if p]
    steps = []

    def shoot(name):
        image = win.grabWindow()
        image.save(str(out / f"{name}-{args.theme}.png"))

    for page in pages:
        def go(page=page):
            controller.prompts.cancel_all()
            controller.toggleActivity(False)
            controller.closeActivity()
            base = "updates" if page in ("updates-details", "prompt") else page
            if page == "settings-discover":
                base = "settings"
            if base in ("activity", "running"):
                base = "updates"
            controller.navigate(base)
            if args.demo:
                demo_data.after_navigate(controller, page, win)
        steps.append((go, 900))
        steps.append((lambda page=page: shoot(page), 300))

    def run(i=0):
        if i >= len(steps):
            for w in dict.fromkeys(warnings + messages):
                print("QML:", w, file=sys.stderr)
            controller.shutdown_threads()
            ui_window.unload(engine, controller)
            app.quit()
            return
        fn, delay = steps[i]
        fn()
        QTimer.singleShot(delay, lambda: run(i + 1))

    QTimer.singleShot(1500, run)
    app.exec()
    return 1 if (args.strict and (warnings or messages)) else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("out")
    parser.add_argument("--theme", choices=("light", "dark", "both"), default="both")
    parser.add_argument("--size", default="1280x800")
    parser.add_argument("--pages", default=",".join(ALL_PAGES))
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--strict", action="store_true",
                        help="exit 1 if QML printed any warning")
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    if args.child:
        return _child(args)

    import subprocess
    code = 0
    themes = ("light", "dark") if args.theme == "both" else (args.theme,)
    for theme in themes:
        config = _scratch_config(theme)
        env = dict(os.environ, XDG_CONFIG_HOME=config, QT_QPA_PLATFORM="offscreen",
                   QT_QPA_PLATFORMTHEME="kde", QT_QUICK_BACKEND="software",
                   XDG_RUNTIME_DIR=tempfile.mkdtemp(prefix="dnfgui-"))
        env.pop("LD_LIBRARY_PATH", None)
        cmd = [sys.executable, __file__, args.out, "--theme", theme, "--size", args.size,
               "--pages", args.pages, "--child"]
        cmd += ["--demo"] if args.demo else []
        cmd += ["--strict"] if args.strict else []
        code |= subprocess.run(cmd, env=env).returncode
        shutil.rmtree(config, ignore_errors=True)
    return code


if __name__ == "__main__":
    sys.exit(main())
