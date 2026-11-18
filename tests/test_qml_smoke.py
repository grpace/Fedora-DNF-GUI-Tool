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
    controller._shutdown()
    for thread in controller.detached_threads:
        thread.wait(10000)
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
    _spin(700)
    lists = [i for i in window.findChildren(QQuickItem)
             if i.property("objectName") == "" and i.metaObject().className().startswith("QQuickListView")
             and i.property("shownPhase") is not None]
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


def _find(window, predicate):
    return [i for i in _items(window.contentItem()) if predicate(i)]


def test_cancel_hidden_for_downloads_that_cannot_be_cancelled(ui):
    controller, window, (warnings, messages) = ui
    fake = type("W", (), {"isRunning": lambda self: True})()
    controller.runner.start_external("Downloading app update", fake)
    controller.toggleActivity(True)
    _spin(150)
    cancel = _find(window, lambda i: i.property("text") == "Cancel"
                   and i.property("cancellable") is None and i.property("flat") is not None)
    assert cancel and not any(c.isVisible() for c in cancel)
    controller.runner.finish_external(True)
    assert _problems(warnings, messages) == []


def test_scrolling_down_is_not_pulled_back_to_the_top(ui):
    controller, window, (warnings, messages) = ui
    controller.updates._on_checked(_scan(120))
    _spin(200)
    view = _find(window, lambda i: i.property("shownPhase") is not None)[0]
    _spin(700)   # past the settle window
    assert abs(view.property("contentY") - view.property("originY")) < 1
    target = view.property("originY") + 600
    view.setProperty("contentY", target)
    _spin(300)   # delegates get created and contentHeight is re-estimated
    assert view.property("contentY") > view.property("originY") + 300
    assert _problems(warnings, messages) == []


def test_reminder_switch_saves_from_any_toggle_but_not_on_load(ui):
    controller, window, (warnings, messages) = ui
    controller.settings.reminders_enabled = False
    controller.navigate("settings")
    _spin(300)
    assert controller.prompts.notices == []        # opening Settings saves nothing
    switch = _find(window, lambda i: i.property("text") == "Remind me about pending updates")[0]
    from PyQt6.QtCore import QMetaObject, Qt
    # What a screen reader's toggle action does: toggle() flips `checked`
    # and (on Qt 6.11) emits no toggled() signal.
    QMetaObject.invokeMethod(switch, "toggle", Qt.ConnectionType.DirectConnection)
    _spin(100)
    assert controller.settings.reminders_enabled is True
    assert _problems(warnings, messages) == []


def test_flathub_error_is_not_shown_as_no_results(ui):
    controller, window, (warnings, messages) = ui
    controller.navigate("flatpak")
    _spin(200)
    answer(controller)
    controller.flatpak._search_generation = 1
    controller.flatpak._on_search_error(1, "network unreachable")
    assert controller.flatpak.searchError == "network unreachable"
    controller.flatpak.search("")   # clearing the box clears the error
    assert controller.flatpak.searchError == ""
    assert _problems(warnings, messages) == []


def test_opening_settings_keeps_non_default_reminder_choices(ui):
    """Saved values that differ from the defaults must survive opening
    Settings (switches update one at a time from the controller)."""
    controller, window, (warnings, messages) = ui
    settings = controller.settings
    settings.reminders_enabled = True
    settings.security_only = True
    settings.notify_flatpak = False
    settings.check_interval_hours = 72
    controller.navigate("settings")
    _spin(400)
    assert (settings.reminders_enabled, settings.security_only,
            settings.notify_flatpak, settings.check_interval_hours) == (True, True, False, 72)
    assert controller.prompts.notices == []
    # A real change saves just that field.
    switch = _find(window, lambda i: i.property("text") == "Include Flatpak updates"
                   and i.property("checkable") is True)[0]
    from PyQt6.QtCore import QMetaObject, Qt
    assert switch.property("checked") is False   # shows the saved value
    QMetaObject.invokeMethod(switch, "toggle", Qt.ConnectionType.DirectConnection)
    _spin(150)
    assert (settings.reminders_enabled, settings.security_only,
            settings.notify_flatpak, settings.check_interval_hours) == (True, True, True, 72)
    assert _problems(warnings, messages) == []


