// DNF Package Manager: the application window.
// `App` is the Python AppController (context property); pages bind to its
// child controllers (App.Updates, App.Packages, ...).
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ApplicationWindow {
    id: root

    readonly property bool compact: width < Kirigami.Units.gridUnit * 50
    readonly property var pageFiles: ({
        "updates": "UpdatesPage.qml", "installed": "InstalledPage.qml",
        "flatpak": "FlatpakPage.qml", "sysinfo": "SystemPage.qml",
        "tools": "ToolsPage.qml", "repos": "ReposPage.qml",
        "history": "HistoryPage.qml", "settings": "SettingsPage.qml"
    })

    // The app's own bold icons (ui/icons), drawn in the theme's colors:
    // ico("download", enabled) is a file URL, or "" for a name the app
    // doesn't ship.
    readonly property string iconBase: App.iconBaseFor(Kirigami.Theme.textColor)
    readonly property string iconBaseDisabled: App.iconBaseFor(Kirigami.Theme.disabledTextColor)
    readonly property var iconSet: {
        const names = {};
        for (const n of App.iconNames)
            names[n] = true;
        return names;
    }
    // Pass the control's own `enabled` (dimmed when false) and, for a
    // colored icon, its `color`: the file is drawn in that color.
    function ico(name, enabled, color) {
        if (!name || !iconSet[name])
            return "";
        const base = color !== undefined ? App.iconBaseFor(color)
                   : enabled === false ? iconBaseDisabled : iconBase;
        return base + name + ".svg";
    }

    title: "DNF Package Manager"
    width: Kirigami.Units.gridUnit * 64
    height: Kirigami.Units.gridUnit * 42
    minimumWidth: Kirigami.Units.gridUnit * 22
    minimumHeight: Kirigami.Units.gridUnit * 20

    pageStack.defaultColumnWidth: Kirigami.Units.gridUnit * 28
    pageStack.globalToolBar.style: Kirigami.ApplicationHeaderStyle.ToolBar
    pageStack.globalToolBar.showNavigationButtons: Kirigami.ApplicationHeaderStyle.ShowBackButton

    // Top-level pages are created once and kept:
    // coming back to a page keeps its scroll position and filters.
    // (PageRow would parent pages it creates to a non-visual object.)
    property var components: ({})
    property var pagesByKey: ({})
    function createPage(file, props) {
        let component = components[file];
        if (!component) {
            component = Qt.createComponent(Qt.resolvedUrl(file));
            components[file] = component;
        }
        if (component.status === Component.Error) {
            console.error(component.errorString());
            return null;
        }
        const page = component.createObject(pageHolder, props || {});
        // The activity capsule floats over the pages' bottom edge: give
        // every page room to scroll its last row clear of it.
        if (page && page.bottomPadding !== undefined) {
            const base = page.bottomPadding;
            page.bottomPadding = Qt.binding(() => base + root.bottomInset);
        }
        return page;
    }
    readonly property real bottomInset: activity.visible ? activity.reservedHeight : 0

    // Kirigami's ColumnView hands a removed page back to its original
    // parent; parking pages here keeps a removed page hidden.
    Item {
        id: pageHolder
        visible: false
    }

    // Detail columns are short-lived: destroyed after PageRow lets go.
    function popTo(depth) {
        while (pageStack.depth > depth) {
            const removed = pageStack.pop();
            if (removed && !Object.values(pagesByKey).includes(removed))
                Qt.callLater(() => removed.destroy());
        }
    }

    property string shownPage: ""
    function showPage(key) {
        const file = pageFiles[key];
        if (!file)
            return;
        shownPage = key;
        let page = pagesByKey[key];
        if (!page) {
            page = createPage(file);
            if (!page)
                return;
            pagesByKey[key] = page;
        }
        popTo(1);
        if (pageStack.depth === 0)
            pageStack.push(page);
        else if (pageStack.get(0) !== page)
            pageStack.replace(page);
    }

    // Open a details column next to the current list (or over it on
    // narrow windows). `file` is a QML file, `props` its properties.
    function openColumn(file, props) {
        popTo(1);
        const page = createPage(file, props);
        if (page) {
            pageStack.push(page);
            page.forceActiveFocus();  // keyboard and screen readers follow
        }
    }

    // Package details beside the list (Updates and Installed pages).
    function openPackageDetails(name) {
        App.Packages.loadDetails(name);
        openColumn("PackageDetailsPage.qml", { packageName: name });
    }

    // Titles of the visible columns (tests and screenshots use this).
    function columnTitles() {
        const titles = [];
        for (let i = 0; i < pageStack.depth; ++i)
            titles.push(pageStack.get(i).title);
        return titles.join(" | ");
    }

    function focusInActivity() {
        for (let it = root.activeFocusItem; it; it = it.parent)
            if (it === activity)
                return true;
        return false;
    }

    function closeColumns() {
        popTo(1);
        if (pageStack.depth > 0)
            pageStack.get(0).forceActiveFocus();  // back to the list
    }

    // Window close: the controller decides (an operation may be running).
    onClosing: (close) => { close.accepted = App.requestClose(); }

    Connections {
        target: App
        // App's properties share one notify signal: this runs on any App
        // change (the log opening, an operation starting), so act only
        // when the page really changed, or open details would close.
        function onCurrentPageChanged() {
            if (App.currentPage !== root.shownPage)
                root.showPage(App.currentPage);
        }
        function onFocusSearchRequested() {
            const page = root.pageStack.depth > 0 ? root.pageStack.get(0) : null;
            if (page && page.focusSearch)
                page.focusSearch();
        }
        function onErrorRaised(text) {
            root.showPassiveNotification(text, "long");
            root.pageStack.Accessible.announce(text);
        }
    }
    Connections {
        target: App.Prompts
        function onNotice(text) {
            root.showPassiveNotification(text);
            root.pageStack.Accessible.announce(text);
        }
    }

    globalDrawer: Sidebar {
        autoCollapsed: root.compact
    }

    // Activity bar under the pages (not the window footer, which Kirigami
    // lays out under the sidebar).
    ActivityBar {
        id: activity
        parent: root.pageStack.parent
        z: 10  // the open log floats over the page
        visible: App.activityVisible
        anchors {
            left: root.pageStack.left
            right: root.pageStack.right
            bottom: parent.bottom
        }
    }

    PromptDialog {}

    // ── Keyboard: window-level, routed to the current page ──
    Shortcut { sequence: "Ctrl+R"; onActivated: App.refreshCurrent() }
    Shortcut { sequences: [StandardKey.Find]; onActivated: App.focusSearch() }
    Shortcut { sequence: "Ctrl+U"; onActivated: App.runFavoriteUpdate() }
    Shortcut { sequence: "Ctrl+T"; onActivated: App.toggleActivity(!App.activityExpanded) }
    // Esc closes the output log when focus is in it (or there's no details
    // column to close), otherwise the details column.
    Shortcut {
        sequence: "Esc"
        enabled: root.pageStack.depth > 1 || App.activityExpanded
        onActivated: {
            if (App.activityExpanded && (root.focusInActivity() || root.pageStack.depth <= 1))
                activity.closeLog();
            else
                root.closeColumns();
        }
    }
    Repeater {
        model: 9
        delegate: Item {
            required property int index
            Shortcut {
                sequence: "Ctrl+" + (index + 1)
                onActivated: App.navigateIndex(index)
            }
        }
    }


    Component.onCompleted: showPage(App.currentPage)
}
