"""Controllers for the Installed, Flatpak, Repositories, History, System
and Tools pages: load a list, filter it, and run the existing commands."""

from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtProperty, pyqtSignal, pyqtSlot

from dnf_gui.core.package import PackageStatus
from dnf_gui.core.worker import (
    CallWorker, FlatpakListWorker, FlatpakSearchWorker, HistoryWorker,
    PackageInfoWorker, PackageListWorker, RepoListWorker, SystemInfoWorker,
    ToolkitCheckWorker,
)
from dnf_gui.ui.controllers.base import FilterModel, RowModel, StateObject, declare

LOADER_PROPS = {"loading": bool, "loaded": bool, "error": str}

PACKAGE_ROLES = ("name", "version", "arch", "repo", "summary", "installed")
SORTS = {
    "name": lambda r: r["name"].lower(),
    "name_desc": lambda r: r["name"].lower(),
    "repo": lambda r: (r["repo"].lower(), r["name"].lower()),
}


def _package_row(pkg) -> dict:
    return {"name": pkg.name, "version": pkg.full_version, "arch": pkg.arch,
            "repo": pkg.repo, "summary": pkg.summary or "",
            "installed": pkg.status == PackageStatus.INSTALLED}


class _Loader(StateObject):
    """Common loading/error state for list pages."""

    _defaults = {"loading": False, "loaded": False, "error": ""}

    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app

    def _fail(self, error: str) -> None:
        self._set(loading=False, error=error)

    def invalidate(self) -> None:
        """System changed: reload on the next visit."""
        self._set(loaded=False)

    def show(self) -> None:
        if not self._state["loaded"]:
            self.refresh()

    def refresh(self) -> None:  # pragma: no cover - overridden
        raise NotImplementedError


# ── Installed packages + repository search + details ──────────────

