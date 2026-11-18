"""Runs privileged and unprivileged commands and streams their output.

This is the security-sensitive core of the UI: every package-changing
command goes through :meth:`OperationRunner.run` / :meth:`run_chain`, which
swap ``pkexec`` for ``sudo -n`` only when the passwordless rule covers the
exact argv (``core.passwordless.maybe_passwordless``), and fall back to
pkexec once if sudo still wants a password.
"""

from __future__ import annotations

import os
import re
from typing import Callable

from PyQt6.QtCore import (
    QAbstractListModel, QByteArray, QModelIndex, QObject, Qt, QTimer, pyqtProperty,
    pyqtSignal, pyqtSlot,
)

from dnf_gui.core.passwordless import maybe_passwordless
from dnf_gui.core.worker import CommandWorker
from dnf_gui.ui.controllers.base import StateObject, state_property

CANCELLED_EXIT_CODES = (-15, 143, -9, 137)
MAX_LOG_LINES = 5000

# dnf5: "[ 3/12] Upgrading foo-1.2-3.fc45.x86_64   100% | ..." (downloads
# and transaction steps both use it).
_DNF5_STEP = re.compile(r"^\[\s*(\d+)\s*/\s*(\d+)\s*\]\s*(.*)$")
# dnf4: "  Upgrading        : foo-1.2-3.fc45.x86_64          3/12"
_DNF4_STEP = re.compile(r"^\s*([A-Z][A-Za-z ]+?)\s*:\s*(\S+)\s+(\d+)/(\d+)\s*$")
_TRAILING_STATS = re.compile(r"\s+\d+%\s*\|.*$")
# "kernel-core-0:7.2.8-300.fc45.x86_64" -> "kernel-core 7.2.8-300.fc45"
_NEVRA = re.compile(r"^(?P<name>.+?)-(?:\d+:)?(?P<vr>[^-]+-[^-]+?)\.(?:x86_64|noarch|i686|aarch64|ppc64le|s390x)$")
# Once dnf starts changing the system, stopping it midway can leave a
# half-applied transaction, so Cancel goes away.
_TRANSACTION_START = ("Running transaction", "Transaction starting")


def _friendly(text: str) -> str:
    """Drop the epoch and architecture from a package NEVRA in a step."""
    words = text.split()
    out = []
    for word in words:
        match = _NEVRA.match(word)
        out.append(f"{match['name']} {match['vr']}" if match else word)
    return " ".join(out)


def parse_step(line: str) -> tuple[str, int, int] | None:
    """``(description, n, total)`` for a dnf progress line, else None."""
    match = _DNF5_STEP.match(line.strip())
    if match:
        n, total, rest = int(match.group(1)), int(match.group(2)), match.group(3)
        rest = _TRAILING_STATS.sub("", rest).strip()
        if total > 0 and rest:
            return _friendly(rest), n, total
        return None
    match = _DNF4_STEP.match(line)
    if match:
        verb, pkg = match.group(1).strip(), match.group(2)
        n, total = int(match.group(3)), int(match.group(4))
        if total > 0:
            return _friendly(f"{verb} {pkg}"), n, total
    return None


class LogModel(QAbstractListModel):
    """The current operation's output, one row per line, capped."""

    countChanged = pyqtSignal()
    appended = pyqtSignal(str)   # new text (one or more lines)
    cleared = pyqtSignal()
    LineRole = Qt.ItemDataRole.UserRole + 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lines: list[str] = []

    def roleNames(self):
        return {self.LineRole: QByteArray(b"line")}

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._lines)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        if role in (Qt.ItemDataRole.DisplayRole, self.LineRole):
            return self._lines[index.row()]
        return None

    def append(self, text: str) -> None:
        new = text.split("\n")
        if not new:
            return
        overflow = len(self._lines) + len(new) - MAX_LOG_LINES
        if overflow > 0:
            drop = min(overflow, len(self._lines))
            self.beginRemoveRows(QModelIndex(), 0, drop - 1)
            del self._lines[:drop]
            self.endRemoveRows()
            new = new[-MAX_LOG_LINES:]
        start = len(self._lines)
        self.beginInsertRows(QModelIndex(), start, start + len(new) - 1)
        self._lines.extend(new)
        self.endInsertRows()
        self.countChanged.emit()
        self.appended.emit("\n".join(new))

    def clear(self) -> None:
        self.beginResetModel()
        self._lines = []
        self.endResetModel()
        self.countChanged.emit()
        self.cleared.emit()

    def text(self) -> str:
        return "\n".join(self._lines)

    @pyqtProperty(int, notify=countChanged)
    def count(self) -> int:
        return len(self._lines)


