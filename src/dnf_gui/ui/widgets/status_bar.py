"""Status bar widget with contextual messages."""

from PyQt6.QtWidgets import QStatusBar, QLabel
from PyQt6.QtCore import QTimer


class AppStatusBar(QStatusBar):
    """Custom status bar with timed messages and persistent info."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._permanent_label = QLabel("")
        self._permanent_label.setStyleSheet("color: #6e7681; font-size: 11px;")
        self.addPermanentWidget(self._permanent_label)
        self.messageChanged.connect(self._on_message_changed)
        self.hide()

    def _on_message_changed(self, message: str):
        if not message:
            self.hide()
        else:
            self.show()

    def show_message(self, message: str, duration_ms: int = 5000):
        """Show a temporary status message."""
        self.showMessage(f"  {message}", duration_ms)

    def set_permanent(self, text: str):
        """Set the permanent status text (right side)."""
        self._permanent_label.setText(text)

    def show_success(self, message: str):
        """Show a success message with green indicator."""
        self.showMessage(f"  ✓ {message}", 5000)

    def show_error(self, message: str):
        """Show an error message with red indicator."""
        self.showMessage(f"  ✗ {message}", 8000)
