"""System info page — beautiful dashboard showing system details."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QGridLayout, QScrollArea, QPushButton, QProgressBar
)
from PyQt6.QtCore import pyqtSignal, Qt


class SystemInfoPage(QWidget):
    """Page displaying comprehensive system information."""

    refresh_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        from dnf_gui.ui.widgets.page_header import PageHeader
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("primary_button")
        refresh_btn.setProperty("compact", True)
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.clicked.connect(self.refresh_clicked.emit)

        # ── Header (own left inset, closer to the sidebar) ──
        layout.addWidget(PageHeader(
            "System Overview", "Hardware, software, and system health at a glance",
            action=refresh_btn))

        # ── Body ──
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(16, 0, 16, 16)
        body_layout.setSpacing(20)
        layout.addWidget(body, 1)

        # ── Scrollable Content ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        scroll_content = QWidget()
        self._content_layout = QVBoxLayout(scroll_content)
        self._content_layout.setContentsMargins(0, 0, 16, 0)
        self._content_layout.setSpacing(20)

        # ── OS & Host Card ──
        os_card = QFrame()
        os_card.setObjectName("card")
        os_layout = QVBoxLayout(os_card)

        os_title = QLabel("Operating System")
        os_title.setObjectName("tool_title")
        os_layout.addWidget(os_title)

        self._os_grid = QGridLayout()
        self._os_grid.setSpacing(8)
        self._os_grid.setColumnMinimumWidth(0, 150)

        self._os_fields = {}
        self._os_optional_rows = {}  # key -> (lbl, val) for conditional hide
        os_items = [
            ("Distribution", "fedora_version", False),
            ("Hostname", "hostname", False),
            ("Architecture", "architecture", False),
            ("Kernel", "kernel", False),
            ("Desktop", "desktop_env", False),
            ("Display Server", "display_server", False),
            ("Shell", "shell", False),
            ("Uptime", "uptime", False),
            ("Boot Mode", "boot_mode", True),
            ("SELinux", "selinux_status", True),
            ("Virtualization", "virtualization", True),
        ]
        for row, (label, key, optional) in enumerate(os_items):
            lbl = QLabel(label)
            lbl.setObjectName("card_detail")
            val = QLabel("—")
            val.setObjectName("card_title")
            val.setWordWrap(True)
            self._os_grid.addWidget(lbl, row, 0)
            self._os_grid.addWidget(val, row, 1)
            self._os_fields[key] = val
            if optional:
                self._os_optional_rows[key] = (lbl, val)

        os_layout.addLayout(self._os_grid)
        self._content_layout.addWidget(os_card)

        # ── Hardware Row ──
        hw_row = QHBoxLayout()
        hw_row.setSpacing(16)

        # CPU Card
        cpu_card = QFrame()
        cpu_card.setObjectName("card")
        cpu_layout = QVBoxLayout(cpu_card)

        cpu_title = QLabel("Processor")
        cpu_title.setObjectName("tool_title")
        cpu_layout.addWidget(cpu_title)

        self._cpu_model = QLabel("—")
        self._cpu_model.setObjectName("card_title")
        self._cpu_model.setWordWrap(True)
        cpu_layout.addWidget(self._cpu_model)

        self._cpu_cores = QLabel("")
        self._cpu_cores.setObjectName("card_detail")
        cpu_layout.addWidget(self._cpu_cores)
        cpu_layout.addStretch()

        hw_row.addWidget(cpu_card)

        # GPU Card
        gpu_card = QFrame()
        gpu_card.setObjectName("card")
        gpu_layout = QVBoxLayout(gpu_card)

        gpu_title = QLabel("Graphics")
        gpu_title.setObjectName("tool_title")
        gpu_layout.addWidget(gpu_title)

        self._gpu_model = QLabel("—")
        self._gpu_model.setObjectName("card_title")
        self._gpu_model.setWordWrap(True)
        gpu_layout.addWidget(self._gpu_model)
        gpu_layout.addStretch()

        hw_row.addWidget(gpu_card)
        self._content_layout.addLayout(hw_row)

        # ── Storage & Memory Row ──
        resource_row = QHBoxLayout()
        resource_row.setSpacing(16)

        # RAM Card
        ram_card = QFrame()
        ram_card.setObjectName("card")
        ram_layout = QVBoxLayout(ram_card)

        ram_title = QLabel("Memory (RAM)")
        ram_title.setObjectName("tool_title")
        ram_layout.addWidget(ram_title)

        self._ram_bar = QProgressBar()
        self._ram_bar.setFixedHeight(8)
        self._ram_bar.setTextVisible(False)
        self._ram_bar.setObjectName("resource_bar")
        ram_layout.addWidget(self._ram_bar)

        self._ram_label = QLabel("— / —")
        self._ram_label.setObjectName("card_title")
        ram_layout.addWidget(self._ram_label)

        self._ram_percent = QLabel("")
        self._ram_percent.setObjectName("card_detail")
        ram_layout.addWidget(self._ram_percent)
        ram_layout.addStretch()

        resource_row.addWidget(ram_card)

        # Disk Card
        disk_card = QFrame()
        disk_card.setObjectName("card")
        disk_layout = QVBoxLayout(disk_card)

        disk_title = QLabel("Disk (Root)")
        disk_title.setObjectName("tool_title")
        disk_layout.addWidget(disk_title)

        self._disk_bar = QProgressBar()
        self._disk_bar.setFixedHeight(8)
        self._disk_bar.setTextVisible(False)
        self._disk_bar.setObjectName("resource_bar")
        disk_layout.addWidget(self._disk_bar)

        self._disk_label = QLabel("— / —")
        self._disk_label.setObjectName("card_title")
        disk_layout.addWidget(self._disk_label)

        self._disk_free_label = QLabel("")
        self._disk_free_label.setObjectName("card_detail")
        disk_layout.addWidget(self._disk_free_label)
        disk_layout.addStretch()

        resource_row.addWidget(disk_card)
        self._content_layout.addLayout(resource_row)

        # ── Conditional Row: Swap, Battery, Environment (same style as CPU/GPU, RAM/Disk) ──
        cond_row_widget = QWidget()
        cond_row = QHBoxLayout(cond_row_widget)
        cond_row.setSpacing(16)
        cond_row.setContentsMargins(0, 0, 0, 0)

        swap_card = QFrame()
        swap_card.setObjectName("card")
        swap_card.hide()
        swap_layout = QVBoxLayout(swap_card)
        swap_title = QLabel("Swap")
        swap_title.setObjectName("tool_title")
        swap_layout.addWidget(swap_title)
        self._swap_bar = QProgressBar()
        self._swap_bar.setFixedHeight(8)
        self._swap_bar.setTextVisible(False)
        self._swap_bar.setObjectName("resource_bar")
        swap_layout.addWidget(self._swap_bar)
        self._swap_label = QLabel("— / —")
        self._swap_label.setObjectName("card_title")
        swap_layout.addWidget(self._swap_label)
        swap_layout.addStretch()
        self._swap_card = swap_card
        cond_row.addWidget(swap_card, 1)

        battery_card = QFrame()
        battery_card.setObjectName("card")
        battery_card.hide()
        battery_layout = QVBoxLayout(battery_card)
        battery_title = QLabel("Battery")
        battery_title.setObjectName("tool_title")
        battery_layout.addWidget(battery_title)
        self._battery_label = QLabel("—")
        self._battery_label.setObjectName("card_title")
        self._battery_label.setWordWrap(True)
        battery_layout.addWidget(self._battery_label)
        battery_layout.addStretch()
        self._battery_card = battery_card
        cond_row.addWidget(battery_card, 1)

        env_card = QFrame()
        env_card.setObjectName("card")
        env_layout = QVBoxLayout(env_card)
        env_title = QLabel("Environment")
        env_title.setObjectName("tool_title")
        env_layout.addWidget(env_title)
        self._env_grid = QGridLayout()
        self._env_grid.setSpacing(8)
        self._env_grid.setColumnMinimumWidth(0, 100)
        self._env_widgets = {}  # key -> (lbl, val) for conditional show
        for row, (label, key) in enumerate([
            ("Audio", "audio_server"),
            ("CPU Temp", "cpu_temp"),
            ("IP Address", "primary_ip"),
        ]):
            lbl = QLabel(label)
            lbl.setObjectName("card_detail")
            val = QLabel("—")
            val.setObjectName("card_title")
            val.setWordWrap(True)
            self._env_grid.addWidget(lbl, row, 0)
            self._env_grid.addWidget(val, row, 1)
            self._env_widgets[key] = (lbl, val)
        env_layout.addLayout(self._env_grid)
        env_layout.addStretch()
        self._env_card = env_card
        cond_row.addWidget(env_card, 1)

        self._cond_row_widget = cond_row_widget
        self._content_layout.addWidget(cond_row_widget)

        # ── Package Stats Row ──
        pkg_row = QHBoxLayout()
        pkg_row.setSpacing(16)

        rpm_card = self._create_count_card("RPM Packages", "0")
        self._rpm_count = rpm_card._value_label
        pkg_row.addWidget(rpm_card, 1)

        flatpak_card = self._create_count_card("Flatpak Apps", "0")
        self._flatpak_count = flatpak_card._value_label
        pkg_row.addWidget(flatpak_card, 1)

        self._content_layout.addLayout(pkg_row)

        self._content_layout.addStretch()
        scroll.setWidget(scroll_content)
        body_layout.addWidget(scroll, 1)

    def _create_count_card(self, title: str, value: str) -> QFrame:
        """Create a count card matching the style/size of other cards (CPU, GPU, RAM, Disk)."""
        card = QFrame()
        card.setObjectName("card")

        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(4)

        title_label = QLabel(f"{title}")
        title_label.setObjectName("tool_title")
        card_layout.addWidget(title_label)

        val_label = QLabel(value)
        val_label.setObjectName("stats_number")
        card_layout.addWidget(val_label)
        card_layout.addStretch()

        card._value_label = val_label
        return card

    def set_loading(self, loading: bool):
        """No-op: loading is indicated by progress bar only."""
        pass

    def display_info(self, info):
        """Display system information from a SystemInfo object."""
        # OS fields
        for key, widget in self._os_fields.items():
            val = getattr(info, key, None)
            if key in self._os_optional_rows:
                lbl, val_w = self._os_optional_rows[key]
                if val is None or val == "":
                    lbl.hide()
                    val_w.hide()
                else:
                    lbl.show()
                    val_w.show()
                    val_w.setText(str(val))
            else:
                widget.setText(str(val) if val else "—")

        # CPU
        self._cpu_model.setText(info.cpu_model or "Unknown")
        self._cpu_cores.setText(f"{info.cpu_cores} threads" if info.cpu_cores else "")

        # GPU
        self._gpu_model.setText(info.gpu or "Not detected")

        # RAM
        self._ram_bar.setValue(int(info.ram_percent))
        self._ram_label.setText(f"{info.ram_used} / {info.ram_total}")
        self._ram_percent.setText(f"{info.ram_percent:.1f}% used")

        # Disk
        self._disk_bar.setValue(int(info.disk_percent))
        self._disk_label.setText(f"{info.disk_used} / {info.disk_total}")
        self._disk_free_label.setText(f"{info.disk_free} free ({info.disk_percent:.1f}% used)")

        # Swap (conditional)
        swap_visible = bool(info.swap_total)
        if swap_visible:
            self._swap_card.show()
            self._swap_bar.setValue(int(info.swap_percent))
            self._swap_label.setText(f"{info.swap_used} / {info.swap_total} ({info.swap_percent:.1f}% used)")
        else:
            self._swap_card.hide()

        # Battery (conditional: laptops only)
        battery_visible = info.battery_percent is not None or info.battery_status
        if battery_visible:
            self._battery_card.show()
            parts = []
            if info.battery_percent is not None:
                parts.append(f"{info.battery_percent}%")
            if info.battery_status:
                parts.append(info.battery_status)
            if info.battery_time and info.battery_time != "—":
                parts.append(f"{info.battery_time} remaining")
            self._battery_label.setText(" · ".join(parts))
        else:
            self._battery_card.hide()

        # Environment (conditional: show card only if any field has data)
        env_has_any = False
        for key, (lbl, val_w) in self._env_widgets.items():
            val = getattr(info, key, None)
            if val:
                lbl.show()
                val_w.show()
                val_w.setText(str(val))
                env_has_any = True
            else:
                lbl.hide()
                val_w.hide()
        self._env_card.setVisible(env_has_any)

        # Hide entire conditional row when nothing to show
        self._cond_row_widget.setVisible(swap_visible or battery_visible or env_has_any)

        # Package counts
        self._rpm_count.setText(str(info.package_count))
        self._flatpak_count.setText(str(info.flatpak_count))
