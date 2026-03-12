"""Terminal page — live output view for DNF operations."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QPlainTextEdit, QFrame
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QTextCursor


class TerminalPage(QWidget):
    """Page showing live terminal output from DNF operations."""

    clear_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 0, 32, 24)
        layout.setSpacing(16)

        # ── Header ──
        header_row = QHBoxLayout()

        header = QLabel("Terminal Output")
        header.setObjectName("page_header")
        header.setContentsMargins(0, 24, 0, 0)
        header_row.addWidget(header)
        header_row.addStretch()

        clear_btn = QPushButton("🗑️  Clear")
        clear_btn.setObjectName("danger_button")
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.clicked.connect(self._clear_terminal)
        clear_btn.setStyleSheet("""
            QPushButton {
                margin-top: 24px;
            }
        """)
        header_row.addWidget(clear_btn)

        layout.addLayout(header_row)

        subheader = QLabel("Real-time output from DNF package operations")
        subheader.setObjectName("page_subheader")
        layout.addWidget(subheader)

        # ── Status indicator ──
        self._status_row = QHBoxLayout()
        self._status_indicator = QLabel("●")
        self._status_indicator.setStyleSheet("color: #6e7681; font-size: 10px;")
        self._status_row.addWidget(self._status_indicator)

        self._status_text = QLabel("Idle — No operations running")
        self._status_text.setStyleSheet("color: #8b949e; font-size: 12px;")
        self._status_row.addWidget(self._status_text)
        self._status_row.addStretch()

        layout.addLayout(self._status_row)

        # ── Separator ──
        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        # ── Terminal Output ──
        self._terminal = QPlainTextEdit()
        self._terminal.setObjectName("terminal")
        self._terminal.setReadOnly(True)
        self._terminal.setPlaceholderText(
            "Terminal output will appear here when you run operations like\n"
            "upgrading packages, installing, or removing software.\n\n"
            "Try checking for updates or installing a package to get started!"
        )
        layout.addWidget(self._terminal, 1)

    def append_line(self, line: str):
        """Append a line to the terminal output."""
        self._terminal.appendPlainText(line)
        # Auto-scroll to bottom
        cursor = self._terminal.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._terminal.setTextCursor(cursor)

    def set_running(self, running: bool, operation: str = ""):
        """Update the running status indicator."""
        if running:
            self._status_indicator.setStyleSheet("color: #3fb950; font-size: 10px;")
            self._status_text.setText(f"Running — {operation}")
        else:
            self._status_indicator.setStyleSheet("color: #6e7681; font-size: 10px;")
            self._status_text.setText("Idle — No operations running")

    def set_error(self):
        """Set error status."""
        self._status_indicator.setStyleSheet("color: #f85149; font-size: 10px;")
        self._status_text.setText("Error — Operation failed")

    def set_success(self):
        """Set success status."""
        self._status_indicator.setStyleSheet("color: #3fb950; font-size: 10px;")
        self._status_text.setText("Complete — Operation finished successfully")

    def _clear_terminal(self):
        """Clear all terminal output."""
        self._terminal.clear()
        self.set_running(False)
