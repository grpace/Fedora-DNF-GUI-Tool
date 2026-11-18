"""Shared test setup: keep AppController tests hermetic and crash-free.

Building an AppController schedules a real ``dnf check-upgrade --refresh``, a
GitHub release check and a reminder check, and it can send desktop
notifications. Tests must not touch the network,
and a window garbage-collected while one of those QThreads is still running
aborts the whole pytest process ("QThread: Destroyed while thread is still
running"). So: stub those workers, and keep every window alive until its
threads have finished.

Nothing reads this machine either: the pages' workers report sample data,
``sudo -n -l`` and ``flatpak --version`` are never run, and dnf5, sudo,
flatpak and rpm are "installed" in /usr/bin whatever this system has. Every
test gets its own empty settings (QSettings and ``XDG_CONFIG_HOME`` point
into its ``tmp_path``), so nothing leaks between tests.

Helpers:

* ``app``: a fresh :class:`AppController` (fixture).
* ``ui``: the real Kirigami window loaded offscreen (fixture), yielding
  ``(controller, window, problems)``; ``problems()`` lists every QML
  warning or error so far.
* ``answer(controller, *choices)`` scripts the answers to the controller's
  prompts (confirmations are async in the QML UI; tests answer at once).
* ``wait_until(predicate, timeout)`` pumps the event loop until
  ``predicate()`` is true.
"""

import os
import tempfile
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# The QML tests load the real UI: same style the app sets, and the
# software renderer so no GPU is needed.
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "org.kde.desktop")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

# Never read or write the real user's settings or autostart entries (each
# test then moves these into its own tmp_path).
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

from dnf_gui.core import worker as _worker  # noqa: E402

# The real scan, which the autouse fixture stubs: tests that exercise it
# call this with the worker as ``self``.
REAL_COMBINED_CHECK_RUN = _worker.CombinedUpdateCheckWorker.run

from dnf_gui.core import paths as _paths  # noqa: E402

REAL_FIND_SYSTEM_BINARY = _paths.find_system_binary
# The programs every test sees as installed, whatever this machine has.
FAKE_BINARIES = ("dnf5", "sudo", "flatpak", "rpm")


def fake_find_system_binary(*names):
    if names and names[0] == "visudo":  # only the rule validation test runs it
        return REAL_FIND_SYSTEM_BINARY(*names)
    for name in names:
        if name in FAKE_BINARIES:
            return f"/usr/bin/{name}"
    return None


def _sample_page_data() -> dict:
    """What the pages' workers report in tests (name → a function giving
    the value): a little of everything, so list delegates get exercised."""
    from dnf_gui.core.discover_manager import DiscoverStatus
    from dnf_gui.core.flatpak_backend import FlatpakApp
    from dnf_gui.core.package import Package, PackageStatus
    from dnf_gui.core.system_info import SystemInfo

    def installed():
        return [Package("bash", "5.3.3", "1.fc45", "x86_64", "fedora", "The GNU Bourne Again shell",
                        status=PackageStatus.INSTALLED),
                Package("firefox", "145.0", "1.fc45", "x86_64", "updates", "Mozilla Firefox",
                        status=PackageStatus.INSTALLED)]
    return {
        "PackageListWorker": installed,
        "PackageInfoWorker": lambda: installed()[1],
        "FlatpakListWorker": lambda: [FlatpakApp("Kdenlive", "org.kde.kdenlive", "25.12.0",
                                                 "stable", "flathub", "136 MB")],
        "FlatpakSearchWorker": lambda: [],
        "RepoListWorker": lambda: [{"id": "fedora", "name": "Fedora 45", "enabled": True},
                                   {"id": "updates-testing", "name": "Fedora 45 - Test Updates",
                                    "enabled": False}],
        "HistoryWorker": lambda: [{"id": "214", "command": "upgrade -y --refresh",
                                   "date": "2026-11-16 09:12 PM", "action": "Upgrade",
                                   "altered": "38"}],
        "SystemInfoWorker": lambda: SystemInfo(
            hostname="test-host", fedora_version="Fedora Linux 45", kernel="7.2.6-300.fc45.x86_64",
            cpu_model="Test CPU", cpu_cores=8, ram_total="16.0 GB", ram_used="4.0 GB",
            ram_percent=25.0, disk_total="512 GB", disk_used="128 GB", disk_free="384 GB",
            disk_percent=25.0, package_count=2, flatpak_count=1, desktop="KDE Plasma 6.8.2 (Wayland)"),
        "ToolkitCheckWorker": lambda: {},
        "DiscoverStatusWorker": lambda: DiscoverStatus(discover_installed=True,
                                                       system_autostart_present=True,
                                                       per_user_disabled=True),
    }


