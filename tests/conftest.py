"""Shared test setup: keep MainWindow tests hermetic and crash-free.

Building a MainWindow schedules a real ``dnf check-upgrade --refresh``, a
GitHub release check and a reminder check. Tests must not touch the network,
and a window garbage-collected while one of those QThreads is still running
aborts the whole pytest process ("QThread: Destroyed while thread is still
running"). So: stub those workers, and keep every window alive until its
threads have finished.
"""

import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Never read or write the real user's settings or autostart entries.
_CONFIG_HOME = tempfile.mkdtemp(prefix="dnf-gui-tests-")
os.environ["XDG_CONFIG_HOME"] = _CONFIG_HOME
from PyQt6.QtCore import QSettings  # noqa: E402

QSettings.setPath(QSettings.Format.NativeFormat, QSettings.Scope.UserScope, _CONFIG_HOME)

import pytest
from PyQt6.QtWidgets import QApplication

# One QApplication for the whole session, created before any test module
# builds widgets. Several modules creating/dropping their own makes Python's
# exit-time teardown order nondeterministic and segfaults.
_APP = QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _hermetic_main_window(monkeypatch):
    from PyQt6.QtCore import QThread
    from dnf_gui.core import worker
    from dnf_gui.core.package import UpdateInfo
    from dnf_gui.ui import main_window

    monkeypatch.setattr(
        worker.CombinedUpdateCheckWorker, "run",
        lambda self: self.finished.emit({"dnf": UpdateInfo(), "flatpak": [],
                                         "security": None, "preview": None,
                                         "security_preview": None,
                                         "reboot": False}))
    monkeypatch.setattr(worker.AppUpdateWorker, "run",
                        lambda self: self.finished.emit(None))
    monkeypatch.setattr(worker.ReminderCheckWorker, "run", lambda self: None)

    windows = []
    original_init = main_window.MainWindow.__init__

    def tracking_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        windows.append(self)

    monkeypatch.setattr(main_window.MainWindow, "__init__", tracking_init)
    yield
    for window in windows:
        for thread in window.findChildren(QThread):
            thread.wait(10000)
    windows.clear()
