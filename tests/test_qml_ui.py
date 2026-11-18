"""Load the real Kirigami UI offscreen and use its pages.

Every test fails on any QML warning or error (a missing property, a typo in
a binding, a page that doesn't load). The window chrome, sidebar, capsule
and keyboard shortcuts are in test_qml_window.py.
"""

from PyQt6.QtCore import QMetaObject, QObject, Qt
from PyQt6.QtQuick import QQuickItem

from dnf_gui.core.package import Package, PackageStatus, UpdateInfo
from dnf_gui.core.release_upgrade import ReleaseUpgrade
from tests.conftest import (
    attached, call, evaluate, find_items, items, spin, wait_until,
)

PAGE_TITLES = {
    "updates": "Updates", "installed": "Installed", "flatpak": "Flatpak",
    "sysinfo": "System", "tools": "Tools", "repos": "Repositories",
    "history": "History", "settings": "Settings",
}


def _titles(window) -> str:
    return call(window, "columnTitles")


def _scan(n: int = 3, reboot=True, security=None) -> dict:
    pkgs = [Package(f"pkg{i}", "1.1", "1.fc45", "x86_64", "updates",
                    status=PackageStatus.UPDATE_AVAILABLE, installed_version="1.0-1.fc45")
            for i in range(n)]
    return {"dnf": UpdateInfo(n, pkgs), "flatpak": [], "security": security,
            "preview": None, "security_preview": None, "reboot": reboot}


def _focus_chain(window) -> list:
    item, titles = window.activeFocusItem(), []
    while item is not None:
        titles.append(item.property("title"))
        item = item.parentItem()
    return titles


def test_every_page_loads_without_qml_warnings(ui):
    controller, window, problems = ui
    for key, title in PAGE_TITLES.items():
        controller.navigate(key)
        assert wait_until(lambda: _titles(window) == title), key
        spin(100)  # let the page's sample data arrive and render
    assert problems() == []


def test_update_rows_and_details_column(ui):
    controller, window, problems = ui
    pkg = Package("firefox", "146.0.1", "1.fc45", "x86_64", "updates",
                  status=PackageStatus.UPDATE_AVAILABLE, installed_version="145.0-1.fc45")
    controller.updates._on_checked({"dnf": UpdateInfo(1, [pkg]), "flatpak": [],
                                    "security": None, "preview": None,
                                    "security_preview": None, "reboot": True})
    assert controller.updates.phase == "ready"
    assert controller.updates.filtered.count == 1
    call(window, "openPackageDetails", "firefox")
    assert wait_until(lambda: _titles(window) == "Updates | firefox")
    controller.navigate("installed")
    assert wait_until(lambda: _titles(window) == "Installed")  # columns close when leaving
    assert problems() == []


def test_opening_details_moves_keyboard_focus_there(ui):
    controller, window, problems = ui
    controller.updates._on_checked(_scan())
    spin(100)
    call(window, "openPackageDetails", "pkg1")
    assert wait_until(lambda: "pkg1" in _focus_chain(window))
    call(window, "closeColumns")
    assert wait_until(lambda: "Updates" in _focus_chain(window))
    assert problems() == []


def test_prompt_dialog_and_output_render(ui):
    controller, window, problems = ui
    controller.prompts.confirm("Remove Package?", "Remove htop?", lambda: None,
                               destructive=True, details=["htop-3.4.1-2.fc45"])
    dialog = [o for o in window.findChildren(QObject)
              if o.metaObject().indexOfProperty("hasPrompt") >= 0]
    assert len(dialog) == 1
    assert wait_until(lambda: dialog[0].property("opened") is True)
    assert dialog[0].property("title") == "Remove Package?"
    controller.prompts.reply(controller.prompts.current["token"], "no")
    assert wait_until(lambda: dialog[0].property("opened") is False)

    controller.runner.append("line one\nline two")
    controller.toggleActivity(True)
    bar = [i for i in find_items(window, lambda i: i.objectName() == "activityBar")][0]
    assert wait_until(bar.isVisible)
    log = find_items(window, lambda i: i.property("readOnly") is True
                     and "line two" in str(i.property("text") or ""))
    assert log and log[0].isVisible()
    assert problems() == []


