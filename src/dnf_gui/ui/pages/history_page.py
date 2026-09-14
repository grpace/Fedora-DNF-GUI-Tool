"""Transaction history page — view DNF transaction log with undo capability."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QFrame,
)
from PyQt6.QtCore import pyqtSignal, Qt


class HistoryCard(QFrame):
    """Card representing a single DNF transaction."""

    undo_clicked = pyqtSignal(str)  # transaction_id
    info_clicked = pyqtSignal(str)  # transaction_id

    def __init__(self, txn: dict, parent=None):
        super().__init__(parent)
        self._txn = txn
        self.setObjectName("card")
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(14)

        # Transaction ID badge
        id_badge = QLabel(f"#{self._txn.get('id', '?')}")
        id_badge.setObjectName("txn_badge")
        id_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        id_badge.setFixedWidth(48)
        layout.addWidget(id_badge)

        # Info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        cmd_label = QLabel(self._txn.get("command", "Unknown command"))
        cmd_label.setObjectName("card_title")
        info_layout.addWidget(cmd_label)

        details = []
        date = self._txn.get("date", "")
        if date:
            details.append(date)
        action = self._txn.get("action", "")
        if action:
            details.append(action)
        altered = self._txn.get("altered", "")
        if altered:
            details.append(f"{altered} packages altered")

        if details:
            detail_label = QLabel(" · ".join(details))
            detail_label.setObjectName("card_detail")
            info_layout.addWidget(detail_label)

        layout.addLayout(info_layout, 1)

        # Actions
        action_layout = QHBoxLayout()
        action_layout.setSpacing(8)

        info_btn = QPushButton("Details")
        info_btn.setObjectName("ghost_button")
        info_btn.setProperty("compact", True)
        info_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        info_btn.clicked.connect(lambda: self.info_clicked.emit(self._txn.get("id", "")))
        action_layout.addWidget(info_btn)

        undo_btn = QPushButton("Undo")
        undo_btn.setObjectName("danger_button")
        undo_btn.setProperty("compact", True)
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
        from dnf_gui.ui.widgets.page_header import PageHeader
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.setObjectName("ghost_button")
        self._refresh_btn.setProperty("compact", True)
        self._refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._refresh_btn.clicked.connect(self.refresh_clicked.emit)

        # ── Header ──
        layout.addWidget(PageHeader(
            "Transaction History", "Review and Undo Recent DNF Package Operations",
            action=self._refresh_btn))

        # ── Body ──
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(20, 0, 20, 20)
        body_layout.setSpacing(16)
        layout.addWidget(body, 1)

        self._count_label = QLabel("")
        self._count_label.setObjectName("hint")
        body_layout.addWidget(self._count_label)

        # ── Separator ──
        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        body_layout.addWidget(sep)

        # ── Transaction List ──
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(8)
        self._list_layout.addStretch()

        self._scroll.setWidget(self._list_container)
        body_layout.addWidget(self._scroll, 1)

        # ── Transaction Details Drawer (collapsed by default) ──
        self._detail_drawer = QFrame()
        self._detail_drawer.setObjectName("card")
        drawer_layout = QVBoxLayout(self._detail_drawer)
        drawer_layout.setContentsMargins(16, 12, 16, 12)
        drawer_layout.setSpacing(8)

        drawer_hdr = QHBoxLayout()
        self._drawer_title = QLabel("Transaction Details")
        self._drawer_title.setObjectName("card_title")
        drawer_hdr.addWidget(self._drawer_title)
        drawer_hdr.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setObjectName("ghost_button")
        close_btn.setProperty("compact", True)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self._detail_drawer.hide)
        drawer_hdr.addWidget(close_btn)
        drawer_layout.addLayout(drawer_hdr)

        self._detail_text = QLabel("")
        self._detail_text.setObjectName("card_mono")
        self._detail_text.setWordWrap(True)
        drawer_layout.addWidget(self._detail_text)

        body_layout.addWidget(self._detail_drawer)
        self._detail_drawer.hide()

    def display_history(self, history: list[dict]):
        """Display transaction history items."""
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not history:
            self._count_label.setText("No transaction history available")
            return

        self._count_label.setText(f"{len(history)} recent transactions")

        for txn in history:
            card = HistoryCard(txn)
            card.undo_clicked.connect(self.undo_clicked.emit)
            card.info_clicked.connect(self.info_requested.emit)
            self._list_layout.insertWidget(self._list_layout.count() - 1, card)

    def show_detail(self, text: str, txn_id: str = ""):
        """Show full transaction output in the detail drawer."""
        if txn_id:
            self._drawer_title.setText(f"Transaction #{txn_id} Details")
        else:
            self._drawer_title.setText("Transaction Details")
        self._detail_text.setText(text)
        self._detail_drawer.show()

    def set_loading(self, loading: bool = True):
        if loading:
            self._count_label.setText("Loading transaction history...")
