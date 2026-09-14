"""Settings page — Discover takeover, update reminders, combined updates."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QCheckBox, QComboBox, QSizePolicy
)
from PyQt6.QtCore import pyqtSignal, Qt


def _section_header(title: str, description: str = "") -> QWidget:
    header = QWidget()
    layout = QVBoxLayout(header)
    layout.setContentsMargins(0, 12, 0, 4)
    layout.setSpacing(3)
    title_lbl = QLabel(title)
    title_lbl.setObjectName("section_label")
    layout.addWidget(title_lbl)
    if description:
        desc_lbl = QLabel(description)
        desc_lbl.setObjectName("hint")
        desc_lbl.setWordWrap(True)
        layout.addWidget(desc_lbl)
    return header


class _Card(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(20, 18, 20, 18)
        self._layout.setSpacing(14)

    def add_row(self, widget) -> None:
        if isinstance(widget, QWidget):
            self._layout.addWidget(widget)
        else:
            self._layout.addLayout(widget)

    def add_button_row(self, *buttons) -> None:
        row = QHBoxLayout()
        row.setSpacing(10)
        for btn in buttons:
            row.addWidget(btn)
        row.addStretch()
        self._layout.addLayout(row)


def _make_button(text: str, style: str = "primary_button") -> QPushButton:
    btn = QPushButton(text)
    btn.setObjectName(style)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    return btn


def _hint(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("hint")
    lbl.setWordWrap(True)
    return lbl


def _caption(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("caption")
    return lbl


class SettingsPage(QWidget):
    """Central place for Discover control + reminder preferences."""

    # Discover
    discover_refresh_requested = pyqtSignal()
    discover_takeover_requested = pyqtSignal()   # per-user disable
    discover_restore_requested = pyqtSignal()    # per-user re-enable
    discover_system_disable_requested = pyqtSignal()
    discover_system_enable_requested = pyqtSignal()
    discover_kill_requested = pyqtSignal()
    discover_remove_notifier_requested = pyqtSignal()
    # Reminders
    reminders_save_requested = pyqtSignal(dict)
    reminders_test_requested = pyqtSignal()
    checker_toggle_requested = pyqtSignal(bool)
    # Passwordless updates
    passwordless_enable_requested = pyqtSignal(str)  # scope
    passwordless_disable_requested = pyqtSignal()
    passwordless_refresh_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        from dnf_gui.ui.widgets.page_header import PageHeader
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Header (own left inset, closer to the sidebar) ──
        layout.addWidget(PageHeader(
            "Settings",
            "Take over updates from Discover, and get reminded about security updates"))

        # ── Body ──
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(20, 0, 20, 20)
        body_layout.setSpacing(20)
        layout.addWidget(body, 1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content_w = QWidget()
        content = QVBoxLayout(content_w)
        content.setContentsMargins(0, 0, 16, 0)
        content.setSpacing(24)

        # ── Discover Update Checks ──
        content.addWidget(_section_header(
            "Discover Update Checks",
            "Fedora KDE comes with Discover, which checks for updates in the background. "
            "Hand updates over to this app to avoid duplicate notifications and unwanted restart-time updates."
        ))
        disc_card = _Card()

        # Status banner: tinted frame with headline + detail line.
        banner = QFrame()
        banner.setObjectName("status_info")
        banner_layout = QVBoxLayout(banner)
        banner_layout.setContentsMargins(16, 12, 16, 12)
        banner_layout.setSpacing(4)
        self._discover_title = QLabel("Checking Discover status...")
        self._discover_title.setObjectName("status_title")
        self._discover_title.setWordWrap(True)
        banner_layout.addWidget(self._discover_title)
        self._discover_status = QLabel("Click Refresh to inspect Discover's state.")
        self._discover_status.setObjectName("status_detail")
        self._discover_status.setWordWrap(True)
        banner_layout.addWidget(self._discover_status)
        disc_card.add_row(banner)
        self._discover_banner = banner

        # Contextual actions in one clean row
        self._btn_takeover = _make_button("Use This App Instead", "primary_button")
        self._btn_takeover.setToolTip(
            "Stop Discover's automatic checks for your user. Safe and reversible, no password needed.")
        self._btn_takeover.clicked.connect(self.discover_takeover_requested.emit)
        self._btn_restore = _make_button("Restore Discover", "ghost_button")
        self._btn_restore.setToolTip(
            "Let Discover check for updates again.")
        self._btn_restore.clicked.connect(self.discover_restore_requested.emit)
        self._btn_disc_refresh = _make_button("Refresh", "ghost_button")
        self._btn_disc_refresh.clicked.connect(self.discover_refresh_requested.emit)

        # Advanced options disclosure toggle
        self._btn_disc_advanced = _make_button("Advanced Options", "ghost_button")
        self._btn_disc_advanced.setProperty("compact", True)
        self._btn_disc_advanced.setCheckable(True)
        self._btn_disc_advanced.setChecked(False)
        self._btn_disc_advanced.toggled.connect(self._toggle_disc_advanced)
        disc_card.add_button_row(
            self._btn_takeover, self._btn_restore, self._btn_disc_refresh, self._btn_disc_advanced)

        # Advanced options container
        self._disc_advanced = QWidget()
        adv_layout = QVBoxLayout(self._disc_advanced)
        adv_layout.setContentsMargins(14, 12, 14, 12)
        adv_layout.setSpacing(10)
        adv_layout.addWidget(_hint(
            "These options apply to every user on this PC and require administrative privileges. "
            "Most users never need them."
        ))
        adv_layout.addWidget(_caption("System-Wide Policies"))
        adv_row1 = QHBoxLayout()
        adv_row1.setSpacing(10)
        self._btn_sys_disable = _make_button("Turn Off for All Users", "danger_button")
        self._btn_sys_disable.setToolTip(
            "Remove Discover's autostart entry and stop reboot-time updates system wide.")
        self._btn_sys_disable.clicked.connect(self.discover_system_disable_requested.emit)
        adv_row1.addWidget(self._btn_sys_disable)
        self._btn_sys_enable = _make_button("Turn Back On", "ghost_button")
        self._btn_sys_enable.clicked.connect(self.discover_system_enable_requested.emit)
        adv_row1.addWidget(self._btn_sys_enable)
        adv_row1.addStretch()
        adv_layout.addLayout(adv_row1)

        adv_layout.addWidget(_caption("Process Control"))
        adv_row2 = QHBoxLayout()
        adv_row2.setSpacing(10)
        self._btn_kill = _make_button("Stop Checker Now", "ghost_button")
        self._btn_kill.setToolTip(
            "Stop Discover's background checker until your next login.")
        self._btn_kill.clicked.connect(self.discover_kill_requested.emit)
        adv_row2.addWidget(self._btn_kill)
        self._btn_remove_notifier = _make_button("Uninstall Checker", "danger_button")
        self._btn_remove_notifier.setToolTip(
            "Uninstall the Discover update checker package. Discover itself stays installed.")
        self._btn_remove_notifier.clicked.connect(
            self.discover_remove_notifier_requested.emit)
        adv_row2.addWidget(self._btn_remove_notifier)
        adv_row2.addStretch()
        adv_layout.addLayout(adv_row2)
        self._disc_advanced.hide()
        disc_card.add_row(self._disc_advanced)
        content.addWidget(disc_card)

        # ── Update Reminders ──
        content.addWidget(_section_header(
            "Update Reminders",
            "Configure background desktop notifications for pending package and security updates."
        ))
        rem_card = _Card()
        rem_card._layout.setSpacing(12)

        self._rem_enabled = QCheckBox("Remind Me About Pending Updates")
        self._rem_enabled.setStyleSheet("font-weight: 600;")
        self._rem_enabled.toggled.connect(self._on_rem_enabled_toggled)
        rem_card.add_row(self._rem_enabled)

        # Indented secondary options
        self._child_options = QWidget()
        child_layout = QVBoxLayout(self._child_options)
        child_layout.setContentsMargins(24, 0, 0, 0)
        child_layout.setSpacing(10)

        self._rem_security_only = QCheckBox("Security Updates Only (Quiet for Routine RPMs)")
        self._rem_flatpak = QCheckBox("Include Flatpak Updates in Reminders")
        self._rem_flatpak.setChecked(True)

        child_layout.addWidget(self._rem_security_only)
        child_layout.addWidget(self._rem_flatpak)
        rem_card.add_row(self._child_options)

        interval_row = QHBoxLayout()
        interval_row.setSpacing(10)
        interval_row.addWidget(QLabel("Check Every:"))
        self._interval_combo = QComboBox()
        self._interval_combo.setFixedWidth(200)
        self._interval_combo.addItem("12 Hours", 12)
        self._interval_combo.addItem("Daily", 24)
        self._interval_combo.addItem("Every 3 Days", 72)
        self._interval_combo.addItem("Weekly", 168)
        interval_row.addWidget(self._interval_combo)
        interval_row.addStretch()
        rem_card._layout.addLayout(interval_row)

        self._rem_last = _hint("Background checks have never run.")
        rem_card.add_row(self._rem_last)

        self._btn_rem_save = _make_button("Save Reminder Settings", "primary_button")
        self._btn_rem_save.clicked.connect(self._emit_save)
        self._btn_rem_test = _make_button("Send Test Notification", "ghost_button")
        self._btn_rem_test.clicked.connect(self.reminders_test_requested.emit)
        rem_card.add_button_row(self._btn_rem_save, self._btn_rem_test)

        rem_card.add_row(_hint(
            "When enabled, reminders automatically run in the background at login and "
            "on your chosen schedule, notifying only when updates are ready. "
            "Flatpak updates notify independently even when Security Updates Only is active."
        ))
        content.addWidget(rem_card)

        # ── Password Prompts ──
        content.addWidget(_section_header(
            "Password Prompts",
            "Grant permission for routine package updates so they run seamlessly without repeated password prompts."
        ))
        pw_card = _Card()
        pw_card._layout.setSpacing(14)

        pw_status_frame = QFrame()
        pw_status_frame.setObjectName("status_info")
        pw_status_layout = QVBoxLayout(pw_status_frame)
        pw_status_layout.setContentsMargins(14, 10, 14, 10)
        pw_status_layout.setSpacing(4)
        self._pw_status = QLabel("Passwordless updates: off.")
        self._pw_status.setObjectName("status_title")
        self._pw_status.setWordWrap(True)
        pw_status_layout.addWidget(self._pw_status)
        pw_card.add_row(pw_status_frame)

        pw_card.add_row(_hint(
            "'Updates only' (recommended) makes  passwordless, so "
            "daily updates just run. Installs, removals, repo changes and "
            "firmware updates still ask for your password. 'All DNF operations' "
            "removes every prompt but lets any program running as you change "
            "system packages. Only use it on a single-user desktop. "
            "Enabling asks for your password once to install a validated "
            "sudoers file (/etc/sudoers.d/90-dnf-gui); disabling restores "
            "prompts immediately."
        ))

        scope_row = QHBoxLayout()
        scope_row.setSpacing(10)
        scope_row.addWidget(QLabel("Privilege Scope:"))
        self._pw_scope_combo = QComboBox()
        self._pw_scope_combo.setFixedWidth(260)
        self._pw_scope_combo.addItem("Updates Only (Recommended)", "updates")
        self._pw_scope_combo.addItem("All DNF Operations", "full")
        scope_row.addWidget(self._pw_scope_combo)
        scope_row.addStretch()
        pw_card._layout.addLayout(scope_row)

        self._btn_pw_enable = _make_button("Enable Passwordless", "primary_button")
        self._btn_pw_enable.clicked.connect(
            lambda: self.passwordless_enable_requested.emit(
                self._pw_scope_combo.currentData()))
        self._btn_pw_disable = _make_button("Disable (Restore Prompts)", "ghost_button")
        self._btn_pw_disable.clicked.connect(self.passwordless_disable_requested.emit)
        self._btn_pw_refresh = _make_button("Refresh", "ghost_button")
        self._btn_pw_refresh.clicked.connect(self.passwordless_refresh_requested.emit)
        pw_card.add_button_row(
            self._btn_pw_enable, self._btn_pw_disable, self._btn_pw_refresh)
        content.addWidget(pw_card)

        content.addStretch()
        scroll.setWidget(content_w)
        body_layout.addWidget(scroll, 1)

    # ─── Slots called by MainWindow ─────────────────────────────

    def _toggle_disc_advanced(self, checked: bool) -> None:
        """Show/hide the advanced Discover options."""
        self._disc_advanced.setVisible(checked)
        self._btn_disc_advanced.setText(
            "Hide Advanced Options" if checked else "Advanced Options")

    def _emit_save(self):
        self.reminders_save_requested.emit({
            "enabled": self._rem_enabled.isChecked(),
            "security_only": self._rem_security_only.isChecked(),
            "notify_flatpak": self._rem_flatpak.isChecked(),
            "interval_hours": self._interval_combo.currentData(),
        })

    def _on_rem_enabled_toggled(self, checked: bool) -> None:
        """Enable or disable reminder sub-options with the master toggle."""
        self._child_options.setEnabled(checked)
        self._interval_combo.setEnabled(checked)

    def load_reminder_settings(self, prefs: dict, checker_installed: bool = False,
                               last_check: str = "") -> None:
        enabled = bool(prefs.get("enabled", False))
        self._rem_enabled.setChecked(enabled)
        self._rem_security_only.setChecked(bool(prefs.get("security_only", False)))
        self._rem_flatpak.setChecked(bool(prefs.get("notify_flatpak", True)))
        interval = int(prefs.get("interval_hours", 24))
        for i in range(self._interval_combo.count()):
            if self._interval_combo.itemData(i) == interval:
                self._interval_combo.setCurrentIndex(i)
                break
        self._child_options.setEnabled(enabled)
        self._interval_combo.setEnabled(enabled)
        self._rem_last.setText(
            f"Last background check: {last_check}" if last_check
            else "Background checks have never run."
        )

    def display_passwordless_status(self, remembered: str, live: str) -> None:
        """Show remembered preference vs what's actually in effect."""
        if live == "off" and remembered == "off":
            text = ("• Passwordless updates are off. "
                    "Every privileged step asks for your password.")
        elif live == remembered and live != "off":
            text = (f"• Passwordless updates are on ({live}). "
                    "Verified working, updates run without a prompt.")
        elif live == "off":
            text = (f"• Passwordless updates are set to {remembered} but are "
                    "not working. The system rule is missing, so enable it "
                    "again below.")
        else:
            text = (f"• Passwordless updates: {live} is active "
                    f"(your setting: {remembered}).")
        self._pw_status.setText(text)
        for i in range(self._pw_scope_combo.count()):
            if self._pw_scope_combo.itemData(i) == (remembered if remembered != "off" else "updates"):
                self._pw_scope_combo.setCurrentIndex(i)
                break

    def display_discover_status(self, status) -> None:
        """Show a banner + one contextual action, in plain language."""
        nothing_to_do = (not status.discover_installed
                         and not status.system_autostart_present)
        active = (status.per_user_disabled
                  or (status.discover_installed
                      and not status.system_autostart_present))

        extras = []
        if status.notifier_running:
            extras.append("Its background checker is running right now.")
        if status.packagekit_offline_active:
            extras.append("It may also install updates when you restart.")
        extra = (" " + " ".join(extras)) if extras else ""

        if nothing_to_do:
            variant = "status_info"
            title = "Discover isn't installed."
            detail = "Nothing to turn off."
        elif active:
            variant = "status_ok"
            title = "This app handles updates."
            detail = ("Discover's automatic checks are off." + extra) if extra \
                else "Discover's automatic checks are off."
        else:
            variant = "status_warn"
            title = "Discover is checking for updates too."
            detail = ("You may see double notifications." + extra) if extra \
                else "You may see double notifications."

        self._discover_banner.setObjectName(variant)
        self._discover_banner.style().unpolish(self._discover_banner)
        self._discover_banner.style().polish(self._discover_banner)
        self._discover_title.setText(title)
        self._discover_status.setText(detail)

        self._btn_takeover.setVisible(not active and not nothing_to_do)
        self._btn_restore.setVisible(active and not nothing_to_do)
