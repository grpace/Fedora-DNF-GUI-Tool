"""Updates page: scan results, the update modes, holds, release upgrades."""

from __future__ import annotations

from datetime import date

from PyQt6.QtCore import QObject, QUrl, pyqtProperty, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QDesktopServices

from dnf_gui.core import release_upgrade
from dnf_gui.core.app_settings import UPDATE_MODE_KEYS
from dnf_gui.core.dnf_backend import DEFAULT_HELD_BACK_PATTERNS, is_held_back
from dnf_gui.core.release_upgrade import RELEASE_NOTES_URL, UPGRADE_DOCS_URL
from dnf_gui.core.security import (
    build_forced_security_update_command, build_security_update_command,
)
from dnf_gui.core.worker import CallWorker, CombinedUpdateCheckWorker, RebootCheckWorker
from dnf_gui.ui.controllers.base import FilterModel, RowModel, StateObject, state_property

# (key, title, description) — v1's split-button modes, same keys in settings.
UPDATE_MODES = (
    ("all", "Upgrade All", "Every system package (dnf upgrade)"),
    ("everything", "Update Everything", "System packages, then all Flatpak apps"),
    ("minor", "Update Without Core",
     "Skips core updates: kernel, graphics drivers, firmware, bootloader"),
    ("security", "Security Only", "Only packages with security advisories"),
)
assert tuple(k for k, _, _ in UPDATE_MODES) == tuple(UPDATE_MODE_KEYS)

GROUPS = {  # key: (rank, section title)
    "security": (0, "Security Fixes"),
    "major": (1, "Core Updates"),
    "other": (2, "Other Updates"),
    "flatpak": (3, "Flatpak Apps"),
}
ROLES = ("name", "kind", "group", "section", "fromVersion", "toVersion", "arch",
         "repo", "size", "severity", "security", "waiting", "major",
         "majorReason", "canToggleMajor", "majorActionLabel", "majorTooltip",
         "appId", "branch", "iconName", "tooltip")


def _format_day(iso_day: str) -> str:
    """ISO day such as 2027-06-02 as "June 2, 2027" ('' if invalid)."""
    try:
        day = date.fromisoformat(iso_day)
    except (TypeError, ValueError):
        return ""
    return f"{day:%B} {day.day}, {day.year}"


def _format_checked(raw) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    day = text.split(" ")[0] if (" " in text and "-" in text) else text
    return "today" if day == date.today().isoformat() else day


def _plural(n: int, one: str, many: str | None = None) -> str:
    return f"{n} {one if n == 1 else (many or one + 's')}"


def _size_text(n: int | None) -> str:
    if not n:
        return ""
    from dnf_gui.utils.helpers import format_size
    return format_size(n)


def _category(row: dict, category: str) -> bool:
    if category == "security":
        return bool(row["security"])
    if category == "major":
        return bool(row["major"])
    if category == "flatpak":
        return row["kind"] == "flatpak"
    return True