SAMPLE_PAGE_DATA = _sample_page_data()


@pytest.fixture(autouse=True)
def _hermetic_controller(monkeypatch, tmp_path):
    from PyQt6.QtCore import QThread
    from dnf_gui.core import worker
    from dnf_gui.core.package import UpdateInfo
    from dnf_gui.ui.controllers import app_controller

    # dnf5, sudo, flatpak and rpm are in /usr/bin; dnf-gui isn't installed.
    from dnf_gui.core import passwordless
    monkeypatch.setattr(_paths, "find_system_binary", fake_find_system_binary)
    monkeypatch.setattr(passwordless, "find_system_binary", fake_find_system_binary)

    # Fresh, empty settings for every test.
    config = tmp_path / "config"
    config.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config))
    QSettings.setPath(QSettings.Format.NativeFormat, QSettings.Scope.UserScope, str(config))

    monkeypatch.setattr(
        worker.CombinedUpdateCheckWorker, "run",
        lambda self: self.finished.emit({"dnf": UpdateInfo(), "flatpak": [],
                                         "security": None, "preview": None,
                                         "security_preview": None,
                                         "reboot": False}))
    monkeypatch.setattr(worker.AppUpdateWorker, "run",
                        lambda self: self.finished.emit(None))
    monkeypatch.setattr(worker.ReminderCheckWorker, "run", lambda self: None)
    # Never run the real `dnf needs-restarting` after a simulated upgrade.
    monkeypatch.setattr(worker.RebootCheckWorker, "run",
                        lambda self: self.finished.emit(False))
    # The pages' lists and facts are samples, never this system's.
    for name, value in SAMPLE_PAGE_DATA.items():
        monkeypatch.setattr(getattr(worker, name), "run",
                            lambda self, value=value: self.finished.emit(value()))
    from dnf_gui.core import flatpak_backend, passwordless as _pw
    monkeypatch.setattr(flatpak_backend.FlatpakBackend, "available", property(lambda self: True))
    monkeypatch.setattr(_pw, "live_status", lambda held_back=(): ("off", False, True))
    # App icons come from the system's AppStream catalogs: one known app.
    monkeypatch.setattr(
        worker.AppIconsWorker, "run",
        lambda self: self.finished.emit({"firefox": {"theme": "org.mozilla.firefox", "file": ""}}))
    # Never show real desktop notifications; tests patch send to inspect them.
    from dnf_gui.core import notifications
    monkeypatch.setattr(notifications.Notifier, "_dbus_notify",
                        lambda self, n, replaces_id=0: 0)
    monkeypatch.setattr(notifications, "_notify_send", lambda n: False)
    monkeypatch.setattr(notifications.Notifier, "close", lambda self, nid: None)
    # Never enable, start or reload the real user's systemd units.
    from dnf_gui.core import app_settings
    monkeypatch.setattr(app_settings, "_systemctl_user", lambda *a: True)
    # Never ask the real sudo which rule is installed: treat the saved scope
    # as the installed one (tests that care patch this).
    monkeypatch.setattr(app_controller.AppController, "_live_passwordless",
                        lambda self: (self.settings.passwordless_scope, True))

    controllers = []
    original_init = app_controller.AppController.__init__

    def tracking_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        controllers.append(self)

    monkeypatch.setattr(app_controller.AppController, "__init__", tracking_init)
    yield
    for controller in controllers:
        controller._reminder_timer.stop()
        for timer in controller._startup_timers:
            timer.stop()
        for thread in controller.findChildren(QThread) + controller.detached_threads:
            thread.wait(10000)
    controllers.clear()
    # Collect now: a controller left for later GC could be destroyed while a
    # later test's event loop has started one of its threads.
    import gc
    gc.collect()


