"""Desktop notifications that open the app where you need it.

Talks to ``org.freedesktop.Notifications`` over QtDBus so a notification
can carry the app's icon and desktop entry (Plasma groups and configures
it under DNF Package Manager), action buttons, and a click handler. When
D-Bus is unusable it falls back to ``notify-send``, which still shows the
message but can't report clicks.

A notification names the app page its click opens (``page``); each action
key is also a page name, so "View Updates" is ``("updates", ...)``.
"""

from __future__ import annotations

import html
import os
import subprocess
from dataclasses import dataclass, field

from PyQt6.QtCore import QMetaType, QObject, pyqtSignal, pyqtSlot

try:
    from PyQt6.QtDBus import (
        QDBusArgument, QDBusConnection, QDBusMessage, QDBusVariant,
    )
except ImportError:  # PyQt6 built without QtDBus: notify-send only
    QDBusConnection = None
    QDBusMessage = object

APP_NAME = "DNF Package Manager"
# The app's own icon file (the one the window uses), so notifications show the
# current icon even before the theme copy is updated or when run from source;
# the theme name is the fallback.
_APP_ICON_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              "ui", "app_icon.svg")
APP_ICON = _APP_ICON_FILE if os.path.isfile(_APP_ICON_FILE) else "dnf-gui"
DESKTOP_ENTRY = "dnf-gui"
DEFAULT_ACTION = "default"  # the spec's key for clicking the notification body
# Returned by Notifier.send when notify-send delivered it: shown, but
# clicks can't be tracked.
UNTRACKED = -1

_SERVICE = "org.freedesktop.Notifications"
_PATH = "/org/freedesktop/Notifications"
_URGENCY = {"low": 0, "normal": 1, "critical": 2}


@dataclass
class Notification:
    title: str
    body: str = ""
    urgency: str = "normal"  # low | normal | critical
    icon: str = APP_ICON
    page: str = ""  # page a click opens; "" just brings the window forward
    actions: list[tuple[str, str]] = field(default_factory=list)  # (page, label)
    timeout_ms: int = -1  # -1 = the server's default
    clickable: bool = True  # False when no process will be left to answer

    def action_list(self) -> list[str]:
        """Flat [key, label, ...] list for the D-Bus Notify call."""
        if not self.clickable:
            return []
        flat = [DEFAULT_ACTION, "Open"]  # body click; servers don't show it as a button
        for key, label in self.actions:
            flat += [key, label]
        return flat


@dataclass
class Activation:
    """What the user did with a notification we waited on."""
    delivered: bool = False
    page: str | None = None  # set when clicked
    token: str = ""  # XDG activation token for focusing the window