class PackagesController(_Loader):
    _defaults = {**_Loader._defaults, "sort": "name", "searching": False,
                 "searchQuery": "", "searchDone": False, "details": {},
                 "detailsLoading": False}
    changed = pyqtSignal()
    declare(locals(), changed, {**LOADER_PROPS, "sort": str, "searching": bool, "searchQuery": str, "searchDone": bool, "details": "QVariantMap", "detailsLoading": bool})

    def __init__(self, app, parent=None):
        super().__init__(app, parent)
        self._installed = RowModel(PACKAGE_ROLES, self)
        self._filtered = FilterModel(self._installed, ("name", "repo"), parent=self)
        self._results = RowModel(PACKAGE_ROLES, self)
        self._search_generation = 0
        self._details_name = ""

    @pyqtProperty(QObject, constant=True)
    def installed(self) -> FilterModel:
        return self._filtered

    @pyqtProperty(QObject, constant=True)
    def results(self) -> RowModel:
        return self._results

    @pyqtSlot()
    def refresh(self) -> None:
        self._set(loading=True, error="")
        worker = PackageListWorker(self.app.backend, parent=self)
        worker.finished.connect(self._on_loaded)
        worker.error.connect(self._fail)
        self._worker = worker
        worker.start()

    def _on_loaded(self, packages) -> None:
        rows = [_package_row(p) for p in packages]
        self._installed.set_rows(self._sorted(rows))
        self._set(loading=False, loaded=True)

    def _sorted(self, rows: list[dict]) -> list[dict]:
        key = self._state["sort"]
        return sorted(rows, key=SORTS.get(key, SORTS["name"]),
                      reverse=key == "name_desc")

    @pyqtSlot(str)
    def setSort(self, key: str) -> None:
        if key in SORTS:
            self._set(sort=key)
            self._installed.set_rows(self._sorted(self._installed.rows()))

    @pyqtSlot(str)
    def search(self, query: str) -> None:
        """Search the repositories (explicit, not on every keystroke)."""
        query = (query or "").strip()
        self._search_generation += 1
        generation = self._search_generation
        if len(query) < 2:
            self._results.set_rows([])
            self._set(searching=False, searchQuery=query, searchDone=False)
            return
        self._set(searching=True, searchQuery=query, searchDone=False)
        worker = CallWorker(self.app.backend.search, query, parent=self)
        worker.finished.connect(lambda res: self._on_search(generation, res))
        worker.error.connect(lambda e: self._on_search_error(generation, e))
        self._search_worker = worker
        worker.start()

    def _on_search(self, generation: int, results) -> None:
        if generation != self._search_generation:
            return  # the user has typed past this query
        self._results.set_rows([_package_row(p) for p in results or []])
        self._set(searching=False, searchDone=True)

    def _on_search_error(self, generation: int, error: str) -> None:
        if generation == self._search_generation:
            self._set(searching=False, searchDone=True)
            self.app.show_error("Search Failed", error)

    @pyqtSlot(str)
    def install(self, name: str) -> None:
        self.app.prompts.confirm(
            "Install Package?",
            f"Install {name} and its dependencies?\n\n"
            "DNF lists everything it installs in the output. "
            + self.app.password_note(self.app.backend.build_install_command(name)),
            lambda: self.app.runner.run(
                self.app.backend.build_install_command(name), f"Installing {name}"),
            confirm_label="Install")

    @pyqtSlot(str)
    def remove(self, name: str) -> None:
        self.app.prompts.confirm(
            "Remove Package?",
            f"Remove {name}?\n\nThis also removes packages that depend on it. "
            + self.app.password_note(self.app.backend.build_remove_command(name)),
            lambda: self.app.runner.run(
                self.app.backend.build_remove_command(name), f"Removing {name}"),
            confirm_label="Remove", destructive=True)

    def reload_details(self) -> None:
        """After an operation: refresh an open details pane (installed?)."""
        if self._details_name:
            self.loadDetails(self._details_name)

    @pyqtSlot(str)
    def loadDetails(self, name: str) -> None:
        """Fetch ``dnf info`` for the details column."""
        self._details_name = name
        self._set(details={"name": name}, detailsLoading=True)
        worker = PackageInfoWorker(self.app.backend, name, parent=self)
        worker.finished.connect(lambda pkg: self._on_details(name, pkg))
        worker.error.connect(lambda _e: self._on_details(name, None))
        self._details_worker = worker
        worker.start()

    def _on_details(self, name: str, pkg) -> None:
        if name != self._details_name:
            return
        if pkg is None:
            self._set(detailsLoading=False,
                      details={"name": name, "missing": True})
            return
        self._set(detailsLoading=False, details={
            "name": pkg.name, "summary": pkg.summary, "description": pkg.description,
            "version": pkg.version, "release": pkg.release, "arch": pkg.arch,
            "repo": pkg.repo, "size": pkg.size, "installedSize": pkg.installed_size,
            "license": pkg.license, "url": pkg.url,
            "installed": pkg.status == PackageStatus.INSTALLED,
            "missing": False})


# ── Flatpak ───────────────────────────────────────────────────────

FLATPAK_ROLES = ("name", "appId", "version", "branch", "origin", "size",
                 "description", "runtime", "installed")


def _flatpak_row(app, installed: bool) -> dict:
    return {"name": app.name or app.application_id, "appId": app.application_id,
            "version": app.version, "branch": app.branch, "origin": app.origin,
            "size": app.size, "description": app.description,
            "runtime": bool(app.is_runtime), "installed": installed}