def new_controller(**kwargs):
    """A fresh AppController. Frees controllers left by earlier tests
    first, while none of their threads run: a later processEvents() would
    otherwise fire their pending start-up timers and GC could destroy a
    running QThread."""
    import gc
    gc.collect()
    from dnf_gui.ui.controllers.app_controller import AppController
    return AppController(**kwargs)


@pytest.fixture
def app():
    """A fresh AppController (torn down by the autouse fixture above)."""
    return new_controller()


def answer(controller, *choices):
    """Answer the next prompts with ``choices`` ("yes", "no", "ok", or a
    button id); later prompts get their default. Returns the shown list."""
    queue = list(choices)

    def auto(prompt):
        return queue.pop(0) if queue else prompt.default
    controller.prompts.auto_answer = auto
    return controller.prompts.shown


def wait_until(predicate, timeout: float = 5.0) -> bool:
    """Pump the event loop until ``predicate()`` is true or ``timeout``
    seconds pass. Returns the predicate's last value."""
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.01)
    return predicate()


def make_backend(dnf_path: str = "/usr/bin/dnf5"):
    """A DNFBackend that uses ``dnf_path`` whatever this machine has."""
    from dnf_gui.core.dnf_backend import DNFBackend
    backend = DNFBackend.__new__(DNFBackend)
    backend._dnf_path = dnf_path
    return backend


# ── the real QML UI ──────────────────────────────────────────────────

def spin(ms: int = 60) -> None:
    """Run the event loop for ``ms`` (animations, deferred layout)."""
    from PyQt6.QtCore import QEventLoop, QTimer
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


@pytest.fixture
def ui():
    """Load Main.qml offscreen. Yields (controller, window, problems):
    ``problems()`` is every QML warning or error so far (QML errors from
    Qt.createComponent reach the message handler, not engine.warnings)."""
    from PyQt6.QtCore import QtMsgType, qInstallMessageHandler
    from dnf_gui.ui import window as ui_window

    messages: list[str] = []

    def handler(kind, _context, text):
        if kind != QtMsgType.QtDebugMsg:
            messages.append(text)
    previous = qInstallMessageHandler(handler)
    controller = new_controller()
    warnings: list[str] = []
    engine, window = ui_window.load(controller, warnings)
    window.resize(1280, 800)
    window.show()
    spin(200)
    yield controller, window, lambda: list(dict.fromkeys(warnings + messages))
    controller._shutdown()
    for thread in controller.detached_threads:
        thread.wait(10000)
    ui_window.unload(engine, controller)
    QApplication.processEvents()
    qInstallMessageHandler(previous)


def items(root):
    """``root`` and every visual item under it."""
    stack = [root]
    while stack:
        item = stack.pop()
        yield item
        stack.extend(item.childItems())


def find_items(window, predicate) -> list:
    return [i for i in items(window.contentItem().parentItem() or window.contentItem())
            if predicate(i)]


def by_name(window, name: str):
    """The QML object with ``objectName: name`` (exactly one): a visual
    item, or a non-visual one such as the sidebar drawer."""
    from PyQt6.QtCore import QObject
    found = find_items(window, lambda i: i.objectName() == name)
    if not found:
        found = window.findChildren(QObject, name)
    assert len(found) == 1, (name, len(found))
    return found[0]


def attached(item, name: str):
    """An attached property such as ``Accessible.name``."""
    from PyQt6.QtQml import QQmlEngine, QQmlProperty
    return QQmlProperty(item, name, QQmlEngine.contextForObject(item)).read()


def evaluate(item, expression: str):
    """Evaluate a QML expression in ``item``'s scope."""
    from PyQt6.QtQml import QQmlEngine, QQmlExpression
    context = QQmlEngine.contextForObject(item)
    value, _ = QQmlExpression(context, item, expression).evaluate()
    return value


def call(obj, method: str, *args):
    """Call a QML function on ``obj`` (QVariant arguments and result)."""
    from PyQt6.QtCore import Q_ARG, Q_RETURN_ARG, QMetaObject, Qt
    return QMetaObject.invokeMethod(
        obj, method, Qt.ConnectionType.DirectConnection, Q_RETURN_ARG("QVariant"),
        *[Q_ARG("QVariant", a) for a in args])
