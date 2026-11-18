"""The window around the pages, loaded offscreen for real: the app's own
title bar (window buttons, resize grips, drag handles on every header), the
sidebar's collapse button, and the floating status capsule with its
keyboard shortcuts."""

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtTest import QTest

from dnf_gui.core.package import Package, PackageStatus, UpdateInfo
from tests.conftest import attached, by_name, call, evaluate, find_items, spin, wait_until

PAGES = ("updates", "installed", "flatpak", "sysinfo", "tools", "repos", "history", "settings")


def _scan(controller, n=3):
    pkgs = [Package(f"pkg{i}", "1.1", "1.fc45", "x86_64", "updates",
                    status=PackageStatus.UPDATE_AVAILABLE, installed_version="1.0-1.fc45")
            for i in range(n)]
    controller.updates._on_checked({"dnf": UpdateInfo(n, pkgs), "flatpak": [],
                                    "security": None, "reboot": False})


def _stack(window):
    return window.property("pageStack")


def _columns(window):
    return [evaluate(window, f"pageStack.get({i})")
            for i in range(_stack(window).property("depth"))]


def _header(page):
    return page.property("globalToolBarItem")


def _scene_rect(item):
    top_left = item.mapToScene(QPointF(0, 0))
    return top_left.x(), top_left.y(), item.width(), item.height()


def _click(window, item):
    x, y, w, h = _scene_rect(item)
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                     QPointF(x + w / 2, y + h / 2).toPoint())


def _open_details(window, name="pkg1"):
    call(window, "openPackageDetails", name)
    assert wait_until(lambda: _stack(window).property("depth") == 2)
    spin(100)  # fitHeaders runs on Qt.callLater


def _key(window, key, modifier=Qt.KeyboardModifier.NoModifier):
    window.requestActivate()
    assert wait_until(window.isActive, 2)
    QTest.keyClick(window, key, modifier)


# ── title bar ────────────────────────────────────────────────────────

def test_window_has_no_system_frame(ui):
    _, window, problems = ui
    assert window.flags() & Qt.WindowType.FramelessWindowHint
    assert problems() == []


def test_window_buttons_are_named_for_screen_readers(ui):
    _, window, problems = ui
    controls = by_name(window, "windowControls")
    assert attached(controls, "Accessible.name") == "Window"
    names = [attached(by_name(window, n), "Accessible.name")
             for n in ("minimizeButton", "maximizeButton", "closeButton")]
    assert names == ["Minimize", "Maximize", "Close"]
    # Top-right corner, all three in a row.
    x, y, w, _ = _scene_rect(controls)
    # Top-right corner, inset a few pixels so the hover pills clear the rounded edge.
    assert 0 <= y <= 2 and 0 <= window.width() - (x + w) <= 6
    assert problems() == []


def test_maximize_switches_to_restore_and_drops_the_frame(ui):
    _, window, problems = ui
    button = by_name(window, "maximizeButton")
    grips = find_items(window, lambda i: i.objectName() == "resizeGrip")
    edge = by_name(window, "windowEdge")
    assert len(grips) == 8 and all(g.isVisible() for g in grips) and edge.isVisible()

    call(window, "toggleMaximized")
    assert wait_until(lambda: button.property("text") == "Restore")
    assert button.property("iconName") == "window-restore"
    assert attached(button, "Accessible.name") == "Restore"
    assert not any(g.isVisible() for g in grips) and not edge.isVisible()

    call(window, "toggleMaximized")
    assert wait_until(lambda: button.property("text") == "Maximize")
    assert button.property("iconName") == "window-maximize"
    assert all(g.isVisible() for g in grips) and edge.isVisible()
    assert problems() == []


def test_rightmost_header_leaves_room_for_the_window_buttons(ui):
    controller, window, problems = ui
    _scan(controller)
    spin(100)
    controls = by_name(window, "windowControls")
    [only] = _columns(window)
    assert _header(only).property("rightPadding") >= controls.width()

    _open_details(window)
    first, details = _columns(window)
    assert _header(details).property("rightPadding") >= controls.width()
    # The list column's header is no longer under the buttons.
    assert _header(first).property("rightPadding") == evaluate(window, "Kirigami.Units.mediumSpacing")
    assert problems() == []


def test_header_buttons_stay_clear_of_the_window_buttons(ui):
    controller, window, problems = ui
    _scan(controller)
    controls_x = _scene_rect(by_name(window, "windowControls"))[0]
    checked = 0
    for key in PAGES:
        controller.navigate(key)
        spin(150)
        header = _header(_columns(window)[-1])
        buttons = find_items(window, lambda i: i.isVisible() and _inside(i, header)
                             and i.metaObject().indexOfProperty("display") >= 0)
        for button in buttons:
            x, _, w, _ = _scene_rect(button)
            assert x + w <= controls_x + 0.5, (key, button.property("text"))
            checked += 1
    assert checked >= 10  # every page but Settings has header actions
    assert problems() == []


def _inside(item, ancestor):
    while item is not None:
        if item == ancestor:
            return True
        item = item.parentItem()
    return False


