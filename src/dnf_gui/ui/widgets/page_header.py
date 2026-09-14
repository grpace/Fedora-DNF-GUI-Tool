"""Shared page header — title + subtitle with their own left inset.

Every page puts its headings at 8px from the content edge while the body
below stays at 16px. That small deliberate offset is what keeps headings
feeling anchored to the sidebar instead of floating mid-panel.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt


class PageHeader(QWidget):
    """Title/subtitle block. Optional action button sits next to the title."""

    def __init__(self, title: str, subtitle: str = "",
                 action: QPushButton | None = None, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 0, 16, 0)
        outer.setSpacing(0)

        title_label = QLabel(title)
        title_label.setObjectName("page_header")

        if action is None:
            outer.addWidget(title_label)
        else:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setAlignment(Qt.AlignmentFlag.AlignBottom)
            row.addWidget(title_label)
            row.addStretch()
            row.addWidget(action)
            outer.addLayout(row)

        if subtitle:
            sub = QLabel(subtitle)
            sub.setObjectName("page_subheader")
            sub.setWordWrap(True)
            outer.addWidget(sub)

        self._title_label = title_label

    @property
    def title_label(self) -> QLabel:
        return self._title_label
