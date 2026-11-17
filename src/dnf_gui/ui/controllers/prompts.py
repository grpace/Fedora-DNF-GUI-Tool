"""Confirmations and notices, shown one at a time by QML.

v1 called ``QMessageBox`` synchronously. A QML dialog can't block a slot
without a nested event loop, which lets shortcuts, worker results and
activation requests re-enter half-finished code. So prompts are async:
callers pass what to do on each answer and return at once; QML shows the
current prompt and calls :meth:`Prompts.reply`. Each prompt has a token,
so a late or repeated reply can't run anything twice.

Tests set :attr:`Prompts.auto_answer` to answer immediately.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Callable

from PyQt6.QtCore import QObject, pyqtProperty, pyqtSignal, pyqtSlot

YES = "yes"
NO = "no"
OK = "ok"

INFO = "info"
WARNING = "warning"
ERROR = "error"


@dataclass
class Prompt:
    token: int
    title: str
    text: str
    buttons: list[tuple[str, str]]  # (choice id, label), primary first
    default: str  # what Enter/Escape-free accept does; NO for destructive
    level: str = INFO
    details: list[str] = field(default_factory=list)
    on_choice: Callable[[str], None] | None = None
    destructive: bool = False

    def as_map(self) -> dict:
        return {
            "token": self.token, "title": self.title, "text": self.text,
            "buttons": [{"id": i, "label": label} for i, label in self.buttons],
            "defaultChoice": self.default, "level": self.level,
            "details": list(self.details), "destructive": self.destructive,
        }


class Prompts(QObject):
    """Queue of prompts; QML shows ``current`` and replies with its token."""

    currentChanged = pyqtSignal()
    # Brief, non-blocking notice (QML: showPassiveNotification).
    notice = pyqtSignal(str)
    # A prompt is waiting; the window must be visible to answer it.
    attentionNeeded = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tokens = itertools.count(1)
        self._queue: list[Prompt] = []
        # Tests: called with the Prompt, returns the choice id.
        self.auto_answer: Callable[[Prompt], str] | None = None
        self.shown: list[Prompt] = []  # every prompt shown (for tests/debugging)
        self.notices: list[str] = []

    # ── Python API ─────────────────────────────────────────────

    def confirm(self, title: str, text: str, on_yes: Callable[[], None], *,
                confirm_label: str = "Continue", cancel_label: str = "Cancel",
                destructive: bool = False, default_yes: bool | None = None,
                level: str = INFO, details: list[str] | None = None,
                on_no: Callable[[], None] | None = None) -> None:
        """Ask yes/no. ``destructive`` prompts default to No."""
        if default_yes is None:
            default_yes = not destructive

        def handle(choice: str) -> None:
            if choice == YES:
                on_yes()
            elif on_no is not None:
                on_no()

        self._enqueue(Prompt(
            token=0, title=title, text=text,
            buttons=[(YES, confirm_label), (NO, cancel_label)],
            default=YES if default_yes else NO,
            level=WARNING if destructive and level == INFO else level,
            details=list(details or []), on_choice=handle,
            destructive=destructive))

    def choose(self, title: str, text: str, buttons: list[tuple[str, str]],
               on_choice: Callable[[str], None], *, default: str | None = None,
               level: str = INFO, details: list[str] | None = None) -> None:
        """Ask with several buttons; ``on_choice`` gets the chosen id."""
        self._enqueue(Prompt(
            token=0, title=title, text=text, buttons=list(buttons),
            default=default or buttons[-1][0], level=level,
            details=list(details or []), on_choice=on_choice))

    def inform(self, title: str, text: str, *, level: str = INFO,
               details: list[str] | None = None) -> None:
        """A notice the user has to acknowledge (warnings, errors, results)."""
        self._enqueue(Prompt(
            token=0, title=title, text=text, buttons=[(OK, "OK")], default=OK,
            level=level, details=list(details or [])))

    def toast(self, text: str) -> None:
        """A brief notice that needs no answer."""
        self.notices.append(text)
        self.notice.emit(text)

    def cancel_all(self) -> None:
        """Answer every open prompt with its safe default (quitting)."""
        queue, self._queue = self._queue, []
        if queue:
            self.currentChanged.emit()
        for prompt in queue:
            safe = NO if any(i == NO for i, _ in prompt.buttons) else prompt.default
            self._resolve(prompt, safe)

    # ── QML API ────────────────────────────────────────────────

    @pyqtProperty("QVariantMap", notify=currentChanged)
    def current(self) -> dict:
        return self._queue[0].as_map() if self._queue else {}

    @pyqtProperty(bool, notify=currentChanged)
    def active(self) -> bool:
        return bool(self._queue)

    @pyqtSlot(int, str)
    def reply(self, token: int, choice: str) -> None:
        if not self._queue or self._queue[0].token != token:
            return  # stale or repeated reply
        prompt = self._queue.pop(0)
        self.currentChanged.emit()
        self._resolve(prompt, choice)

    # ── internals ──────────────────────────────────────────────

    def _enqueue(self, prompt: Prompt) -> None:
        prompt.token = next(self._tokens)
        self.shown.append(prompt)
        if self.auto_answer is not None:
            self._resolve(prompt, self.auto_answer(prompt))
            return
        self._queue.append(prompt)
        if len(self._queue) == 1:
            self.currentChanged.emit()
        self.attentionNeeded.emit()

    @staticmethod
    def _resolve(prompt: Prompt, choice: str) -> None:
        if prompt.on_choice is None:
            return
        valid = {i for i, _ in prompt.buttons}
        prompt.on_choice(choice if choice in valid else prompt.default)
