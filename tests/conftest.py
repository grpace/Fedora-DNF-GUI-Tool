"""Shared test setup: keep AppController tests hermetic and crash-free.

Building an AppController schedules a real ``dnf check-upgrade --refresh``, a
GitHub release check and a reminder check, and it can send desktop
notifications. Tests must not touch the network,
and a window garbage-collected while one of those QThreads is still running
aborts the whole pytest process ("QThread: Destroyed while thread is still
running"). So: stub those workers, and keep every window alive until its
threads have finished.

``answer(controller, *choices)`` scripts the answers to the controller's
prompts (confirmations are async in the QML UI; tests answer at once).
"""

import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# The QML smoke tests load the real UI: same style the app sets, and the
# software renderer so no GPU is needed.
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "org.kde.desktop")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

# Never read or write the real user's settings or autostart entries.
_CONFIG_HOME = tempfile.mkdtemp(prefix="dnf-gui-tests-")
os.environ["XDG_CONFIG_HOME"] = _CONFIG_HOME
from PyQt6.QtCore import QSettings  # noqa: E402

QSettings.setPath(QSettings.Format.NativeFormat, QSettings.Scope.UserScope, _CONFIG_HOME)

import pytest  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

# One QApplication for the whole session, created before any test module
# builds widgets. Several modules creating/dropping their own makes Python's
# exit-time teardown order nondeterministic and segfaults.
_APP = QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _hermetic_controller(monkeypatch):
    from PyQt6.QtCore import QThread
    from dnf_gui.core import worker
    from dnf_gui.core.package import UpdateInfo
    from dnf_gui.ui.controllers import app_controller

    monkeypatch.setattr(
        worker.CombinedUpdateCheckWorker, "run",
        lambda self: self.finished.emit({"dnf": UpdateInfo(), "flatpak": [],
                                         "security": None, "preview": None,
                                         "security_preview": None,
                                         "reboot": False}))
    monkeypatch.setattr(worker.AppUpdateWorker, "run",
                        lambda self: self.finished.emit(None))
    monkeypatch.setattr(worker.ReminderCheckWorker, "run", lambda self: None)
    # Never show real desktop notifications; tests patch send to inspect them.
    from dnf_gui.core import notifications
    monkeypatch.setattr(notifications.Notifier, "_dbus_notify",
                        lambda self, n, replaces_id=0: 0)
    monkeypatch.setattr(notifications, "_notify_send", lambda n: False)
    monkeypatch.setattr(notifications.Notifier, "close", lambda self, nid: None)
    # Never enable, start or reload the real user's systemd units.
    from dnf_gui.core import app_settings
    monkeypatch.setattr(app_settings, "_systemctl_user", lambda *a: True)

    controllers = []
    original_init = app_controller.AppController.__init__

    def tracking_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        controllers.append(self)

    monkeypatch.setattr(app_controller.AppController, "__init__", tracking_init)
    yield
    for controller in controllers:
        controller._reminder_timer.stop()
        for thread in controller.findChildren(QThread):
            thread.wait(10000)
    controllers.clear()
    # Collect now: a controller left for later GC could be destroyed while a
    # later test's event loop has started one of its threads.
    import gc
    gc.collect()


def answer(controller, *choices):
    """Answer the next prompts with ``choices`` ("yes", "no", "ok", or a
    button id); later prompts get their default. Returns the shown list."""
    queue = list(choices)

    def auto(prompt):
        return queue.pop(0) if queue else prompt.default
    controller.prompts.auto_answer = auto
    return controller.prompts.shown
