"""Live terminal page — displays real-time command output."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QPlainTextEdit, QFrame,
)
from PyQt6.QtCore import pyqtSignal, Qt


class TerminalPage(QWidget):
    """Page showing real-time terminal output from DNF operations."""

    cancel_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        from dnf_gui.ui.widgets.page_header import PageHeader
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        clear_btn = QPushButton("Clear")
        clear_btn.setObjectName("ghost_button")
        clear_btn.setProperty("compact", True)
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.clicked.connect(self._clear_terminal)

        # ── Header ──
        layout.addWidget(PageHeader(
            "Live Terminal", "Real-Time Output from System Package Operations",
            action=clear_btn))

        # ── Body ──
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(16, 0, 16, 16)
        body_layout.setSpacing(16)
        layout.addWidget(body, 1)

        # ── Status indicator ──
        self._status_row = QHBoxLayout()
        self._status_indicator = QLabel("●")
        self._status_indicator.setObjectName("term_dot_idle")
        self._status_row.addWidget(self._status_indicator)

        self._status_text = QLabel("Idle · No Operations Running")
        self._status_text.setObjectName("hint")
        self._status_row.addWidget(self._status_text)
        self._status_row.addStretch()

        body_layout.addLayout(self._status_row)

        # ── Separator ──
        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        body_layout.addWidget(sep)

        self._terminal = QPlainTextEdit()
        self._terminal.setObjectName("terminal")
        self._terminal.setReadOnly(True)
        self._terminal.setPlaceholderText(
            "Terminal output will appear here when you run operations like\n"
            "upgrading packages, installing, or removing software.\n\n"
            "Use keyboard shortcuts to quickly navigate:\n"
            "Ctrl+1 Updates · Ctrl+2 Installed · Ctrl+3 Flatpak · Ctrl+4 System Info"
        )
        body_layout.addWidget(self._terminal, 1)

        # ── Bottom Action Bar ──
        bottom_bar = QHBoxLayout()

        self._cancel_btn = QPushButton("Cancel Operation")
        self._cancel_btn.setObjectName("danger_button")
        self._cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.clicked.connect(self.cancel_clicked.emit)
        bottom_bar.addWidget(self._cancel_btn)

        bottom_bar.addStretch()
        body_layout.addLayout(bottom_bar)

    def append_line(self, text: str):
        """Append a line to the terminal output."""
        self._terminal.appendPlainText(text)
        self._scroll_to_bottom()

    def set_running(self, running: bool, description: str = ""):
        """Update the status indicator for a running operation."""
        self._cancel_btn.setEnabled(running)
        if running:
            self._status_indicator.setObjectName("term_dot_run")
            self._status_text.setText(f"Running: {description}" if description else "Operation in Progress...")
        else:
            self._status_indicator.setObjectName("term_dot_idle")
            self._status_text.setText("Idle · No Operations Running")
        # Re-polish for dynamic QSS update
        self._status_indicator.style().unpolish(self._status_indicator)
        self._status_indicator.style().polish(self._status_indicator)

    def set_success(self):
        """Show success status."""
        self._status_indicator.setObjectName("term_dot_ok")
        self._status_text.setText("Operation Completed Successfully")
        self._status_indicator.style().unpolish(self._status_indicator)
        self._status_indicator.style().polish(self._status_indicator)

    def set_error(self, message: str = ""):
        """Show error status."""
        self._status_indicator.setObjectName("term_dot_err")
        self._status_text.setText(message or "Operation Failed")
        self._status_indicator.style().unpolish(self._status_indicator)
        self._status_indicator.style().polish(self._status_indicator)

    def _clear_terminal(self):
        self._terminal.clear()

    def _scroll_to_bottom(self):
        sb = self._terminal.verticalScrollBar()
        sb.setValue(sb.maximum())