class FlatpakController(_Loader):
    _defaults = {**_Loader._defaults, "available": True, "showRuntimes": False,
                 "searching": False, "searchQuery": "", "searchDone": False,
                 "searchError": ""}
    changed = pyqtSignal()
    declare(locals(), changed, {**LOADER_PROPS, "available": bool, "showRuntimes": bool, "searching": bool, "searchQuery": str, "searchDone": bool, "searchError": str})

    def __init__(self, app, parent=None):
        super().__init__(app, parent)
        self._installed = RowModel(FLATPAK_ROLES, self)
        self._filtered = FilterModel(
            self._installed, ("name", "appId"),
            lambda row, cat: cat != "apps" or not row["runtime"], self)
        self._filtered.category = "apps"
        self._results = RowModel(FLATPAK_ROLES, self)
        self._search_generation = 0

    @pyqtProperty(QObject, constant=True)
    def installed(self) -> FilterModel:
        return self._filtered

    @pyqtProperty(QObject, constant=True)
    def results(self) -> RowModel:
        return self._results

    @pyqtSlot(bool)
    def setShowRuntimes(self, show: bool) -> None:
        self._set(showRuntimes=bool(show))
        self._filtered.category = "all" if show else "apps"

    @pyqtSlot()
    def refresh(self) -> None:
        if not self.app.flatpak_backend.available:
            self._set(available=False, loaded=True, loading=False)
            return
        self._set(loading=True, error="", available=True)
        worker = FlatpakListWorker(self.app.flatpak_backend, parent=self)
        worker.finished.connect(self._on_loaded)
        worker.error.connect(self._fail)
        self._worker = worker
        worker.start()

    def _on_loaded(self, apps) -> None:
        rows = sorted((_flatpak_row(a, True) for a in apps),
                      key=lambda r: (r["runtime"], r["name"].lower()))
        self._installed.set_rows(rows)
        self._set(loading=False, loaded=True)

    @pyqtSlot(str)
    def search(self, query: str) -> None:
        query = (query or "").strip()
        self._search_generation += 1
        generation = self._search_generation
        if len(query) < 2:
            self._results.set_rows([])
            self._set(searching=False, searchQuery=query, searchDone=False)
            return
        self._set(searching=True, searchQuery=query, searchDone=False, searchError="")
        worker = FlatpakSearchWorker(self.app.flatpak_backend, query, parent=self)
        worker.finished.connect(lambda apps: self._on_search(generation, apps))
        worker.error.connect(lambda e: self._on_search_error(generation, e))
        self._search_worker = worker
        worker.start()

    def _on_search_error(self, generation: int, error: str) -> None:
        if generation == self._search_generation:
            self._results.set_rows([])
            self._set(searching=False, searchDone=True, searchError=error)
            self.app.show_error("Flathub Search Failed", error)

    def _on_search(self, generation: int, apps) -> None:
        if generation != self._search_generation:
            return
        installed = {r["appId"] for r in self._installed.rows()}
        self._results.set_rows(
            [_flatpak_row(a, a.application_id in installed) for a in apps or []])
        self._set(searching=False, searchDone=True)

    @pyqtSlot(str, str)
    def install(self, app_id: str, remotes: str = "") -> None:
        self.app.prompts.confirm(
            "Install Flatpak App?", f"Install {app_id}?",
            lambda: self.app.runner.run(
                self.app.flatpak_backend.build_install_command(app_id, remotes),
                f"Installing Flatpak: {app_id}"),
            confirm_label="Install")

    @pyqtSlot(str)
    def remove(self, app_id: str) -> None:
        self.app.prompts.confirm(
            "Remove Flatpak App?", f"Remove {app_id}?",
            lambda: self.app.runner.run(
                self.app.flatpak_backend.build_remove_command(app_id),
                f"Removing Flatpak: {app_id}"),
            confirm_label="Remove", destructive=True)

    @pyqtSlot()
    def updateAll(self) -> None:
        self.app.prompts.confirm(
            "Update Flatpak Apps?", "Update all Flatpak applications?",
            lambda: self.app.runner.run(
                self.app.flatpak_backend.build_update_all_command(),
                "Updating all Flatpak apps"),
            confirm_label="Update All")

    @pyqtSlot()
    def removeUnused(self) -> None:
        self.app.prompts.confirm(
            "Remove Unused Runtimes?",
            "Remove Flatpak runtimes and extensions that no installed app uses?",
            lambda: self.app.runner.run(
                self.app.flatpak_backend.build_remove_unused_command(),
                "Removing unused Flatpak runtimes"),
            confirm_label="Remove Unused", destructive=True)

    @pyqtSlot()
    def repair(self) -> None:
        self.app.prompts.confirm(
            "Repair Flatpak?",
            "Check the Flatpak installation and fix what's broken? This can fix "
            "apps that won't start.",
            lambda: self.app.runner.run(
                self.app.flatpak_backend.build_repair_command(),
                "Repairing Flatpak installation"),
            confirm_label="Repair")