def test_up_to_date_and_failed_states(ui):
    controller, window, problems = ui
    controller.updates._on_checked({"dnf": UpdateInfo(), "flatpak": [], "security": None})
    spin()
    assert controller.updates.phase == "uptodate"
    failed = UpdateInfo()
    failed.check_failed = True
    controller.updates._on_checked({"dnf": failed, "flatpak": [], "security": None})
    spin()
    assert controller.updates.phase == "failed"
    assert "Up to Date" not in controller.updates.headline
    assert problems() == []


def _focused_page_title(window) -> str:
    for title in _focus_chain(window):
        if isinstance(title, str) and title in PAGE_TITLES.values():
            return title
    return ""


def test_ctrl_f_focuses_the_visible_pages_field(ui):
    controller, window, problems = ui
    controller.updates._on_checked(_scan())
    for key in ("installed", "flatpak", "repos", "history", "updates"):
        controller.navigate(key)   # every page now exists, hidden or not
        spin()
    for key in ("repos", "updates", "installed", "history"):
        controller.navigate(key)
        spin()
        controller.focusSearch()
        assert wait_until(lambda: _focused_page_title(window) == PAGE_TITLES[key]), key
    assert problems() == []


def test_show_all_updates_clears_the_filter(ui):
    controller, window, problems = ui
    controller.updates._on_checked(_scan())
    spin()
    controller.updates.filtered.query = "zzzz"
    controller.updates.filtered.category = "security"
    spin()
    updates_page = next(p for p in window.findChildren(QQuickItem)
                        if p.property("title") == "Updates"
                        and p.metaObject().indexOfMethod("showAllUpdates()") >= 0)
    QMetaObject.invokeMethod(updates_page, "showAllUpdates", Qt.ConnectionType.DirectConnection)
    assert controller.updates.filtered.query == ""
    assert controller.updates.filtered.category == "all"
    assert controller.updates.filtered.count == 3
    assert problems() == []


def _update_list(window):
    return find_items(window, lambda i: i.property("shownPhase") is not None)[0]


def test_summary_stays_at_the_top_when_results_arrive(ui):
    controller, window, problems = ui
    spin()
    controller.updates._on_checked(_scan(40))
    spin(700)   # past the settle window
    view = _update_list(window)
    assert abs(view.property("contentY") - view.property("originY")) < 1
    assert problems() == []


def test_scrolling_down_is_not_pulled_back_to_the_top(ui):
    controller, window, problems = ui
    controller.updates._on_checked(_scan(120))
    spin(900)   # past the settle window
    view = _update_list(window)
    assert abs(view.property("contentY") - view.property("originY")) < 1
    view.setProperty("contentY", view.property("originY") + 600)
    spin(300)   # delegates get created and contentHeight is re-estimated
    assert view.property("contentY") > view.property("originY") + 300
    assert problems() == []


def test_collapsed_sidebar_keeps_its_icons(ui):
    controller, window, problems = ui
    window.resize(820, 700)   # below the compact width
    spin(300)
    nav = find_items(window, lambda i: i.property("key") == "updates"
                     and i.property("collapsed") is not None)
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
    assert problems() == []


def test_cancel_hidden_for_downloads_that_cannot_be_cancelled(ui):
    controller, window, problems = ui
    fake = type("W", (), {"isRunning": lambda self: True})()
    controller.runner.start_external("Downloading app update", fake)
    controller.toggleActivity(True)
    spin(150)
    cancel = find_items(window, lambda i: i.property("text") == "Cancel"
                        and i.property("cancellable") is None and i.property("flat") is not None)
    assert cancel and not any(c.isVisible() for c in cancel)
    controller.runner.finish_external(True)
    assert problems() == []


