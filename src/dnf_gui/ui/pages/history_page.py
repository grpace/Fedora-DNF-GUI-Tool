"""History page — DNF transaction history with undo capability."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QPlainTextEdit
)
from PyQt6.QtCore import pyqtSignal, Qt


class HistoryCard(QFrame):
    """Card displaying a single DNF transaction."""

    undo_clicked = pyqtSignal(str)   # transaction_id
    info_clicked = pyqtSignal(str)   # transaction_id

    def __init__(self, transaction: dict, parent=None):
        super().__init__(parent)
        self._txn = transaction
        self.setObjectName("card")
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        # Transaction ID badge
        id_label = QLabel(f"#{self._txn.get('id', '?')}")
        id_label.setFixedWidth(60)
        id_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        id_label.setStyleSheet("""
            background-color: #1a3a5c;
            color: #58a6ff;
            border-radius: 6px;
            font-size: 13px;
            font-weight: 700;
            padding: 6px 8px;
        """)
        layout.addWidget(id_label)

        # Info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        command = self._txn.get("command", "Unknown operation")
        cmd_label = QLabel(command)
        cmd_label.setStyleSheet("font-size: 13px; font-weight: 600; color: #e6edf3;")
        cmd_label.setWordWrap(True)
        info_layout.addWidget(cmd_label)

        detail_parts = []
        if self._txn.get("date"):
            detail_parts.append(self._txn["date"])
        if self._txn.get("action"):
            detail_parts.append(self._txn["action"])
        if self._txn.get("altered"):
            detail_parts.append(f"{self._txn['altered']} packages")

        if detail_parts:
            detail = QLabel(" · ".join(detail_parts))
            detail.setStyleSheet("color: #8b949e; font-size: 12px;")
            info_layout.addWidget(detail)

        layout.addLayout(info_layout, 1)

        # Action buttons
        action_layout = QHBoxLayout()
        action_layout.setSpacing(8)

        info_btn = QPushButton("Details")
        info_btn.setObjectName("primary_button")
        info_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent; color: #58a6ff;
                border: 1px solid #58a6ff; border-radius: 8px;
                padding: 8px 14px; font-size: 12px; font-weight: 600;
                min-width: 70px;
            }
            QPushButton:hover { background-color: #58a6ff; color: #ffffff; }
        """)
        info_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        info_btn.clicked.connect(lambda: self.info_clicked.emit(self._txn.get("id", "")))
        action_layout.addWidget(info_btn)

        undo_btn = QPushButton("Undo")
        undo_btn.setObjectName("danger_button")
        undo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        undo_btn.clicked.connect(lambda: self.undo_clicked.emit(self._txn.get("id", "")))
        action_layout.addWidget(undo_btn)

        layout.addLayout(action_layout)


class HistoryPage(QWidget):
    """Page showing DNF transaction history."""

    refresh_clicked = pyqtSignal()
    undo_clicked = pyqtSignal(str)
    info_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 16)
        layout.setSpacing(16)

        # ── Header ──
        header_row = QHBoxLayout()
        header = QLabel("Transaction History")
        header.setObjectName("page_header")
        header_row.addWidget(header)
        header_row.addStretch()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("primary_button")
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.setStyleSheet("QPushButton { margin-top: 24px; }")
        refresh_btn.clicked.connect(self.refresh_clicked.emit)
        header_row.addWidget(refresh_btn)
        layout.addLayout(header_row)

        subheader = QLabel("View and undo recent DNF package operations")
        subheader.setObjectName("page_subheader")
        layout.addWidget(subheader)

        self._count_label = QLabel("")
        self._count_label.setStyleSheet("color: #8b949e; font-size: 13px;")
        layout.addWidget(self._count_label)

        # ── Separator ──
        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        # ── Info Detail Panel (hidden by default) ──
        self._detail_panel = QFrame()
        self._detail_panel.setObjectName("card")
        self._detail_panel.hide()
        detail_layout = QVBoxLayout(self._detail_panel)

        detail_header = QHBoxLayout()
        detail_title = QLabel("📋  Transaction Details")
        detail_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #58a6ff;")
        detail_header.addWidget(detail_title)
        detail_header.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent; color: #8b949e; border: none;
                font-size: 16px; padding: 4px 8px;
            }
            QPushButton:hover { color: #e6edf3; }
        """)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(lambda: self._detail_panel.hide())
        detail_header.addWidget(close_btn)
        detail_layout.addLayout(detail_header)

        self._detail_text = QPlainTextEdit()
        self._detail_text.setObjectName("terminal")
        self._detail_text.setReadOnly(True)
        self._detail_text.setMaximumHeight(200)
        detail_layout.addWidget(self._detail_text)

        layout.addWidget(self._detail_panel)

        # ── History List ──
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(6)
        self._list_layout.addStretch()

        self._scroll.setWidget(self._list_container)
        layout.addWidget(self._scroll, 1)

        # ── Empty State ──
        self._status_label = QLabel("Click 'Refresh' to load transaction history")
        self._status_label.setObjectName("loading_label")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._list_layout.insertWidget(0, self._status_label)

    def set_loading(self, loading: bool):
        if loading:
            self._status_label.setText("Checking history...")
            self._status_label.show()

    def display_history(self, transactions: list[dict]):
        # Clear
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not transactions:
            self._status_label.setText("No transaction history available")
            self._status_label.show()
            self._list_layout.insertWidget(0, self._status_label)
            self._count_label.setText("")
        else:
            self._status_label.hide()
            self._count_label.setText(f"{len(transactions)} recent transactions")

            # Show most recent first
            for txn in reversed(transactions):
                card = HistoryCard(txn)
                card.undo_clicked.connect(self.undo_clicked.emit)
                card.info_clicked.connect(self.info_requested.emit)
                self._list_layout.insertWidget(self._list_layout.count() - 1, card)

    def show_detail(self, detail_text: str):
        """Show transaction detail in the panel."""
        self._detail_text.setPlainText(detail_text)
        self._detail_panel.show()