class Notifier(QObject):
    """Sends notifications and reports clicks on the ones it sent.

    Needs a QCoreApplication; D-Bus signals arrive through its event loop.
    """

    activated = pyqtSignal(str, str)  # page ("" = just raise), activation token
    closed = pyqtSignal(int)  # notification id

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bus = None
        self._pages: dict[int, str] = {}
        self._tokens: dict[int, str] = {}
        self._capabilities: list[str] | None = None
        if QDBusConnection is None:
            return
        try:
            bus = QDBusConnection.sessionBus()
            if bus.isConnected():
                self._bus = bus
                for signal in ("ActionInvoked", "NotificationClosed",
                               "ActivationToken"):
                    bus.connect(_SERVICE, _PATH, _SERVICE, signal, self._on_signal)
        except Exception:
            self._bus = None

    # ─── Sending ──────────────────────────────────────────────
    def send(self, notification: Notification, replaces_id: int = 0) -> int:
        """Show ``notification``. Returns its id, ``UNTRACKED`` if only
        notify-send could deliver it, or 0 if nothing could."""
        nid = self._dbus_notify(notification, replaces_id)
        if nid > 0:
            self._pages[nid] = notification.page
            return nid
        return UNTRACKED if _notify_send(notification) else 0

    def close(self, nid: int) -> None:
        if nid <= 0 or self._bus is None:
            return
        self._pages.pop(nid, None)
        self._tokens.pop(nid, None)
        try:
            msg = QDBusMessage.createMethodCall(
                _SERVICE, _PATH, _SERVICE, "CloseNotification")
            msg.setArguments([QDBusArgument(nid, QMetaType.Type.UInt.value)])
            self._bus.call(msg, timeout=2000)
        except Exception:
            pass

    def supports_markup(self) -> bool:
        return "body-markup" in self._get_capabilities()

    def _get_capabilities(self) -> list[str]:
        if self._capabilities is None:
            self._capabilities = []
            if self._bus is not None:
                try:
                    msg = QDBusMessage.createMethodCall(
                        _SERVICE, _PATH, _SERVICE, "GetCapabilities")
                    reply = self._bus.call(msg, timeout=2000)
                    if reply.type() == QDBusMessage.MessageType.ReplyMessage:
                        self._capabilities = [str(c) for c in reply.arguments()[0]]
                except Exception:
                    pass
        return self._capabilities

    def _dbus_notify(self, n: Notification, replaces_id: int) -> int:
        if self._bus is None:
            return 0
        try:
            body = (html.escape(n.body, quote=False)
                    if self.supports_markup() else n.body)
            actions = n.action_list() if "actions" in self._get_capabilities() else []
            hints = {
                "desktop-entry": QDBusVariant(DESKTOP_ENTRY),
                "urgency": QDBusVariant(QDBusArgument(
                    _URGENCY.get(n.urgency, 1), QMetaType.Type.UChar.value)),
            }
            msg = QDBusMessage.createMethodCall(_SERVICE, _PATH, _SERVICE, "Notify")
            msg.setArguments([
                APP_NAME,
                QDBusArgument(max(0, replaces_id), QMetaType.Type.UInt.value),
                n.icon, n.title, body,
                QDBusArgument(actions, QMetaType.Type.QStringList.value),
                hints, int(n.timeout_ms),
            ])
            reply = self._bus.call(msg, timeout=5000)
            if reply.type() != QDBusMessage.MessageType.ReplyMessage:
                return 0
            return int(reply.arguments()[0])
        except Exception:
            return 0

    # ─── Signals from the notification server ────────────────
    @pyqtSlot(QDBusMessage)
    def _on_signal(self, msg) -> None:
        try:
            args = msg.arguments()
            nid = int(args[0])
            if nid not in self._pages:
                return  # someone else's notification
            member = msg.member()
            if member == "ActivationToken":
                self._tokens[nid] = str(args[1])
            elif member == "ActionInvoked":
                key = str(args[1])
                page = self._pages.get(nid, "") if key == DEFAULT_ACTION else key
                self.activated.emit(page, self._tokens.pop(nid, ""))
            elif member == "NotificationClosed":
                self._pages.pop(nid, None)
                self._tokens.pop(nid, None)
                self.closed.emit(nid)
        except Exception:
            pass


def notify_send_command(n: Notification) -> list[str]:
    return ["notify-send", f"--app-name={APP_NAME}", f"--icon={n.icon}",
            f"--urgency={n.urgency}", f"--hint=string:desktop-entry:{DESKTOP_ENTRY}",
            "--", n.title, n.body]


def _notify_send(n: Notification) -> bool:
    """Plain fallback when D-Bus can't be reached from Qt."""
    try:
        return subprocess.run(notify_send_command(n), capture_output=True,
                              timeout=5).returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def send_once(notification: Notification) -> bool:
    """Show ``notification`` from a process without a GUI. True if shown."""
    from PyQt6.QtCore import QCoreApplication
    app = QCoreApplication.instance() or QCoreApplication([])  # noqa: F841
    return Notifier().send(notification) != 0