class OperationRunner(StateObject):
    """One command (or chain) at a time, with live output for the footer."""

    changed = pyqtSignal()
    # (exit code, operation, failed chain step?) — after every operation.
    finished = pyqtSignal(int, str, bool)
    # The user tried to start something while another operation runs.
    busyRejected = pyqtSignal()

    _defaults = {
        "busy": False,
        "status": "idle",   # idle | auth | running | succeeded | failed | cancelled
        "operation": "",
        "step": "",
        "progress": -1.0,   # 0..1, or -1 for indeterminate
        "statusText": "",
        "cancelling": False,
        "cancellable": False,
    }

    def __init__(self, settings, prompts, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._prompts = prompts
        self._log = LogModel(self)
        self._worker: CommandWorker | None = None
        self._queue: list[list[str]] = []
        self._output: list[str] = []  # dnf output of the current operation
        self.failed_steps_left = 0  # steps a failed chain didn't reach
        self._operation = ""
        self._on_done: Callable[[int], None] | None = None
        self._external = None  # a non-command worker (app download) counts as busy

    busy = state_property(bool, "busy", changed)
    status = state_property(str, "status", changed)
    operation = state_property(str, "operation", changed)
    step = state_property(str, "step", changed)
    progress = state_property(float, "progress", changed)
    statusText = state_property(str, "statusText", changed)
    cancelling = state_property(bool, "cancelling", changed)
    cancellable = state_property(bool, "cancellable", changed)

    @pyqtProperty(QObject, constant=True)
    def log(self) -> LogModel:
        return self._log

    # ── Python API ─────────────────────────────────────────────

    @property
    def output(self) -> list[str]:
        """Lines dnf printed during the current/last operation."""
        return list(self._output)

    @property
    def worker(self) -> CommandWorker | None:
        return self._worker

    @property
    def queue(self) -> list[list[str]]:
        return list(self._queue)

    def running(self) -> bool:
        worker = self._worker
        external = self._external
        return bool((worker is not None and worker.isRunning())
                    or (external is not None and external.isRunning()))

    def check_busy(self) -> bool:
        """True (and tell the user) if an operation is already running."""
        if not self.running() and not self._queue:
            return False
        self._prompts.inform(
            "Operation in Progress",
            "Another operation is still running. Wait for it to finish "
            "before starting a new one.")
        self.busyRejected.emit()
        return True

    def run(self, cmd: list[str], operation: str) -> bool:
        """Run one command. Returns False if another one is running."""
        if self.check_busy():
            return False
        self._begin(operation, f"  {operation}")
        self._queue = []
        self._start(cmd, lambda code: self._finish(code, operation, False))
        return True

    def run_chain(self, cmds: list[list[str]], operation: str) -> bool:
        """Run commands back to back; stop at the first failure.

        Used by Update Everything, so the privileged dnf step and the
        unprivileged Flatpak step share one log.
        """
        if self.check_busy():
            return False
        self._begin(operation, f"  {operation} ({len(cmds)} steps)")
        self._queue = list(cmds)
        self._next_in_chain(operation)
        return True

    def start_external(self, operation: str, worker=None) -> None:
        """Show progress for work that isn't a CommandWorker (app download).

        While it runs the runner is busy (nothing else starts), but it
        can't be cancelled.
        """
        self._begin(operation, f"  {operation}")
        self._external = worker
        self._set(busy=True, cancellable=False)

    def finish_external(self, ok: bool, text: str = "") -> None:
        self._external = None
        self._set(busy=False, status="succeeded" if ok else "failed",
                  statusText=text or ("Completed" if ok else "Failed"),
                  progress=-1.0, step="")

    def append(self, text: str) -> None:
        self._log.append(text)

    def set_result_text(self, text: str) -> None:
        self._set(statusText=text)

    @pyqtSlot()
    def cancel(self) -> None:
        worker = self._worker
        if worker is None or self._state["cancelling"]:
            return
        self.append("\n⚠ Cancelling operation...")
        self._set(cancelling=True)
        self._try_cancel(worker, attempts=30)

    def _try_cancel(self, worker: CommandWorker, attempts: int) -> None:
        """Cancel once the process exists (a click right after Start would
        otherwise be lost while the thread is still launching it)."""
        if worker is not self._worker:
            return  # already finished
        if worker._process is not None:
            worker.cancel()
        elif attempts > 0:
            QTimer.singleShot(100, lambda: self._try_cancel(worker, attempts - 1))

    @pyqtSlot()
    def clear(self) -> None:
        if self.running():
            return
        self._log.clear()
        self._set(status="idle", operation="", step="", statusText="",
                  progress=-1.0)

    @pyqtSlot(result=str)
    def text(self) -> str:
        return self._log.text()

    @pyqtSlot()
    def copyToClipboard(self) -> None:
        from PyQt6.QtGui import QGuiApplication
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self._log.text())
            self._prompts.toast("Output copied")

    # ── internals ──────────────────────────────────────────────

    def _begin(self, operation: str, banner: str) -> None:
        self._operation = operation
        self.failed_steps_left = 0
        self._output = []
        rule = "─" * 60
        self.append(f"\n{rule}\n{banner}\n{rule}\n")
        self._set(busy=True, status="running", operation=operation, step="",
                  progress=-1.0, statusText="", cancelling=False)

    def _next_in_chain(self, operation: str) -> None:
        if not self._queue:
            self._finish(0, operation, False)
            return
        cmd = self._queue.pop(0)
        short = " ".join(cmd[1:3]) if len(cmd) > 2 else " ".join(cmd)
        self.append(f"\n── Step: {short} ──\n")
        self._start(cmd, lambda code: self._on_chain_step(code, operation))

    def _on_chain_step(self, code: int, operation: str) -> None:
        if code != 0:
            # Recorded before the queue is cleared: callers need to know
            # whether the failed step was the last one.
            self.failed_steps_left = len(self._queue)
            self.append(f"\n✗ Step failed (exit {code}) — stopping here. "
                        "Fix the error above and re-run.")
            self._finish(code, operation, True)
            return
        self._next_in_chain(operation)

    def _start(self, cmd: list[str], done: Callable[[int], None], *,
               retried: bool = False) -> None:
        """Start a CommandWorker, swapping pkexec→sudo -n when covered.

        If the rule claims to cover the command but sudo still demands a
        password (e.g. the rule was deleted outside the app), retry exactly
        once via pkexec so the user gets a password prompt instead of a
        cryptic failure.
        """
        # The retry is the password-prompt fallback: plain pkexec.
        effective = cmd if retried else maybe_passwordless(
            cmd, self._settings.passwordless_scope)
        if effective != cmd:
            self.append("(passwordless updates rule active — no password needed)")
        collected: list[str] = []
        worker = CommandWorker(effective, parent=self)
        waiting_for_password = bool(effective) and effective[0] == "pkexec"
        self._set(status="auth" if waiting_for_password else "running")

        def on_line(line: str) -> None:
            collected.append(line)
            self._output.append(line)
            self.append(line)
            if self._state["status"] == "auth":
                self._set(status="running")
            if self._state["cancellable"] and line.strip().startswith(_TRANSACTION_START):
                self._set(cancellable=False)
            step = parse_step(line)
            if step is not None:
                text, n, total = step
                self._set(step=f"{text} ({n} of {total})", progress=n / total)

        def on_done(code: int) -> None:
            if self._worker is worker:
                self._worker = None
            if (code != 0 and not retried and effective
                    and os.path.basename(effective[0]) == "sudo"
                    and any("password" in line.lower() for line in collected)):
                self.append("(passwordless rule didn't apply — "
                            "falling back to password prompt)")
                self._start(cmd, done, retried=True)
                return
            done(code)

        def on_error(error: str) -> None:
            # Failed to start (e.g. binary missing): finish through the
            # normal path so chains stop and pending state is reset.
            self.append(f"\n❌ Error: {error}")
            on_done(-1)

        self._set(cancellable=True)
        worker.output_line.connect(on_line)
        worker.finished.connect(on_done)
        worker.error.connect(on_error)
        self._worker = worker
        worker.start()

    def _finish(self, code: int, operation: str, chain_failed: bool) -> None:
        self._queue = []
        if code == 0:
            status, text = "succeeded", "Completed"
        elif code in CANCELLED_EXIT_CODES:
            status, text = "cancelled", "Operation Cancelled"
        else:
            status, text = "failed", f"Failed (exit code {code})"
        self._set(busy=False, status=status, statusText=text, cancelling=False,
                  cancellable=False,
                  progress=1.0 if code == 0 else self._state["progress"])
        self.finished.emit(code, operation, chain_failed)
