"""Keep one app window per user.

The first instance listens on a local socket. A later launch (the app
menu, or a clicked reminder) sends it the page to show plus the launch's
activation token, then exits, so the running window comes forward instead
of a second copy running dnf next to the first.
"""

from __future__ import annotations

import json
import os

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

_MAX_REQUEST = 4096


def socket_name() -> str:
    """Per-user socket path, private to the user's runtime dir."""
    runtime = os.environ.get("XDG_RUNTIME_DIR", "")
    path = os.path.join(runtime, "dnf-gui.socket") if runtime else ""
    # Unix socket paths are limited to 108 bytes.
    if path and os.path.isdir(runtime) and len(path.encode()) < 100:
        return path
    return f"dnf-gui-{os.getuid()}"


def _connect(timeout_ms: int) -> QLocalSocket | None:
    sock = QLocalSocket()
    sock.connectToServer(socket_name())
    return sock if sock.waitForConnected(timeout_ms) else None


def forward_to_running(request: dict, timeout_ms: int = 5000) -> bool:
    """Hand ``request`` to a running instance. False if none answers."""
    sock = _connect(min(timeout_ms, 1000))
    if sock is None:
        return False
    try:
        sock.write(json.dumps(request).encode() + b"\n")
        sock.flush()
        sock.waitForBytesWritten(timeout_ms)
        # Wait for the acknowledgement, so a frozen instance isn't mistaken
        # for one that handled the request.
        return sock.waitForReadyRead(timeout_ms) and bytes(sock.readAll()).startswith(b"ok")
    finally:
        sock.disconnectFromServer()


def parse_request(raw: bytes) -> dict | None:
    """Validate a request: only known string fields are passed on."""
    try:
        data = json.loads(raw.decode("utf-8", "replace"))
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    page = data.get("page", "")
    token = data.get("token", "")
    if not isinstance(page, str) or not isinstance(token, str):
        return None
    return {"page": page[:32], "token": token[:512]}


class InstanceServer(QObject):
    """Listens for later launches and emits what they asked for."""

    request_received = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._server = QLocalServer(self)
        self._server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self._server.newConnection.connect(self._on_connection)

    def listen(self) -> bool:
        name = socket_name()
        if self._server.listen(name):
            return True
        # A crashed instance leaves its socket behind. Replace it only if
        # nothing accepts connections on it: a busy instance that was too
        # slow to answer keeps its socket.
        live = _connect(500)
        if live is not None:
            live.disconnectFromServer()
            return False
        QLocalServer.removeServer(name)
        return self._server.listen(name)

    def _on_connection(self):
        while self._server.hasPendingConnections():
            sock = self._server.nextPendingConnection()
            buffer = bytearray()
            done = []

            def read(sock=sock, buffer=buffer, done=done):
                buffer.extend(bytes(sock.readAll()))
                if done or (b"\n" not in buffer and len(buffer) < _MAX_REQUEST):
                    return
                done.append(True)
                request = parse_request(bytes(buffer).split(b"\n", 1)[0])
                sock.write(b"ok\n" if request is not None else b"error\n")
                sock.flush()
                sock.disconnectFromServer()
                if request is not None:
                    self.request_received.emit(request)

            sock.readyRead.connect(read)
            sock.disconnected.connect(sock.deleteLater)
            if sock.bytesAvailable():
                read()  # arrived before readyRead was connected