def test_every_header_gets_exactly_one_drag_handle(ui):
    controller, window, problems = ui
    _scan(controller)
    spin(100)

    def handles(page):
        return [c for c in _header(page).childItems() if c.objectName() == "moveHandle"]
    for _ in range(3):  # reopening details must not stack handles
        _open_details(window)
        assert [len(handles(p)) for p in _columns(window)] == [1, 1]
        call(window, "closeColumns")
        spin(100)
    controller.navigate("installed")
    spin(100)
    controller.navigate("updates")
    spin(100)
    assert [len(handles(p)) for p in _columns(window)] == [1]
    assert problems() == []


# ── sidebar ──────────────────────────────────────────────────────────

def test_sidebar_button_overrides_auto_collapse_until_the_width_crosses(ui):
    _, window, problems = ui
    sidebar = by_name(window, "sidebar")
    toggle = by_name(window, "sidebarToggle")
    assert sidebar.property("collapsed") is False
    assert attached(toggle, "Accessible.name") == "Collapse Sidebar"

    _click(window, toggle)
    assert wait_until(lambda: sidebar.property("collapsed") is True)
    assert sidebar.property("userCollapsed") is True
    assert attached(toggle, "Accessible.name") == "Expand Sidebar"

    window.resize(820, 700)   # below the compact width: auto-collapse takes over
    assert wait_until(lambda: sidebar.property("autoCollapsed") is True)
    assert sidebar.property("userCollapsed") is None
    assert sidebar.property("collapsed") is True

    spin(300)  # the collapse animation
    _click(window, toggle)    # expand anyway
    assert wait_until(lambda: sidebar.property("collapsed") is False)
    assert sidebar.property("userCollapsed") is False

    window.resize(1280, 800)  # back above: the override is dropped
    assert wait_until(lambda: sidebar.property("autoCollapsed") is False)
    assert sidebar.property("userCollapsed") is None
    assert sidebar.property("collapsed") is False
    assert problems() == []


# ── the status capsule ───────────────────────────────────────────────

def test_capsule_reserves_room_at_the_bottom_of_every_page(ui):
    controller, window, problems = ui
    bar = by_name(window, "activityBar")
    for key in PAGES:  # create every page
        controller.navigate(key)
        spin(80)
    pages = window.property("pagesByKey").toVariant()
    assert set(pages) == set(PAGES)
    assert not bar.isVisible() and window.property("bottomInset") == 0
    before = {key: page.property("bottomPadding") for key, page in pages.items()}

    controller.toggleActivity(False)          # the capsule, log closed
    controller._set(activityVisible=True)
    assert wait_until(bar.isVisible)
    reserved = bar.property("reservedHeight")
    assert reserved > 0 and window.property("bottomInset") == reserved
    for key, page in pages.items():
        assert page.property("bottomPadding") == before[key] + reserved, key

    controller.closeActivity()
    assert wait_until(lambda: not bar.isVisible())
    assert window.property("bottomInset") == 0
    assert {key: page.property("bottomPadding") for key, page in pages.items()} == before
    assert problems() == []


def test_ctrl_t_toggles_the_output(ui):
    controller, window, problems = ui
    assert not controller.activityExpanded
    _key(window, Qt.Key.Key_T, Qt.KeyboardModifier.ControlModifier)
    assert wait_until(lambda: controller.activityExpanded)
    assert controller.activityVisible
    _key(window, Qt.Key.Key_T, Qt.KeyboardModifier.ControlModifier)
    assert wait_until(lambda: not controller.activityExpanded)
    assert problems() == []


def test_ctrl_numbers_switch_pages_and_ctrl_8_opens_the_output(ui):
    controller, window, problems = ui
    _key(window, Qt.Key.Key_4, Qt.KeyboardModifier.ControlModifier)
    assert wait_until(lambda: controller.currentPage == "sysinfo")
    assert wait_until(lambda: call(window, "columnTitles") == "System")
    _key(window, Qt.Key.Key_8, Qt.KeyboardModifier.ControlModifier)
    assert wait_until(lambda: controller.activityExpanded)
    assert controller.currentPage == "sysinfo"
    assert problems() == []


def test_escape_closes_the_log_or_the_column_by_where_focus_is(ui):
    """With the log open, Esc closes whatever holds the focus: the details
    column from the column, the log from any control in the log pane."""
    controller, window, problems = ui
    _scan(controller)
    controller.toggleActivity(True)
    _open_details(window)
    _key(window, Qt.Key.Key_Escape)  # focus is in the details column
    assert wait_until(lambda: call(window, "columnTitles") == "Updates")
    assert controller.activityExpanded

    _open_details(window)
    controller.runner.append("some output")
    copy = find_items(window, lambda i: i.property("text") == "Copy Output")
    assert copy
    copy[0].forceActiveFocus()
    assert wait_until(lambda: window.activeFocusItem() == copy[0])
    _key(window, Qt.Key.Key_Escape)  # focus is on a button in the log pane
    assert wait_until(lambda: not controller.activityExpanded)
    assert call(window, "columnTitles") == "Updates | pkg1"

    controller.toggleActivity(True)
    call(window, "closeColumns")
    assert wait_until(lambda: _stack(window).property("depth") == 1)
    _key(window, Qt.Key.Key_Escape)  # no column to close: the log closes
    assert wait_until(lambda: not controller.activityExpanded)
    assert problems() == []
