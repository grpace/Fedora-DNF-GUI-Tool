"""Terminal page — live output view for DNF operations."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QPlainTextEdit, QFrame, QLineEdit
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QTextCursor


class TerminalPage(QWidget):
    """Page showing live terminal output from DNF operations."""

    clear_clicked = pyqtSignal()
    input_submitted = pyqtSignal(str)
    cancel_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 16)
        layout.setSpacing(16)

        # ── Header ──
        header_row = QHBoxLayout()

        header = QLabel("Terminal Output")
        header.setObjectName("page_header")
        header_row.addWidget(header)
        header_row.addStretch()

        clear_btn = QPushButton("Clear")
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

        self._terminal = QPlainTextEdit()
        self._terminal.setObjectName("terminal")
        self._terminal.setReadOnly(True)
        self._terminal.setPlaceholderText(
            "Terminal output will appear here when you run operations like\n"
            "upgrading packages, installing, or removing software.\n\n"
            "Try checking for updates or installing a package to get started!"
        )
        layout.addWidget(self._terminal, 1)

        # ── Terminal Input ──
        self._input_row = QHBoxLayout()
        self._input_row.setSpacing(12)
        
        self._input_field = QLineEdit()
        self._input_field.setObjectName("search_input")
        self._input_field.setPlaceholderText("Type input here and press Enter (e.g. 'y' for Yes)...")
        self._input_field.returnPressed.connect(self._send_input)
        self._input_field.setVisible(False)
        self._input_row.addWidget(self._input_field, 1)
        
        self._cancel_btn = QPushButton("Cancel Process")
        self._cancel_btn.setObjectName("danger_button")
        self._cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cancel_btn.clicked.connect(self.cancel_clicked.emit)
        self._cancel_btn.setVisible(False)
        self._input_row.addWidget(self._cancel_btn)
        
        layout.addLayout(self._input_row)

    def append_line(self, line: str):
        """Append a line to the terminal output."""
        self._terminal.appendPlainText(line)
        # Auto-scroll to bottom
        cursor = self._terminal.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._terminal.setTextCursor(cursor)

    def _send_input(self):
        """Emit text from input field and clear it."""
        text = self._input_field.text()
        self._input_field.clear()
        # Echo input to terminal output visually
        self.append_line(f"> {text}")
        self.input_submitted.emit(text)

    def set_running(self, running: bool, operation: str = ""):
        """Update the running status indicator."""
        self._input_field.setVisible(running)
        self._cancel_btn.setVisible(running)
        if running:
            self._input_field.setFocus()
            self._status_indicator.setStyleSheet("color: #3fb950; font-size: 10px;")
            self._status_text.setText(f"Running — {operation}")
        else:
            self._status_indicator.setStyleSheet("color: #6e7681; font-size: 10px;")
            self._status_text.setText("Idle — No operations running")

    def set_error(self):
        """Set error status."""
        self._input_field.setVisible(False)
        self._cancel_btn.setVisible(False)
        self._status_indicator.setStyleSheet("color: #f85149; font-size: 10px;")
        self._status_text.setText("Error — Operation failed")

    def set_success(self):
        """Set success status."""
        self._input_field.setVisible(False)
        self._cancel_btn.setVisible(False)
        self._status_indicator.setStyleSheet("color: #3fb950; font-size: 10px;")
        self._status_text.setText("Complete — Operation finished successfully")

    def _clear_terminal(self):
        """Clear all terminal output."""
        self._terminal.clear()
        self.set_running(False)
