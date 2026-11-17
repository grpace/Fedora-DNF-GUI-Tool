"""Load the real Kirigami UI offscreen and visit every page.

Fails on any QML warning or error (a missing property, a typo in a
binding, a page that doesn't load), and checks that navigation, the
details column, prompts and the activity panel are wired up.
"""

import pytest
from PyQt6.QtCore import QMetaObject, Q_ARG, Q_RETURN_ARG, Qt, QtMsgType, qInstallMessageHandler
from PyQt6.QtWidgets import QApplication

from tests.conftest import answer
from dnf_gui.core.package import Package, PackageStatus, UpdateInfo

PAGE_TITLES = {
    "updates": "Updates", "installed": "Installed", "flatpak": "Flatpak",
    "sysinfo": "System", "tools": "Tools", "repos": "Repositories",
    "history": "History", "settings": "Settings",
}


def _spin(ms: int = 60) -> None:
    from PyQt6.QtCore import QEventLoop, QTimer
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


@pytest.fixture
def ui():
    from dnf_gui.ui import window as ui_window
    from dnf_gui.ui.controllers.app_controller import AppController

    messages: list[str] = []

    def handler(kind, _context, text):
        if kind != QtMsgType.QtDebugMsg:
            messages.append(text)
    previous = qInstallMessageHandler(handler)
    controller = AppController()
    warnings: list[str] = []
    engine, window = ui_window.load(controller, warnings)
    window.resize(1280, 800)
    window.show()
    _spin(200)
    yield controller, window, (warnings, messages)
    controller.prompts.cancel_all()
    controller.shutdown_threads()
    ui_window.unload(engine, controller)
    QApplication.processEvents()
    qInstallMessageHandler(previous)


def _titles(window) -> str:
    return QMetaObject.invokeMethod(
        window, "columnTitles", Qt.ConnectionType.DirectConnection,
        Q_RETURN_ARG("QVariant"))


def _problems(warnings, messages) -> list[str]:
    return list(dict.fromkeys(warnings + messages))


def test_every_page_loads_without_qml_warnings(ui):
    controller, window, (warnings, messages) = ui
    for key, title in PAGE_TITLES.items():
        controller.navigate(key)
        _spin()
        assert _titles(window) == title, key
    assert _problems(warnings, messages) == []


def test_ctrl_number_order_matches_v1(ui):
    controller, window, (warnings, messages) = ui
    controller.navigateIndex(3)
    _spin()
    assert controller.currentPage == "sysinfo"
    controller.navigateIndex(7)  # v1's Terminal page: now the activity panel
    assert controller.activityExpanded and controller.activityVisible
    assert controller.currentPage == "sysinfo"
    assert _problems(warnings, messages) == []


def test_update_rows_and_details_column(ui):
    controller, window, (warnings, messages) = ui
    pkg = Package("firefox", "146.0.1", "1.fc45", "x86_64", "updates",
                  status=PackageStatus.UPDATE_AVAILABLE, installed_version="145.0-1.fc45")
    controller.updates._on_checked({"dnf": UpdateInfo(1, [pkg]), "flatpak": [],
                                    "security": None, "preview": None,
                                    "security_preview": None, "reboot": True})
    _spin()
    assert controller.updates.phase == "ready"
    assert controller.updates.filtered.count == 1
    QMetaObject.invokeMethod(window, "openPackageDetails", Qt.ConnectionType.DirectConnection,
                             Q_ARG("QVariant", "firefox"))
    _spin()
    assert _titles(window) == "Updates | firefox"
    controller.navigate("installed")
    _spin()
    assert _titles(window) == "Installed"  # columns close when leaving
    assert _problems(warnings, messages) == []


def test_prompt_and_activity_panel_render(ui):
    controller, window, (warnings, messages) = ui
    controller.prompts.confirm("Remove Package?", "Remove htop?", lambda: None,
                               destructive=True, details=["htop-3.4.1-2.fc45"])
    _spin()
    assert controller.prompts.active
    controller.prompts.reply(controller.prompts.current["token"], "no")
    controller.runner.append("line one\nline two")
    controller.toggleActivity(True)
    _spin()
    assert controller.runner.log.count >= 2
    assert _problems(warnings, messages) == []