# ── Repositories ──────────────────────────────────────────────────

class ReposController(_Loader):
    changed = pyqtSignal()
    declare(locals(), changed, dict(LOADER_PROPS))

    def __init__(self, app, parent=None):
        super().__init__(app, parent)
        self._repos = RowModel(("id", "name", "enabled"), self)
        self._filtered = FilterModel(self._repos, ("id", "name"), parent=self)

    @pyqtProperty(QObject, constant=True)
    def repos(self) -> FilterModel:
        return self._filtered

    @pyqtSlot()
    def refresh(self) -> None:
        self._set(loading=True, error="")
        worker = RepoListWorker(self.app.backend, show_all=True, parent=self)
        worker.finished.connect(self._on_loaded)
        worker.error.connect(self._fail)
        self._worker = worker
        worker.start()

    def _on_loaded(self, repos) -> None:
        rows = sorted(({"id": r.get("id", ""), "name": r.get("name", ""),
                        "enabled": bool(r.get("enabled", True))} for r in repos),
                      key=lambda r: (not r["enabled"], r["id"].lower()))
        self._repos.set_rows(rows)
        self._set(loading=False, loaded=True)

    @pyqtSlot(str, bool)
    def setEnabled(self, repo_id: str, enabled: bool) -> None:
        """The switch stays as it is until the reloaded list says otherwise."""
        if enabled:
            self.app.prompts.confirm(
                "Enable Repository?", f"Enable {repo_id}?",
                lambda: self.app.runner.run(
                    self.app.backend.build_enable_repo_command(repo_id),
                    f"Enabling repo: {repo_id}"),
                confirm_label="Enable")
        else:
            self.app.prompts.confirm(
                "Disable Repository?",
                f"Disable {repo_id}?\n\nYou won't get updates from it until "
                "you turn it back on.",
                lambda: self.app.runner.run(
                    self.app.backend.build_disable_repo_command(repo_id),
                    f"Disabling repo: {repo_id}"),
                confirm_label="Disable", destructive=True)

    @pyqtSlot(str)
    def addCopr(self, copr_name: str) -> None:
        copr_name = (copr_name or "").strip()
        try:
            cmd = self.app.backend.build_add_copr_command(copr_name)
        except ValueError as e:
            self.app.prompts.inform("Invalid COPR", f"{e}\n\nExample: user/my-project",
                                    level="warning")
            return
        self.app.prompts.confirm(
            "Add COPR Repository?",
            f"Enable the COPR repository {copr_name}?\n\n"
            "COPR repositories are community-maintained. Use them at your own risk.",
            lambda: self.app.runner.run(cmd, f"Adding COPR: {copr_name}"),
            confirm_label="Add Repository", destructive=True)


# ── History ───────────────────────────────────────────────────────

# dnf5 lists transaction actions as letters ("E, I, U").
_ACTION_WORDS = {"I": "Install", "U": "Upgrade", "E": "Removed", "D": "Downgrade",
                 "R": "Reinstall", "O": "Obsoleted", "C": "Reason Change"}


def describe_actions(action: str) -> str:
    """'E, I, U' → 'Removed, Install, Upgrade'; words pass through."""
    parts = [p.strip() for p in action.replace(",", " ").split()]
    if parts and all(p in _ACTION_WORDS for p in parts):
        return ", ".join(_ACTION_WORDS[p] for p in parts)
    return action


