"""Custom animated progress bar widget."""

from PyQt6.QtWidgets import QProgressBar


class AnimatedProgressBar(QProgressBar):
    """A progress bar with smooth animation and pulsing indeterminate mode."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTextVisible(False)
        self.setFixedHeight(4)
        self._animation = None

    def start_indeterminate(self):
        """Start an indeterminate (pulsing) progress animation."""
        self.setRange(0, 0)  # Qt's built-in indeterminate mode
        self.show()

    def stop(self):
        """Stop animation and reset."""
        self.setRange(0, 100)
        self.setValue(0)
        self.hide()