def test_up_to_date_and_failed_states(ui):
    controller, window, (warnings, messages) = ui
    controller.updates._on_checked({"dnf": UpdateInfo(), "flatpak": [], "security": None})
    _spin()
    assert controller.updates.phase == "uptodate"
    failed = UpdateInfo()
    failed.check_failed = True
    controller.updates._on_checked({"dnf": failed, "flatpak": [], "security": None})
    _spin()
    assert controller.updates.phase == "failed"
    assert "Up to Date" not in controller.updates.headline
    assert _problems(warnings, messages) == []


def test_prompts_answered_through_conftest_helper(ui):
    controller, _window, _ = ui
    ran = []
    shown = answer(controller, "yes")
    controller.prompts.confirm("Go?", "Go now?", lambda: ran.append(1))
    assert ran == [1] and shown[-1].title == "Go?"


def _scan(n: int = 3) -> dict:
    pkgs = [Package(f"pkg{i}", "1.1", "1.fc45", "x86_64", "updates",
                    status=PackageStatus.UPDATE_AVAILABLE, installed_version="1.0-1.fc45")
            for i in range(n)]
    return {"dnf": UpdateInfo(n, pkgs), "flatpak": [], "security": None,
            "preview": None, "security_preview": None, "reboot": True}


def _focused_page_title(window) -> str:
    item = window.activeFocusItem()
    while item is not None:
        title = item.property("title")
        if isinstance(title, str) and title in PAGE_TITLES.values():
            return title
        item = item.parentItem()
    return ""


def test_ctrl_f_focuses_the_visible_pages_field(ui):
    controller, window, (warnings, messages) = ui
    controller.updates._on_checked(_scan())
    for key in ("installed", "flatpak", "repos", "history", "updates"):
        controller.navigate(key)   # every page now exists, hidden or not
        _spin()
    for key in ("repos", "updates", "installed", "history"):
        controller.navigate(key)
        _spin()
        controller.focusSearch()
        _spin()
        assert _focused_page_title(window) == PAGE_TITLES[key], key
    assert _problems(warnings, messages) == []


def test_show_all_updates_clears_the_filter(ui):
    controller, window, (warnings, messages) = ui
    controller.updates._on_checked(_scan())
    _spin()
    controller.updates.filtered.query = "zzzz"
    controller.updates.filtered.category = "security"
    _spin()
    from PyQt6.QtQuick import QQuickItem
    updates_page = next(p for p in window.findChildren(QQuickItem)
                        if p.property("title") == "Updates" and p.metaObject().indexOfMethod("showAllUpdates()") >= 0)
    QMetaObject.invokeMethod(updates_page, "showAllUpdates", Qt.ConnectionType.DirectConnection)
    assert controller.updates.filtered.query == ""
    assert controller.updates.filtered.category == "all"
    assert controller.updates.filtered.count == 3
    assert _problems(warnings, messages) == []


def test_summary_stays_at_the_top_when_results_arrive(ui):
    controller, window, (warnings, messages) = ui
    from PyQt6.QtQuick import QQuickItem
    _spin()
    controller.updates._on_checked(_scan(40))
    _spin(200)
    lists = [i for i in window.findChildren(QQuickItem)
             if i.property("objectName") == "" and i.metaObject().className().startswith("QQuickListView")
             and i.property("pinnedTop") is not None]
    assert lists
    view = lists[0]
    assert abs(view.property("contentY") - view.property("originY")) < 1
    assert _problems(warnings, messages) == []


def _items(root):
    stack = [root]
    while stack:
        item = stack.pop()
        yield item
        stack.extend(item.childItems())


def test_collapsed_sidebar_keeps_its_icons(ui):
    controller, window, (warnings, messages) = ui
    window.resize(820, 700)   # below the compact width
    _spin(300)
    nav = [i for i in _items(window.contentItem())
           if i.property("key") == "updates" and i.property("collapsed") is not None]
    assert nav and nav[0].property("collapsed") is True
    item = nav[0]
    assert item.isVisible()
    # Its icon sits in the rail at the window's left edge, and is drawn.
    from PyQt6.QtCore import QPointF
    centre = item.mapToScene(QPointF(item.width() / 2, item.height() / 2))
    assert 0 < centre.x() < 120
    opacity, parent = 1.0, item
    while parent is not None:
        opacity *= parent.opacity()
        parent = parent.parentItem()
    assert opacity > 0.5
    assert _problems(warnings, messages) == []