class HistoryController(_Loader):
    _defaults = {**_Loader._defaults, "detailId": "", "detailText": "",
                 "detailLoading": False}
    changed = pyqtSignal()
    declare(locals(), changed, {**LOADER_PROPS, "detailId": str, "detailText": str, "detailLoading": bool})

    def __init__(self, app, parent=None):
        super().__init__(app, parent)
        self._items = RowModel(("id", "command", "date", "action", "altered"), self)
        self._filtered = FilterModel(self._items, ("id", "command", "action"),
                                     parent=self)

    @pyqtProperty(QObject, constant=True)
    def items(self) -> FilterModel:
        return self._filtered

    @pyqtSlot()
    def refresh(self) -> None:
        if self._state["loading"]:
            return  # one history load at a time
        self._set(loading=True, error="")
        worker = HistoryWorker(self.app.backend, parent=self)
        worker.finished.connect(self._on_loaded)
        worker.error.connect(self._on_error)
        self._worker = worker
        worker.start()

    def _on_loaded(self, history) -> None:
        rows = []
        for t in history:
            row = {k: str(t.get(k, "")) for k in ("id", "command", "date", "action", "altered")}
            row["action"] = describe_actions(row["action"])
            rows.append(row)
        self._items.set_rows(rows)
        self._set(loading=False, loaded=True)

    def _on_error(self, error: str) -> None:
        self._fail(error)
        self.app.show_error("Couldn't Load History", error)

    @pyqtSlot(str)
    def loadDetail(self, txn_id: str) -> None:
        self._set(detailId=txn_id, detailText="", detailLoading=True)
        worker = CallWorker(self.app.backend.history_info, txn_id, parent=self)
        worker.finished.connect(lambda text: self._on_detail(txn_id, text))
        worker.error.connect(lambda e: self._on_detail(txn_id, e))
        self._detail_worker = worker
        worker.start()

    def _on_detail(self, txn_id: str, text) -> None:
        if txn_id == self._state["detailId"]:
            self._set(detailText=str(text or ""), detailLoading=False)

    @pyqtSlot(str)
    def undo(self, txn_id: str) -> None:
        try:
            cmd = self.app.backend.build_history_undo_command(txn_id)
        except ValueError as e:
            self.app.prompts.inform("Invalid Transaction", str(e), level="warning")
            return
        self.app.prompts.confirm(
            "Undo Transaction?",
            f"Undo transaction #{txn_id}?\n\nThis reverses the changes made in "
            "that transaction. " + self.app.password_note(cmd),
            lambda: self.app.runner.run(cmd, f"Undoing transaction #{txn_id}"),
            confirm_label="Undo", destructive=True)


# ── System info + Quick Tools ─────────────────────────────────────

TOOLS = (
    # (id, section, title, description, action label, destructive)
    ("rpmfusion_free", "Repositories", "RPM Fusion (Free)",
     "Open-source packages Fedora doesn't ship.", "Enable", False),
    ("rpmfusion_nonfree", "Repositories", "RPM Fusion (Non-Free)",
     "Proprietary drivers and codecs.", "Enable", False),
    ("add_flathub", "Repositories", "Flathub",
     "Thousands of Flatpak apps.", "Add", False),
    ("firmware_check", "Maintenance", "Check Firmware Updates",
     "Look for BIOS/UEFI and device firmware updates with fwupd.", "Check", False),
    ("firmware_update", "Maintenance", "Apply Firmware Updates",
     "Install available device firmware updates. May need a restart.",
     "Update", False),
    ("clean_cache", "Maintenance", "Clean DNF Cache",
     "Remove cached metadata and downloaded packages.", "Clean", True),
    ("rebuild_cache", "Maintenance", "Rebuild Metadata Cache",
     "Download fresh repository metadata.", "Rebuild", False),
    ("distro_sync", "Maintenance", "Distribution Sync",
     "Match every installed package to the versions in your repositories.",
     "Sync", True),
)