def test_output_log_is_readable_text(ui):
    controller, window, problems = ui
    controller.toggleActivity(True)
    controller.runner.append("✗ Step failed (exit 1)")
    spin(150)
    areas = find_items(window, lambda i: i.property("readOnly") is True
                       and "Step failed" in str(i.property("text") or ""))
    assert areas, "the log should be a read-only text area screen readers can move through"
    assert areas[0].property("activeFocusOnTab") is True
    assert problems() == []


def test_flathub_error_is_not_shown_as_no_results(ui):
    controller, window, problems = ui
    controller.navigate("flatpak")
    spin(200)
    page = next(p for p in find_items(window, lambda i: i.property("title") == "Flatpak"
                                      and i.property("mode") is not None))
    page.setProperty("mode", "find")
    controller.prompts.auto_answer = lambda prompt: prompt.default
    controller.flatpak._search_generation = 1
    controller.flatpak._on_search_error(1, "network unreachable")

    def placeholder():
        return [i for i in items(page) if i.isVisible()
                and i.metaObject().indexOfProperty("explanation") >= 0]
    assert wait_until(lambda: [p.property("text") for p in placeholder()] == ["Couldn't Search Flathub"])
    assert placeholder()[0].property("explanation") == "network unreachable"
    controller.flatpak.search("")   # clearing the box clears the error
    assert wait_until(lambda: [p.property("text") for p in placeholder()] == ["Find Apps on Flathub"])
    assert problems() == []


# ── Settings ─────────────────────────────────────────────────────────

def test_reminder_switch_saves_from_any_toggle_but_not_on_load(ui):
    controller, window, problems = ui
    controller.settings.reminders_enabled = False
    controller.navigate("settings")
    spin(300)
    assert controller.prompts.notices == []        # opening Settings saves nothing
    switch = find_items(window, lambda i: i.property("text") == "Remind me about pending updates")[0]
    # What a screen reader's toggle action does: toggle() flips `checked`
    # and (on Qt 6.11) emits no toggled() signal.
    QMetaObject.invokeMethod(switch, "toggle", Qt.ConnectionType.DirectConnection)
    assert wait_until(lambda: controller.settings.reminders_enabled is True)
    assert problems() == []


def test_opening_settings_keeps_non_default_reminder_choices(ui):
    """Saved values that differ from the defaults must survive opening
    Settings (switches update one at a time from the controller)."""
    controller, window, problems = ui
    settings = controller.settings
    settings.reminders_enabled = True
    settings.security_only = True
    settings.notify_flatpak = False
    settings.check_interval_hours = 72
    controller.navigate("settings")
    spin(400)
    assert (settings.reminders_enabled, settings.security_only,
            settings.notify_flatpak, settings.check_interval_hours) == (True, True, False, 72)
    assert controller.prompts.notices == []
    # A real change saves just that field.
    switch = find_items(window, lambda i: i.property("text") == "Include Flatpak updates"
                        and i.property("checkable") is True)[0]
    assert switch.property("checked") is False   # shows the saved value
    QMetaObject.invokeMethod(switch, "toggle", Qt.ConnectionType.DirectConnection)
    assert wait_until(lambda: settings.notify_flatpak is True)
    assert (settings.reminders_enabled, settings.security_only,
            settings.notify_flatpak, settings.check_interval_hours) == (True, True, True, 72)
    assert problems() == []


# ── notices ──────────────────────────────────────────────────────────

def _notices(window):
    return [i for i in find_items(window, lambda i: i.property("tone") is not None
                                  and i.metaObject().indexOfProperty("dismissAction") >= 0)
            if i.isVisible()]


def _show_every_notice(controller):
    from types import SimpleNamespace

    from tests.test_security import _blocked_summary
    controller.updates._on_checked(_scan(reboot=True, security=_blocked_summary()))
    controller.updates.set_release_upgrade(ReleaseUpgrade(44, 45, "2027-06-02"))
    controller._on_app_update_checked(SimpleNamespace(
        latest_version="2.0.1", download_url="https://github.com/x/y.rpm", sha256="ab" * 32,
        release_url="", release_notes=""))