def test_output_log_is_readable_text(ui):
    controller, window, (warnings, messages) = ui
    controller.toggleActivity(True)
    controller.runner.append("✗ Step failed (exit 1)")
    _spin(150)
    areas = _find(window, lambda i: i.property("readOnly") is True
                  and "Step failed" in str(i.property("text") or ""))
    assert areas, "the log should be a read-only text area screen readers can move through"
    assert areas[0].property("activeFocusOnTab") is True
    assert _problems(warnings, messages) == []


def test_opening_details_moves_keyboard_focus_there(ui):
    controller, window, (warnings, messages) = ui
    controller.updates._on_checked(_scan())
    _spin(200)
    QMetaObject.invokeMethod(window, "openPackageDetails", Qt.ConnectionType.DirectConnection,
                             Q_ARG("QVariant", "pkg1"))
    _spin(200)
    item, titles = window.activeFocusItem(), []
    while item is not None:
        titles.append(item.property("title"))
        item = item.parentItem()
    assert "pkg1" in titles
    QMetaObject.invokeMethod(window, "closeColumns", Qt.ConnectionType.DirectConnection)
    _spin(150)
    item, titles = window.activeFocusItem(), []
    while item is not None:
        titles.append(item.property("title"))
        item = item.parentItem()
    assert "Updates" in titles
    assert _problems(warnings, messages) == []


def _press_escape(window) -> None:
    from PyQt6.QtTest import QTest
    window.requestActivate()
    _spin(50)
    QTest.keyClick(window, Qt.Key.Key_Escape)
    _spin(150)


def test_escape_closes_the_log_or_the_column_by_where_focus_is(ui):
    """With the log open, Esc closes whatever holds the focus: the details
    column from the column, the log from any control in the log pane."""
    controller, window, (warnings, messages) = ui
    controller.updates._on_checked(_scan())
    _spin(200)
    controller.toggleActivity(True)
    QMetaObject.invokeMethod(window, "openPackageDetails", Qt.ConnectionType.DirectConnection,
                             Q_ARG("QVariant", "pkg1"))
    _spin(200)
    _press_escape(window)  # focus is in the details column
    assert _titles(window) == "Updates"
    assert controller.activityExpanded

    QMetaObject.invokeMethod(window, "openPackageDetails", Qt.ConnectionType.DirectConnection,
                             Q_ARG("QVariant", "pkg1"))
    _spin(200)
    controller.runner.append("some output")
    _spin(100)
    copy = _find(window, lambda i: i.property("text") == "Copy Output")
    assert copy
    copy[0].forceActiveFocus()
    _spin(50)
    _press_escape(window)  # focus is on a button in the log pane
    assert not controller.activityExpanded
    assert _titles(window) == "Updates | pkg1"

    controller.toggleActivity(True)
    QMetaObject.invokeMethod(window, "closeColumns", Qt.ConnectionType.DirectConnection)
    _spin(150)
    _press_escape(window)  # no column to close: the log closes
    assert not controller.activityExpanded
    assert _problems(warnings, messages) == []


def test_banners_give_screen_readers_plain_text(ui):
    """Kirigami's banner label would expose its HTML document as the
    accessible name; screen readers must get the sentence instead."""
    from PyQt6.QtQml import QQmlEngine, QQmlProperty
    controller, window, (warnings, messages) = ui
    controller.updates._on_checked(_scan())       # restart needed: a banner shows
    _spin(300)
    names = []
    for item in _find(window, lambda i: i.property("readOnly") is True
                      and "Restart to finish updating" in str(i.property("text") or "")):
        prop = QQmlProperty(item, "Accessible.name", QQmlEngine.contextForObject(item))
        names.append(str(prop.read() or ""))
    assert names, "the restart banner should be showing"
    assert not [n for n in names if "<" in n]
    assert any(n.startswith("Restart to finish updating. Core system") for n in names)
    assert _problems(warnings, messages) == []