class SystemController(_Loader):
    _defaults = {**_Loader._defaults, "info": {}}
    changed = pyqtSignal()
    declare(locals(), changed, {**LOADER_PROPS, "info": "QVariantMap"})

    def __init__(self, app, parent=None):
        super().__init__(app, parent)
        self._tools = RowModel(("id", "section", "title", "description", "action",
                                "destructive", "done"), self)
        self._tools.set_rows([
            {"id": t[0], "section": t[1], "title": t[2], "description": t[3],
             "action": t[4], "destructive": t[5], "done": False} for t in TOOLS])
        self._tools_loaded = False

    @pyqtProperty(QObject, constant=True)
    def tools(self) -> RowModel:
        return self._tools

    @pyqtSlot()
    def refresh(self) -> None:
        self._set(loading=True, error="")
        worker = SystemInfoWorker(parent=self)
        worker.finished.connect(self._on_loaded)
        worker.error.connect(self._fail)
        self._worker = worker
        worker.start()

    def _on_loaded(self, info) -> None:
        data = {k: v for k, v in vars(info).items()} if info is not None else {}
        self._set(info={k: ("" if v is None else v) for k, v in data.items()},
                  loading=False, loaded=True)

    def show(self) -> None:
        """Every visit shows fresh memory, disk and tool status (as in v1)."""
        if not self._state["loading"]:
            self.refresh()
        self.refreshTools()

    @pyqtSlot()
    def refreshTools(self) -> None:
        worker = ToolkitCheckWorker(self)
        worker.finished.connect(self._on_tools)
        self._tools_worker = worker
        worker.start()

    def _on_tools(self, statuses: dict) -> None:
        rows = self._tools.rows()
        for row in rows:
            row["done"] = bool(statuses.get(row["id"], False))
        self._tools.set_rows(rows)

    @pyqtSlot(str)
    def runTool(self, tool_id: str) -> None:
        backend = self.app.backend
        tool_map = {
            "rpmfusion_free": (backend.build_install_rpmfusion_free_command,
                               "Installing RPM Fusion (Free)",
                               "Enable the RPM Fusion Free repository?"),
            "rpmfusion_nonfree": (backend.build_install_rpmfusion_nonfree_command,
                                  "Installing RPM Fusion (Non-Free)",
                                  "Enable the RPM Fusion Non-Free repository?"),
            "add_flathub": (lambda: ["flatpak", "remote-add", "--if-not-exists",
                                     "flathub",
                                     "https://dl.flathub.org/repo/flathub.flatpakrepo"],
                            "Adding Flathub repository",
                            "Add the Flathub repository to Flatpak?"),
            "firmware_check": (backend.build_firmware_update_check_command,
                               "Checking firmware updates",
                               "Check for available firmware updates?"),
            "firmware_update": (backend.build_firmware_update_apply_command,
                                "Applying firmware updates",
                                "Apply firmware updates? This may need a restart."),
            "clean_cache": (backend.build_clean_cache_command, "Cleaning DNF cache",
                            "Clean all DNF cached data?"),
            "rebuild_cache": (backend.build_makecache_command,
                              "Rebuilding metadata cache",
                              "Rebuild the DNF metadata cache?"),
            "distro_sync": (backend.build_distro_sync_command, "Distribution Sync",
                            "Run a distribution sync? This changes installed "
                            "packages to match the versions in your repositories."),
        }
        if tool_id not in tool_map:
            self.app.prompts.inform("Unknown Tool", f"Unknown tool: {tool_id}",
                                    level="warning")
            return
        builder, operation, question = tool_map[tool_id]
        tool = next(t for t in TOOLS if t[0] == tool_id)
        self.app.prompts.confirm(
            tool[2], question,
            lambda: self.app.runner.run(builder(), operation),
            confirm_label=tool[4], destructive=tool[5])