def _plain(notice, item) -> bool:
    return evaluate(item, "textFormat === Text.PlainText") is True


def test_every_notice_reads_as_one_plain_alert(ui):
    """A notice is one alert with its title as the name and its body as the
    description; none of its text is read as markup."""
    controller, window, problems = ui
    _show_every_notice(controller)
    assert wait_until(lambda: len(_notices(window)) == 4)
    titles = {n.property("title") for n in _notices(window)}
    assert titles == {"Restart to finish updating", "DNF Package Manager 2.0.1 is available",
                      "Fedora 45 is available", "1 security advisory waiting on RPM Fusion"}
    for notice in _notices(window):
        title, body = notice.property("title"), notice.property("body")
        assert title and body, title
        assert evaluate(notice, "Accessible.role === Accessible.AlertMessage") is True
        assert attached(notice, "Accessible.name") == title
        assert attached(notice, "Accessible.description") == body
        texts = [i for i in items(notice) if i.metaObject().indexOfProperty("textFormat") >= 0
                 and i.metaObject().indexOfProperty("elide") >= 0]
        assert texts and all(_plain(notice, t) for t in texts), title
        names = [str(attached(i, "Accessible.name") or "") for i in items(notice)]
        assert not [n for n in names if "<" in n], title
        # Every button inside has words; icon-only ones say them as their name.
        buttons = [i for i in items(notice) if i.isVisible()
                   and i.metaObject().indexOfProperty("display") >= 0]
        assert buttons and all(b.property("text") for b in buttons), title
        for button in buttons:
            if evaluate(button, "display === QQC2.AbstractButton.IconOnly"):
                assert attached(button, "Accessible.name") == button.property("text"), title
    # The restart notice's dismiss button is icon-only but keeps its words.
    restart = next(n for n in _notices(window) if n.property("title") == "Restart to finish updating")
    later = [i for i in items(restart) if i.property("text") == "Later" and i.isVisible()
             and i.metaObject().indexOfProperty("display") >= 0]
    assert later and attached(later[0], "Accessible.name") == "Later"
    assert problems() == []


def test_notice_details_button_is_named_and_unfolds_the_body(ui):
    controller, window, problems = ui
    window.resize(820, 700)   # narrow: every body folds behind the chevron
    _show_every_notice(controller)
    assert wait_until(lambda: len(_notices(window)) == 4)
    spin(300)
    for notice in _notices(window):
        [chevron] = [i for i in items(notice) if i.objectName() == "noticeExpand"]
        assert chevron.isVisible(), notice.property("title")
        assert attached(chevron, "Accessible.name") == "Show Details"
        QMetaObject.invokeMethod(chevron, "click", Qt.ConnectionType.DirectConnection)
        assert wait_until(lambda: notice.property("expanded") is True)
        assert attached(chevron, "Accessible.name") == "Hide Details"
        body = [i for i in items(notice) if i.isVisible() and i.property("text") == notice.property("body")
                and i.metaObject().indexOfProperty("wrapMode") >= 0]
        assert body, notice.property("title")
    assert problems() == []


def test_markup_from_dnf_is_shown_literally(ui):
    controller, window, problems = ui
    controller.updates._on_checked(_scan(reboot=False))
    controller.updates._set(blocked={"visible": True, "title": "<b>libheif</b> is waiting",
                                     "text": "dnf said <i>no</i> & <a href='x'>more</a>"})
    assert wait_until(lambda: len(_notices(window)) == 1)
    [notice] = _notices(window)
    assert attached(notice, "Accessible.name") == "<b>libheif</b> is waiting"
    shown = [i.property("text") for i in items(notice) if i.isVisible()
             and i.metaObject().indexOfProperty("textFormat") >= 0]
    assert "<b>libheif</b> is waiting" in shown
    assert all(_plain(notice, i) for i in items(notice)
               if i.metaObject().indexOfProperty("textFormat") >= 0
               and i.metaObject().indexOfProperty("elide") >= 0)
    assert problems() == []