def notify_and_wait(notification: Notification, max_wait_s: float) -> Activation:
    """Show ``notification`` and wait until it's clicked, closed, or
    ``max_wait_s`` passes (then it's withdrawn, since nothing would be
    left to answer a click). Used by the headless reminder.
    """
    import signal
    from PyQt6.QtCore import QCoreApplication, QEventLoop, QTimer

    app = QCoreApplication.instance() or QCoreApplication([])  # noqa: F841
    notifier = Notifier()
    result = Activation()
    nid = notifier.send(notification)
    result.delivered = nid != 0
    if nid <= 0:
        return result  # undelivered, or notify-send can't report clicks

    loop = QEventLoop()
    finished = {"done": False}

    def on_activated(page: str, token: str):
        result.page, result.token = page, token
        finished["done"] = True
        loop.quit()

    def on_closed(closed_id: int):
        if closed_id == nid:
            finished["done"] = True
            loop.quit()

    notifier.activated.connect(on_activated)
    notifier.closed.connect(on_closed)
    QTimer.singleShot(int(max_wait_s * 1000), loop.quit)
    # Python only runs signal handlers between bytecodes; a ticking timer
    # lets SIGTERM (systemctl stop) end the wait cleanly.
    tick = QTimer()
    tick.timeout.connect(lambda: None)
    tick.start(1000)
    previous = signal.signal(signal.SIGTERM, lambda *_: loop.quit())
    try:
        loop.exec()
    finally:
        tick.stop()
        signal.signal(signal.SIGTERM, previous)
    if not finished["done"]:
        notifier.close(nid)
    return result


def launch_app(page: str = "", token: str = "") -> bool:
    """Open the app (or bring the running one forward) on ``page``.

    From the background service the app is started as its own transient
    unit; a child left in the service would be killed when it exits.
    """
    from dnf_gui.core.app_settings import _app_command
    argv = _app_command() + (["--page", page] if page else [])
    env = dict(os.environ)
    if token:
        env["XDG_ACTIVATION_TOKEN"] = token  # Wayland focus
        env["DESKTOP_STARTUP_ID"] = token  # X11 startup notification
    if os.environ.get("INVOCATION_ID"):  # running under systemd
        import secrets
        unit = f"app-dnf\\x2dgui@{secrets.token_hex(4)}.service"
        run = ["systemd-run", "--user", "--quiet", "--collect",
               "--slice=app.slice", f"--unit={unit}",
               "--description=DNF Package Manager"]
        if token:
            run += [f"--setenv=XDG_ACTIVATION_TOKEN={token}",
                    f"--setenv=DESKTOP_STARTUP_ID={token}"]
        try:
            if subprocess.run(run + ["--", *argv], capture_output=True,
                              timeout=30).returncode == 0:
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass
    try:
        subprocess.Popen(argv, env=env, start_new_session=True,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
        return True
    except OSError:
        return False


# ─── Notification content ─────────────────────────────────────

def _count(n: int, singular: str, plural: str | None = None) -> str:
    return f"{n} {singular if n == 1 else (plural or singular + 's')}"


def _join(parts: list[str]) -> str:
    if len(parts) <= 1:
        return "".join(parts)
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def reminder_text(result, security_only: bool, notify_flatpak: bool) -> tuple[str, str]:
    """Title and body for an update reminder (a ``ReminderResult``)."""
    parts: list[str] = []
    if security_only:
        if result.security_total:
            parts.append(_count(result.security_total, "security update"))
    elif result.dnf_updates:
        system = _count(result.dnf_updates, "system update")
        if result.security_total:
            system += f" ({result.security_total} security)"
        parts.append(system)
    elif result.security_total:
        parts.append(_count(result.security_total, "security update"))
    if notify_flatpak and result.flatpak_updates:
        parts.append(_count(result.flatpak_updates, "Flatpak update"))

    total = (result.flatpak_updates if notify_flatpak else 0) + (
        result.security_total if security_only else
        max(result.dnf_updates, result.security_total))
    verb = "is" if total == 1 and len(parts) == 1 else "are"
    body = f"{_join(parts) or 'Updates'} {verb} ready to install."
    if result.security_urgent:
        title = "Important Security Updates"
        body += " Some fix critical or important security issues."
    elif result.security_total:
        title = "Security Updates Available"
    else:
        title = "Updates Available"
    return title, body


def reminder_notification(result) -> Notification:
    return Notification(
        title=result.title or "Updates Available",
        body=result.message,
        urgency="critical" if result.security_urgent else "normal",
        page="updates",
        actions=[("updates", "View Updates")],
    )