class UpdatesController(StateObject):
    changed = pyqtSignal()
    _defaults = {
        "phase": "idle",  # idle | checking | ready | uptodate | failed
        "headline": "",
        "summary": "",
        "lastChecked": "",
        "dnfCount": 0,
        "flatpakCount": 0,
        "total": 0,
        "securityTotal": 0,
        "securityWaiting": 0,
        "favorite": "all",
        "modes": [],
        "rebootRequired": False,
        "release": {},
        "blocked": {},
        "majorCount": 0,
        "mainMode": "everything",
        "rebootCertain": True,
    }

    phase = state_property(str, "phase", changed)
    headline = state_property(str, "headline", changed)
    summary = state_property(str, "summary", changed)
    lastChecked = state_property(str, "lastChecked", changed)
    dnfCount = state_property(int, "dnfCount", changed)
    flatpakCount = state_property(int, "flatpakCount", changed)
    total = state_property(int, "total", changed)
    securityTotal = state_property(int, "securityTotal", changed)
    securityWaiting = state_property(int, "securityWaiting", changed)
    favorite = state_property(str, "favorite", changed)
    modes = state_property("QVariantList", "modes", changed)
    rebootRequired = state_property(bool, "rebootRequired", changed)
    release = state_property("QVariantMap", "release", changed)
    blocked = state_property("QVariantMap", "blocked", changed)
    majorCount = state_property(int, "majorCount", changed)
    mainMode = state_property(str, "mainMode", changed)
    rebootCertain = state_property(bool, "rebootCertain", changed)

    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self._model = RowModel(ROLES, self)
        self._filtered = FilterModel(
            self._model, ("name", "repo", "appId"), _category, self)
        self._info = None          # core.package.UpdateInfo
        self._flatpaks: list = []
        self._security = None      # core.security.SecuritySummary
        self.upgrade_preview = None
        self.security_preview = None
        self._release_upgrade = None
        self._reboot_dismissed = False
        self._cache: dict | None = None  # last good scan; revisits reuse it
        self._check_worker = None
        self._held_back = list(app.settings.held_back_patterns)
        self._state["favorite"] = app.settings.update_favorite
        self._refresh_modes()

    @pyqtProperty(QObject, constant=True)
    def model(self) -> RowModel:
        return self._model

    @pyqtProperty(QObject, constant=True)
    def filtered(self) -> FilterModel:
        return self._filtered

    @pyqtSlot(str, str, result=bool)
    def flatpakHasUpdate(self, app_id: str, branch: str) -> bool:
        """Whether this installed Flatpak (app id + branch) has an update."""
        return any(r["kind"] == "flatpak" and r["appId"] == app_id
                   and (not r["branch"] or not branch or r["branch"] == branch)
                   for r in self._model._rows)

    @pyqtSlot(str, result="QVariantMap")
    def updateFor(self, name: str) -> dict:
        """The pending update row for ``name`` ({} if none)."""
        return self._model.find("name", name) or {}

    # ── scanning ───────────────────────────────────────────────

    def invalidate(self) -> None:
        """System state changed: the next visit must rescan."""
        self._cache = None

    def show(self) -> None:
        """Page visit: reuse the last scan, or scan if there is none."""
        if self._cache is not None:
            self._apply(self._cache)
        else:
            self.check()

    @pyqtSlot()
    def check(self) -> None:
        running = self._check_worker
        if running is not None and running.isRunning():
            return  # a scan is already on its way
        self._set(phase="checking")
        worker = CombinedUpdateCheckWorker(
            self.app.backend, self.app.flatpak_backend, parent=self)
        worker.finished.connect(self._on_checked)
        worker.error.connect(self._on_check_error)
        self._check_worker = worker
        worker.start()

    def _on_check_error(self, error: str) -> None:
        self._set(phase="failed", headline="Couldn't Check for Updates",
                  summary=error)
        self.app.show_error("Operation Failed", f"An error occurred:\n\n{error}")

    def _on_checked(self, result: dict) -> None:
        info = result.get("dnf")
        self._reboot_dismissed = False  # a fresh scan may need a restart again
        self._apply(result)
        if getattr(info, "check_failed", False):
            self._cache = None  # unknown, not zero: rescan next visit
            return
        self._cache = result
        self.app.set_update_badge(self._state["total"])

    def _apply(self, result: dict) -> None:
        info = result.get("dnf")
        self._info = info
        self._flatpaks = list(result.get("flatpak") or [])
        self._security = result.get("security")
        self.upgrade_preview = result.get("preview")
        self.security_preview = result.get("security_preview")
        self._release_upgrade = result.get("release_upgrade")
        dnf_count = len(info.packages) if info and info.packages else 0
        reboot = result.get("reboot")
        if reboot is not None:
            # A scan that can't tell (None) leaves the banner as it was, so
            # it never clears "a restart may be needed" from the check that
            # ran after an update.
            self.set_reboot_required(bool(reboot))
        self._set(dnfCount=dnf_count, flatpakCount=len(self._flatpaks),
                  total=dnf_count + len(self._flatpaks),
                  securityTotal=self._security.total if self._security else 0,
                  securityWaiting=(len(self._security.blocked_advisories)
                                   if self._security else 0),
                  lastChecked=_format_checked(getattr(info, "last_checked", ""))
                  or "today")
        self._refresh_release()
        self._refresh_blocked()
        self._rebuild()

    # ── rows and summary ───────────────────────────────────────

    def _rebuild(self) -> None:
        info, security = self._info, self._security
        packages = list(info.packages) if info and info.packages else []
        severity = dict(security.package_severity) if security else {}
        blocked = security.blocked if security else None
        sizes = {}
        if self.upgrade_preview is not None:
            sizes = {name: n for name, n in getattr(self.upgrade_preview, "entries", [])}
        rows = []
        seen = set()
        for pkg in packages:
            installed, new = pkg.installed_version or "", pkg.full_version
            # Show epochs on both sides or neither ("3:1.0 → 1.1" reads
            # like a downgrade).
            if installed and (":" in installed) != (":" in new):
                installed = installed.split(":", 1)[-1]
                new = new.split(":", 1)[-1]
            if pkg.name in seen:
                continue
            seen.add(pkg.name)
            major = is_held_back(pkg.name, self._held_back)
            is_security = pkg.name in severity
            waiting = bool(blocked and pkg.name in blocked.packages)
            group = "security" if is_security else ("major" if major else "other")
            label, tip, can_toggle = self._hold_action(pkg.name)
            sev = severity.get(pkg.name, "")
            if is_security:
                tooltip = (f"Fixes a {sev or 'security'} advisory. "
                           + ("Security Only can't install it yet." if waiting
                              else "Included in Security Only."))
            else:
                tooltip = ""
            rows.append({
                "name": pkg.name, "kind": "dnf", "group": group,
                "section": GROUPS[group][1],
                "fromVersion": installed,
                "toVersion": new, "arch": pkg.arch, "repo": pkg.repo,
                "size": _size_text(sizes.get(pkg.name)),
                "severity": sev.title() if sev else ("Security" if is_security else ""),
                "security": is_security, "waiting": waiting, "major": major,
                "majorReason": self._major_reason(pkg.name) if major else "",
                "canToggleMajor": can_toggle, "majorActionLabel": label,
                "majorTooltip": tip, "appId": "", "branch": "", "iconName": "package-x-generic",
                "tooltip": tooltip,
            })
        rows.sort(key=lambda r: (GROUPS[r["group"]][0], r["name"].lower()))
        flatpak_rows = []
        for app in self._flatpaks:
            flatpak_rows.append({
                "name": app.name or app.application_id, "kind": "flatpak",
                "group": "flatpak", "section": GROUPS["flatpak"][1],
                "fromVersion": "", "toVersion": app.version or app.branch,
                "arch": "", "repo": app.origin, "size": app.size or "",
                "severity": "", "security": False, "waiting": False,
                "major": False, "majorReason": "", "canToggleMajor": False,
                "majorActionLabel": "", "majorTooltip": "",
                "appId": app.application_id, "branch": app.branch or "",
                "iconName": app.application_id,
                "tooltip": app.application_id,
            })
        flatpak_rows.sort(key=lambda r: r["name"].lower())
        self._model.set_rows(rows + flatpak_rows)
        self._set(majorCount=sum(r["major"] for r in rows))
        self._refresh_modes()
        self._refresh_summary()

    def _refresh_summary(self) -> None:
        info = self._info
        dnf, flatpak = self._state["dnfCount"], self._state["flatpakCount"]
        total = dnf + flatpak
        if info is not None and getattr(info, "check_failed", False):
            phase = "failed"
            headline = "Couldn't Check for Updates"
            summary = ("dnf couldn't reach the repositories. Check your internet "
                       "connection, then choose Check Again.")
            if flatpak:
                summary += f" {_plural(flatpak, 'Flatpak update')} found."
        elif total == 0:
            phase, headline = "uptodate", "Your System Is Up to Date"
            summary = "No system or Flatpak updates are waiting."
        else:
            phase = "ready"
            headline = f"{_plural(total, 'Update')} Ready"
            parts = []
            sec = self._state["securityTotal"]
            if sec:
                urgent = self._security.critical if self._security else 0
                text = f"{_plural(sec, 'security advisory', 'security advisories')}"
                if urgent:
                    text += f", {urgent} critical"
                parts.append(text + ".")
            what = []
            if dnf:
                what.append(_plural(dnf, "system package"))
            if flatpak:
                what.append(_plural(flatpak, "Flatpak app"))
            line = " and ".join(what)
            download = self._preview_line(self.upgrade_preview)
            if download and "download" in download:
                line += f", {download.split(', ', 1)[1]}"
            parts.append(line[0].upper() + line[1:] + ".")
            waiting = self._state["securityWaiting"]
            if waiting:
                parts.append(f"{_plural(waiting, 'advisory', 'advisories')} "
                             "can't install yet.")
            summary = " ".join(parts)
        self._set(phase=phase, headline=headline, summary=summary)

    def _major_pattern(self, name: str) -> str | None:
        return next((p for p in self._held_back if is_held_back(name, [p])), None)

    def _major_reason(self, name: str) -> str:
        pattern = self._major_pattern(name)
        why = ("You marked this as core." if pattern == name
               else f"Core package (matches “{pattern}”).")
        return (f"{why} Update Without Core skips it; Upgrade All and "
                "Update Everything install it.")

    def _hold_action(self, name: str) -> tuple[str, str, bool]:
        """(label, tooltip, enabled) for the row's Treat as Core action."""
        if name in self._held_back:
            return ("Don't Treat as Core", "Update Without Core will install "
                    "it again.", True)
        pattern = self._major_pattern(name)
        if pattern:
            return ("Don't Treat as Core", f"Counts as core because it matches "
                    f"“{pattern}”. Change the patterns in Settings.", False)
        return ("Treat as Core", "Update Without Core will skip it. Upgrade "
                "All still installs it.", True)

    def _refresh_modes(self) -> None:
        dnf = self._state["dnfCount"]
        flatpak = self._state["flatpakCount"]
        minor = len(self.minor_package_names())
        held = len(self.held_back_package_names())
        installable = self._state["securityTotal"] - self._state["securityWaiting"]
        waiting = self._state["securityWaiting"]
        if waiting and not installable:
            sec_detail = f"Nothing to install yet · {waiting} waiting"
        elif waiting:
            sec_detail = f"{installable} advisories ({waiting} waiting)"
        else:
            sec_detail = _plural(self._state["securityTotal"], "advisory", "advisories")
        state = {
            "all": (dnf > 0, _plural(dnf, "package"), dnf),
            "everything": (dnf + flatpak > 0,
                           f"{_plural(dnf, 'package')} + {flatpak} Flatpak"
                           if flatpak else _plural(dnf, "package"), dnf + flatpak),
            "minor": (minor > 0, f"{_plural(minor, 'package')} (skips {held} core)"
                      if held else _plural(minor, "package"), minor),
            # Stays enabled with waiting advisories: it explains and offers Force.
            "security": (self._state["securityTotal"] > 0, sec_detail,
                         installable),
        }
        modes = []
        for key, title, description in UPDATE_MODES:
            enabled, detail, count = state[key]
            modes.append({"key": key, "title": title, "description": description,
                          "detail": detail, "enabled": enabled, "count": count,
                          "favorite": key == self._state["favorite"]})
        # The main button runs the favorite, or, when that has nothing to
        # install (e.g. Upgrade All with only Flatpak updates), the first mode
        # that does, so it's never disabled while updates are waiting.
        favorite = self._state["favorite"]
        main = favorite if state[favorite][0] else next(
            (k for k in ("everything", "all", "minor", "security") if state[k][0]),
            favorite)
        self._set(modes=modes, mainMode=main)

    def _refresh_release(self) -> None:
        upgrade = self._release_upgrade
        dismissed = self.app.settings.dismissed_release
        if upgrade is None or (not upgrade.downloaded and upgrade.target <= dismissed):
            self._set(release={})
            return
        target, current = upgrade.target, upgrade.current
        if upgrade.downloaded:
            info = {"visible": True, "downloaded": True, "target": target,
                    "title": f"Fedora {target} is downloaded and ready to install",
                    "text": "Restart to install it. Installation runs before you "
                            "log in, takes roughly 15–60 minutes, and must not be "
                            "interrupted. Save your work first.",
                    "primary": "Restart and Install", "secondary": "Cancel Upgrade"}
        else:
            text = f"Upgrade from Fedora {current} to get the latest Fedora release."
            eol = _format_day(upgrade.current_eol)
            if eol:
                text += f" Fedora {current} gets updates until {eol}."
            info = {"visible": True, "downloaded": False, "target": target,
                    "title": f"Fedora {target} is available", "text": text,
                    "primary": f"Upgrade to Fedora {target}…",
                    "secondary": "Not Now"}
        self._set(release=info)

    def set_release_upgrade(self, upgrade) -> None:
        self._release_upgrade = upgrade
        self._refresh_release()

    def _refresh_blocked(self) -> None:
        security = self._security
        blocked = security.blocked if security else None
        if not blocked:
            self._set(blocked={})
            return
        waiting = self._state["securityWaiting"]
        count = waiting or len(blocked.packages)
        noun = ("advisory" if count == 1 else "advisories") if waiting else (
            "package" if count == 1 else "packages")
        title = (f"{count} security {noun} waiting on {blocked.source}"
                 if blocked.source else f"{count} security {noun} can't install yet")
        text = ("Nothing to do now: your other updates install normally, and this "
                "one installs by itself once "
                + (blocked.source or "its repository") + " catches up, usually "
                "within a few days.")
        self._set(blocked={"visible": True, "title": title, "text": text})

    # ── held-back (major) patterns ─────────────────────────────

    def set_held_back_patterns(self, patterns: list[str]) -> None:
        self._held_back = list(patterns)
        if self._info is not None:
            self._rebuild()

    @property
    def held_back_patterns(self) -> list[str]:
        return list(self._held_back)

    def _names_where(self, held: bool) -> list[str]:
        info = self._info
        if not info or not info.packages:
            return []
        names: list[str] = []
        for pkg in info.packages:
            if is_held_back(pkg.name, self._held_back) == held and pkg.name not in names:
                names.append(pkg.name)
        return names

    def held_back_package_names(self) -> list[str]:
        return self._names_where(True)

    def minor_package_names(self) -> list[str]:
        return self._names_where(False)

    # ── blocked security ───────────────────────────────────────

    @property
    def security_blocked(self):
        return self._security.blocked if self._security else None

    @property
    def security_installable(self) -> int:
        return self._state["securityTotal"] - self._state["securityWaiting"]

    def blocked_summary(self) -> str:
        blocked = self.security_blocked
        if not blocked:
            return ""
        installable = self.security_installable
        if installable:
            advice = (f"Security Only still installs the other {installable} "
                      f"{'advisory' if installable == 1 else 'advisories'}.")
        else:
            advice = ("Running Security Only again won't install it until then, "
                      "unless you force it.")
        return f"{blocked.explanation()} {advice}"

    # ── actions ────────────────────────────────────────────────

    @staticmethod
    def _preview_line(preview, count_fallback: int = 0) -> str:
        """'N packages, ~X download' ('' if unknown)."""
        if preview is not None and preview.has_preview:
            if preview.sizes_known and preview.total_bytes > 0:
                return (f"{preview.count} packages, "
                        f"~{_size_text(preview.total_bytes)} download")
            return f"{preview.count} packages"
        if count_fallback:
            return f"{count_fallback} packages"
        return ""

    @pyqtSlot(str)
    def setFavorite(self, key: str) -> None:
        if key not in UPDATE_MODE_KEYS:
            return
        self.app.settings.update_favorite = key
        self._set(favorite=key)
        self._refresh_modes()

    @pyqtSlot()
    def runFavorite(self) -> None:
        """Ctrl+U and the main button: run the main mode if it can run."""
        key = self._state["mainMode"]
        mode = next((m for m in self._state["modes"] if m["key"] == key), None)
        if mode and mode["enabled"]:
            self.runMode(key)

    @pyqtSlot(str)
    def runMode(self, key: str) -> None:
        {"all": self.upgrade_all, "everything": self.update_everything,
         "minor": self.upgrade_without_major,
         "security": self.security_upgrade}.get(key, lambda: None)()

    def _plain_names(self, names: list[str], limit: int = 12) -> str:
        shown = ", ".join(names[:limit])
        more = f" and {len(names) - limit} more" if len(names) > limit else ""
        return shown + more

    def upgrade_all(self) -> None:
        preview = self._preview_line(self.upgrade_preview)
        detail = f"\n\n{preview}." if preview else ""
        cmd = self.app.backend.build_upgrade_command()
        self.app.prompts.confirm(
            "Upgrade All?",
            f"This upgrades every package on your system.{detail}\n\n"
            + self.app.password_note(cmd),
            lambda: self.app.runner.run(cmd, "System Upgrade"),
            confirm_label="Upgrade All", default_yes=False)

    def update_everything(self) -> None:
        dnf_preview = self._preview_line(self.upgrade_preview)
        self.app.prompts.confirm(
            "Update Everything?",
            "This runs back to back:\n\n"
            "1. dnf upgrade --refresh (system packages"
            f"{f' — {dnf_preview}' if dnf_preview else ''})\n"
            "2. flatpak update -y (all Flatpak apps)\n\n"
            "dnf may also replace or remove packages when an update needs it; "
            "the output lists everything it changes. "
            + self.app.password_note(self.app.backend.build_upgrade_command()),
            lambda: self.app.runner.run_chain(
                [self.app.backend.build_upgrade_command(),
                 self.app.flatpak_backend.build_update_all_command()],
                "Update Everything (DNF + Flatpak)"),
            confirm_label="Update Everything", default_yes=False)

    def security_upgrade(self) -> None:
        if self.security_blocked and not self.security_installable:
            self.explain_blocked_security()
            return
        preview = self._preview_line(self.security_preview)
        detail = f"\n\n{preview}." if preview else ""
        if self.security_blocked:
            detail += f"\n\n{self.blocked_summary()}"
        self.app.prompts.confirm(
            "Security Updates Only?",
            "Install only security advisories?\n\nRuns: dnf upgrade --security"
            f"{detail}\n\n"
            "Recommended when you want the important fixes fast without "
            "pulling every feature update. "
            + self.app.password_note(build_security_update_command()),
            lambda: self.app.runner.run(
                build_security_update_command(), "Security Upgrade"),
            confirm_label="Install Security Updates")

    @pyqtSlot()
    def explainBlocked(self) -> None:
        """The blocked-security banner's Details: why, and the Force option."""
        self.explain_blocked_security()

    def explain_blocked_security(self) -> None:
        """Security Only has nothing it can install: say why, offer force."""
        def chosen(choice: str) -> None:
            if choice == "force":
                self.forceSecurity()
        self.app.prompts.choose(
            "Nothing to Install Yet",
            "Some security updates can't be installed yet.\n\n"
            + self.blocked_summary()
            + "\n\nWaiting is usually best. Force Install removes the package "
            "that holds them back.",
            [("force", "Force Install…"), ("ok", "OK")], chosen, default="ok")

    @pyqtSlot()
    def forceSecurity(self) -> None:
        blocked = self.security_blocked
        if blocked is None:
            return
        removals = list(blocked.removals)
        if removals:
            consequence = (
                f"To make room, dnf will remove: {', '.join(removals)}.\n\n"
                "Anything that relies on it stops working until you reinstall "
                "it. Once a matching update is out, reinstall with:\n"
                f"sudo dnf install {' '.join(removals)}")
        else:
            consequence = "dnf may remove packages that block these updates."

        def go() -> None:
            self.app.forced_removals = removals
            self.app.runner.run(
                build_forced_security_update_command(), "Forced Security Upgrade")
        self.app.prompts.confirm(
            "Force Security Updates?",
            f"{blocked.explanation()}\n\n{consequence}\n\n"
            "Runs: dnf upgrade --security --allowerasing --best\n\n"
            "Waiting is usually the better choice. Force anyway?",
            go, confirm_label="Force Install", destructive=True)

    def upgrade_without_major(self) -> None:
        patterns = self.held_back_patterns
        held = self.held_back_package_names()
        preview = self.upgrade_preview
        preview_text = self._preview_line(
            preview.excluding(patterns) if preview is not None else None,
            count_fallback=len(self.minor_package_names()))
        detail = f"\n\n{preview_text}." if preview_text else ""
        if held:
            held_text = (f"Core updates skipped ({len(held)}): "
                         f"{self._plain_names(held)}.\n"
                         "These install when you run Upgrade All.")
        else:
            held_text = "No core updates are pending right now."
        self.app.prompts.confirm(
            "Update Without Core?",
            "Install everything except core updates (kernel, graphics "
            f"drivers, firmware, bootloader)?{detail}\n\n{held_text}\n\n"
            "What counts as core can be changed in Settings. "
            + self.app.password_note(
                self.app.backend.build_upgrade_without_major_command(patterns)),
            lambda: self.app.runner.run(
                self.app.backend.build_upgrade_without_major_command(patterns),
                "Update Without Core"),
            confirm_label="Update Without Core")

    @pyqtSlot(str)
    def upgradePackage(self, name: str) -> None:
        self.app.prompts.confirm(
            "Update Package?",
            f"Update only {name} (and anything it needs)?\n\n"
            + self.app.password_note(self.app.backend.build_upgrade_package_command(name)),
            lambda: self.app.runner.run(
                self.app.backend.build_upgrade_package_command(name),
                f"Updating {name}"),
            confirm_label="Update")

    @pyqtSlot(str)
    def toggleMajor(self, name: str) -> None:
        """Per-row Treat as Core / Don't Treat as Core."""
        self.app.settings_controller.toggle_hold(
            name, name not in self._held_back)

    @pyqtSlot()
    def dismissReboot(self) -> None:
        self._reboot_dismissed = True
        self._set(rebootRequired=False)

    def set_reboot_required(self, required: bool, certain: bool = True) -> None:
        self._set(rebootRequired=bool(required) and not self._reboot_dismissed,
                  rebootCertain=certain)

    def _on_reboot_checked(self, needed) -> None:
        # Unknown isn't "no": after an update, say a restart may be needed.
        if needed is None:
            self.set_reboot_required(True, certain=False)
        else:
            self.set_reboot_required(bool(needed))

    def _on_reboot_check_failed(self, _error: str) -> None:
        self.set_reboot_required(True, certain=False)

    def recheck_reboot(self) -> None:
        """After a successful upgrade a reboot may be pending (new kernel)."""
        worker = RebootCheckWorker(self.app.backend, parent=self)
        # Bound methods, not lambdas: PyQt drops these connections when this
        # controller goes away, so a late result can't reach a dead object.
        worker.finished.connect(self._on_reboot_checked)
        worker.error.connect(self._on_reboot_check_failed)
        self._reboot_worker = worker
        worker.start()

    @pyqtSlot()
    def reboot(self) -> None:
        self.app.prompts.confirm(
            "Restart Now?",
            "Restart the computer now to finish applying updates?\n\n"
            "Save your work first. Unsaved changes will be lost.",
            self.app.reboot_now, confirm_label="Restart Now", destructive=True)

    # ── Fedora release upgrades ────────────────────────────────

    @staticmethod
    def release_operation(target: int) -> str:
        return f"Upgrade to Fedora {target}"

    @pyqtSlot()
    def releasePrimary(self) -> None:
        upgrade = self._release_upgrade
        if upgrade is None:
            return
        if upgrade.downloaded:
            self.install_release_upgrade(upgrade.target)
        else:
            self.start_release_upgrade(upgrade.target)

    @pyqtSlot()
    def releaseSecondary(self) -> None:
        upgrade = self._release_upgrade
        if upgrade is None:
            return
        if upgrade.downloaded:
            self.cancel_release_upgrade()
        else:
            self.app.settings.dismissed_release = upgrade.target
            self._set(release={})

    @pyqtSlot()
    def openReleaseNotes(self) -> None:
        QDesktopServices.openUrl(QUrl(RELEASE_NOTES_URL))

    def start_release_upgrade(self, target: int) -> None:
        current = release_upgrade.current_release() or target - 1

        def go() -> None:
            self.app.pending_release_target = target
            self.app.runner.run_chain(
                [self.app.backend.build_upgrade_command(),
                 release_upgrade.build_download_command(self.app.backend.dnf_path,
                                                        target)],
                self.release_operation(target))
        self.app.prompts.confirm(
            f"Upgrade to Fedora {target}?",
            f"Upgrading from Fedora {current} to Fedora {target} takes three "
            "steps:\n\n"
            f"1. Install all pending updates for Fedora {current}.\n"
            f"2. Download Fedora {target} (usually 2–4 GB). You can keep working.\n"
            "3. Restart to install. This runs before you log in and takes about "
            "15–60 minutes.\n\n"
            "Steps 1 and 2 start now. You decide when to restart.\n\n"
            "Before you start: back up important files and keep laptops plugged "
            "in. Third-party repositories (COPRs, vendor repos) may not have "
            f"Fedora {target} packages yet.\n\nFedora's guide: {UPGRADE_DOCS_URL}",
            go, confirm_label="Start Upgrade", default_yes=False)

    def on_release_download_failed(self, target: int) -> None:
        self.app.prompts.confirm(
            "Download Failed",
            f"Downloading Fedora {target} failed. This usually means some "
            "installed packages (often from a COPR or third-party repo) have "
            f"no Fedora {target} version yet.\n\n"
            "Check the output for the packages involved. You can retry and let "
            "DNF remove those packages (--allowerasing), or cancel, deal with "
            "them yourself and try again later.",
            lambda: self.app.runner.run(
                release_upgrade.build_download_command(
                    self.app.backend.dnf_path, target, allow_erasing=True),
                self.release_operation(target)),
            confirm_label="Retry and Remove Conflicting Packages", destructive=True)

    def on_release_downloaded(self, target: int) -> None:
        current = release_upgrade.current_release() or target - 1
        self.set_release_upgrade(
            release_upgrade.ReleaseUpgrade(current, target, downloaded=True))
        self.install_release_upgrade(target)

    def install_release_upgrade(self, target: int) -> None:
        self.app.prompts.confirm(
            f"Restart and Install Fedora {target}?",
            f"Fedora {target} is downloaded. Restart now to install it?\n\n"
            "Save your work first. The installation runs before you log in, "
            "takes about 15–60 minutes, and must not be interrupted. Your "
            "computer restarts again when it's done.\n\n"
            "Choose Later to install from the Updates page.",
            lambda: self.app.runner.run(
                release_upgrade.build_reboot_command(self.app.backend.dnf_path),
                f"Restarting to install Fedora {target}"),
            confirm_label="Restart and Install", cancel_label="Later",
            destructive=True)

    def cancel_release_upgrade(self) -> None:
        self.app.prompts.confirm(
            "Cancel Upgrade?",
            "Discard the downloaded Fedora upgrade and free its disk space? "
            "You can start the upgrade again later.",
            lambda: self.app.runner.run(
                release_upgrade.build_clean_command(self.app.backend.dnf_path),
                "Cancelling Fedora upgrade"),
            confirm_label="Discard Upgrade", cancel_label="Keep It",
            destructive=True)

    # ── clean up ───────────────────────────────────────────────

    @pyqtSlot()
    def autoremove(self) -> None:
        """Preview what dnf autoremove would remove, then confirm."""
        running = getattr(self, "_autoremove_worker", None)
        if running is not None and running.isRunning():
            return  # already looking
        self.app.prompts.toast("Looking for packages nothing needs…")
        worker = CallWorker(self.app.backend.unneeded_packages, parent=self)
        worker.finished.connect(self._confirm_autoremove)
        worker.error.connect(lambda e: self.app.show_error(
            "Operation Failed", f"An error occurred:\n\n{e}"))
        self._autoremove_worker = worker
        worker.start()

    def _confirm_autoremove(self, packages: list) -> None:
        if not packages:
            self.app.prompts.inform(
                "Nothing to Clean Up",
                "No unneeded dependencies are installed. There's nothing to remove.")
            return
        self.app.prompts.confirm(
            "Clean Up?",
            f"Remove {_plural(len(packages), 'package')} that were installed as "
            "dependencies and are no longer needed?\n\n"
            "Check the list for anything you use directly; if you see one, "
            "cancel and install it explicitly so DNF keeps it. "
            "Runs: dnf autoremove -y",
            lambda: self.app.runner.run(
                self.app.backend.build_autoremove_command(), "Autoremove"),
            confirm_label="Remove", destructive=True, details=list(packages))


__all__ = ["UpdatesController", "UPDATE_MODES", "DEFAULT_HELD_BACK_PATTERNS"]
