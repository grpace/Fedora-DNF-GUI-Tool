"""Shared page header — title + subtitle with fixed left inset.

Contract (covered by tests): the ``page_header`` QLabel sits at x=8 within
the page. Body content on every page stays at 16px, so headings feel
anchored to the sidebar.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt


class PageHeader(QWidget):
    """Title/subtitle block. Optional action button sits next to the title."""

    def __init__(self, title: str, subtitle: str = "",
                 action: QPushButton | None = None,
                 kicker: str = "", parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 16, 16, 12)
        outer.setSpacing(4)

        if kicker:
            kick = QLabel(kicker.upper())
            kick.setObjectName("page_kicker")
            outer.addWidget(kick)

        title_label = QLabel(title)
        title_label.setObjectName("page_header")

        if action is None:
            outer.addWidget(title_label)
        else:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(12)
            row.setAlignment(Qt.AlignmentFlag.AlignVCenter)
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
