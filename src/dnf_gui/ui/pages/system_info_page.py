"""System info page — hardware specs, OS details, and resource monitor."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QFrame, QGridLayout, QProgressBar, QPushButton,
)
from PyQt6.QtCore import Qt, pyqtSignal

from dnf_gui.core.system_info import SystemInfo


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
        refresh_btn.setObjectName("ghost_button")
        refresh_btn.setProperty("compact", True)
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.clicked.connect(self.refresh_clicked.emit)

        # ── Header ──
        layout.addWidget(PageHeader(
            "System Information", "Hardware Specifications and System Health",
            action=refresh_btn))

        # ── Body ──
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(16, 0, 16, 16)
        body_layout.setSpacing(16)
        layout.addWidget(body, 1)

        # ── Scrollable Content ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        scroll_content = QWidget()
        self._content_layout = QVBoxLayout(scroll_content)
        self._content_layout.setContentsMargins(0, 0, 16, 0)
        self._content_layout.setSpacing(14)

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
            ("Desktop Environment", "desktop_env", False),
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

        cpu_title = QLabel("Processor (CPU)")
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

        gpu_title = QLabel("Graphics (GPU)")
        gpu_title.setObjectName("tool_title")
        gpu_layout.addWidget(gpu_title)

        self._gpu_model = QLabel("—")
        self._gpu_model.setObjectName("card_title")
        self._gpu_model.setWordWrap(True)
        gpu_layout.addWidget(self._gpu_model)
        gpu_layout.addStretch()

        hw_row.addWidget(gpu_card)

        self._content_layout.addLayout(hw_row)

        # ── Resources Row ──
        res_row = QHBoxLayout()
        res_row.setSpacing(16)

        # RAM Card
        ram_card = QFrame()
        ram_card.setObjectName("card")
        ram_layout = QVBoxLayout(ram_card)

        ram_title = QLabel("Memory (RAM)")
        ram_title.setObjectName("tool_title")
        ram_layout.addWidget(ram_title)

        self._ram_text = QLabel("—")
        self._ram_text.setObjectName("card_title")
        ram_layout.addWidget(self._ram_text)

        self._ram_bar = QProgressBar()
        self._ram_bar.setObjectName("resource_bar")
        self._ram_bar.setTextVisible(False)
        self._ram_bar.setRange(0, 100)
        ram_layout.addWidget(self._ram_bar)

        self._ram_detail = QLabel("")
        self._ram_detail.setObjectName("card_detail")
        ram_layout.addWidget(self._ram_detail)

        res_row.addWidget(ram_card)

        # Disk Card
        disk_card = QFrame()
        disk_card.setObjectName("card")
        disk_layout = QVBoxLayout(disk_card)

        disk_title = QLabel("Storage (Root /)")
        disk_title.setObjectName("tool_title")
        disk_layout.addWidget(disk_title)

        self._disk_text = QLabel("—")
        self._disk_text.setObjectName("card_title")
        disk_layout.addWidget(self._disk_text)

        self._disk_bar = QProgressBar()
        self._disk_bar.setObjectName("resource_bar")
        self._disk_bar.setTextVisible(False)
        self._disk_bar.setRange(0, 100)
        disk_layout.addWidget(self._disk_bar)

        self._disk_detail = QLabel("")
        self._disk_detail.setObjectName("card_detail")
        disk_layout.addWidget(self._disk_detail)

        res_row.addWidget(disk_card)

        self._content_layout.addLayout(res_row)

        # ── Extended Resources Row ──
        self._ext_res_row = QHBoxLayout()
        self._ext_res_row.setSpacing(16)

        # Swap Card (conditional)
        self._swap_card = QFrame()
        self._swap_card.setObjectName("card")
        swap_layout = QVBoxLayout(self._swap_card)
        swap_title = QLabel("Swap Space")
        swap_title.setObjectName("tool_title")
        swap_layout.addWidget(swap_title)
        self._swap_text = QLabel("—")
        self._swap_text.setObjectName("card_title")
        swap_layout.addWidget(self._swap_text)
        self._swap_bar = QProgressBar()
        self._swap_bar.setObjectName("resource_bar")
        self._swap_bar.setTextVisible(False)
        self._swap_bar.setRange(0, 100)
        swap_layout.addWidget(self._swap_bar)
        self._swap_detail = QLabel("")
        self._swap_detail.setObjectName("card_detail")
        swap_layout.addWidget(self._swap_detail)
        self._ext_res_row.addWidget(self._swap_card)

        # Battery Card (conditional)
        self._battery_card = QFrame()
        self._battery_card.setObjectName("card")
        bat_layout = QVBoxLayout(self._battery_card)
        bat_title = QLabel("Battery")
        bat_title.setObjectName("tool_title")
        bat_layout.addWidget(bat_title)
        self._battery_text = QLabel("—")
        self._battery_text.setObjectName("card_title")
        bat_layout.addWidget(self._battery_text)
        self._battery_bar = QProgressBar()
        self._battery_bar.setObjectName("resource_bar")
        self._battery_bar.setTextVisible(False)
        self._battery_bar.setRange(0, 100)
        bat_layout.addWidget(self._battery_bar)
        self._battery_detail = QLabel("")
        self._battery_detail.setObjectName("card_detail")
        bat_layout.addWidget(self._battery_detail)
        self._ext_res_row.addWidget(self._battery_card)

        self._content_layout.addLayout(self._ext_res_row)
        self._swap_card.hide()
        self._battery_card.hide()

        # ── System Environment Card ──
        self._env_card = QFrame()
        self._env_card.setObjectName("card")
        env_layout = QVBoxLayout(self._env_card)

        env_title = QLabel("Environment & Sensors")
        env_title.setObjectName("tool_title")
        env_layout.addWidget(env_title)

        self._env_grid = QGridLayout()
        self._env_grid.setSpacing(8)
        self._env_grid.setColumnMinimumWidth(0, 150)

        self._env_fields = {}
        env_items = [
            ("Audio Server", "audio_server"),
            ("CPU Temperature", "cpu_temp"),
            ("Primary IP Address", "primary_ip"),
        ]
        for row, (label, key) in enumerate(env_items):
            lbl = QLabel(label)
            lbl.setObjectName("card_detail")
            val = QLabel("—")
            val.setObjectName("card_title")
            val.setWordWrap(True)
            self._env_grid.addWidget(lbl, row, 0)
            self._env_grid.addWidget(val, row, 1)
            self._env_fields[key] = (lbl, val)

        env_layout.addLayout(self._env_grid)
        self._content_layout.addWidget(self._env_card)
        self._env_card.hide()

        # ── Package Counts Card ──
        pkg_card = QFrame()
        pkg_card.setObjectName("card")
        pkg_layout = QHBoxLayout(pkg_card)
        pkg_layout.setContentsMargins(16, 12, 16, 12)

        self._pkg_count = QLabel("Installed Packages: —")
        self._pkg_count.setObjectName("card_title")
        pkg_layout.addWidget(self._pkg_count)

        self._flatpak_count = QLabel("Flatpak Applications: —")
        self._flatpak_count.setObjectName("card_title")
        pkg_layout.addWidget(self._flatpak_count)

        self._content_layout.addWidget(pkg_card)

        self._content_layout.addStretch()
        scroll.setWidget(scroll_content)
        body_layout.addWidget(scroll, 1)

    def display_info(self, info: SystemInfo):
        """Display gathered system information."""
        # OS Grid
        for key, val_label in self._os_fields.items():
            val = getattr(info, key, "")
            if val:
                val_label.setText(str(val))
            else:
                val_label.setText("—")

        # Optional OS rows: hide if None
        for key, (lbl, val) in self._os_optional_rows.items():
            present = getattr(info, key, None) is not None
            lbl.setVisible(present)
            val.setVisible(present)

        # CPU
        if info.cpu_model:
            self._cpu_model.setText(info.cpu_model)
        if info.cpu_cores:
            self._cpu_cores.setText(f"{info.cpu_cores} Cores / Threads")

        # GPU
        if info.gpu:
            self._gpu_model.setText(info.gpu)

        # RAM
        if info.ram_used and info.ram_total:
            self._ram_text.setText(f"{info.ram_used} / {info.ram_total}")
            self._ram_bar.setValue(int(info.ram_percent))
            self._ram_detail.setText(f"{info.ram_percent:.1f}% in use")

        # Disk
        if info.disk_used and info.disk_total:
            self._disk_text.setText(f"{info.disk_used} / {info.disk_total}")
            self._disk_bar.setValue(int(info.disk_percent))
            detail = f"{info.disk_percent:.1f}% used"
            if info.disk_free:
                detail += f" ({info.disk_free} free)"
            self._disk_detail.setText(detail)

        # Swap (conditional)
        if info.swap_total and info.swap_total != "0 B":
            self._swap_card.show()
            self._swap_text.setText(f"{info.swap_used} / {info.swap_total}")
            self._swap_bar.setValue(int(info.swap_percent))
            self._swap_detail.setText(f"{info.swap_percent:.1f}% used")
        else:
            self._swap_card.hide()

        # Battery (conditional)
        if info.battery_percent is not None:
            self._battery_card.show()
            self._battery_text.setText(f"{info.battery_percent}%")
            self._battery_bar.setValue(info.battery_percent)
            parts = []
            if info.battery_status:
                parts.append(info.battery_status)
            if info.battery_time:
                parts.append(info.battery_time)
            self._battery_detail.setText(" · ".join(parts))
        else:
            self._battery_card.hide()

        # Environment & Sensors (conditional)
        env_visible_count = 0
        for key, (lbl, val) in self._env_fields.items():
            attr = getattr(info, key, None)
            if attr:
                val.setText(str(attr))
                lbl.show()
                val.show()
                env_visible_count += 1
            else:
                lbl.hide()
                val.hide()
        self._env_card.setVisible(env_visible_count > 0)

        # Package counts
        if info.package_count:
            self._pkg_count.setText(f"Installed RPM Packages: {info.package_count}")
        if info.flatpak_count is not None:
            self._flatpak_count.setText(f"Flatpak Applications: {info.flatpak_count}")

    def set_loading(self, loading: bool = True):
        """Show loading placeholder."""
        for val_label in self._os_fields.values():
            val_label.setText("Loading...")
        self._cpu_model.setText("Loading...")
        self._gpu_model.setText("Loading...")
        self._ram_text.setText("Loading...")
        self._disk_text.setText("Loading...")
