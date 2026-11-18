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
    // One spacing scale for every page: the page edge (cards, list rows,
    // section headers, page toolbars) sits this far in.
    readonly property real gutter: compact ? Kirigami.Units.largeSpacing : Kirigami.Units.largeSpacing * 2
    // Secondary text: the text color blended toward the background
    // (scripts/check_contrast.py SECONDARY_MIX).
    readonly property real secondaryMix: 0.3
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

    // ── The app's own title bar ──
    // No system frame: the sidebar runs to the top, the page header is the
    // title bar (drag to move, double-click to maximize), and the window
    // buttons sit at its right end.
    flags: Qt.Window | Qt.FramelessWindowHint

    // Rounded window: a transparent surface with our own rounded background.
    // The sidebar sits on the window color; the pages run to the window's
    // edges on their own background, with one divider from the sidebar.
    // Square when maximized.
    readonly property bool maximizedLook: windowControls.maximized
    readonly property real windowRadius: maximizedLook ? 0 : Kirigami.Units.gridUnit * 0.6
    readonly property color hairline: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                                              Kirigami.Theme.textColor.b, 0.12)
    color: "transparent"
    background: Rectangle {
        color: Kirigami.Theme.backgroundColor
        radius: root.windowRadius
    }
    Rectangle {
        id: contentPanel
        objectName: "contentPanel"
        parent: root.pageStack.parent
        z: root.pageStack.z - 1
        x: root.pageStack.x
        y: root.pageStack.y
        width: root.pageStack.width
        height: root.pageStack.height
        // Its right-hand corners follow the window's.
        topRightRadius: root.windowRadius
        bottomRightRadius: root.windowRadius
        Kirigami.Theme.colorSet: Kirigami.Theme.View
        Kirigami.Theme.inherit: false
        color: Kirigami.Theme.backgroundColor
        Rectangle {  // the one divider between the sidebar and the pages
            width: 1
            height: parent.height
            color: root.hairline
        }
    }
    // Kirigami draws a line along the top of each header (meant to sit under
    // a system title bar); in a frameless window it's a stray line.
    function hideTopSeparator(header) {
        for (const child of header.children)
            if (String(child).indexOf("Separator") >= 0)
                child.visible = false;
    }
    function toggleMaximized() {
        if (visibility === Window.Maximized)
            showNormal();
        else
            showMaximized();
    }
    // Drag/double-click handling, attached behind a header's own controls.
    Component {
        id: moveHandle
        Item {
            objectName: "moveHandle"
            anchors.fill: parent
            z: -1
            DragHandler {
                target: null
                onActiveChanged: if (active) root.startSystemMove()
            }
            TapHandler {
                acceptedButtons: Qt.LeftButton
                onDoubleTapped: root.toggleMaximized()
            }
        }
    }
    // The rightmost header leaves room for the window buttons; each header
    // also becomes a drag handle.
    property var movableHeaders: []
    function fitHeaders() {
        for (let i = 0; i < pageStack.depth; ++i) {
            const header = pageStack.get(i).globalToolBarItem;
            if (!header)
                continue;
            if (!movableHeaders.includes(header)) {
                moveHandle.createObject(header);
                movableHeaders.push(header);
                hideTopSeparator(header);
                if (header.background)
                    header.background.color = "transparent";  // the panel shows through
            }
            header.rightPadding = i === pageStack.depth - 1
                ? windowControls.width + windowControls.anchors.rightMargin + Kirigami.Units.smallSpacing
                : Kirigami.Units.mediumSpacing;
        }
    }
    Connections {
        target: root.pageStack
        function onDepthChanged() { Qt.callLater(root.fitHeaders); }
        function onCurrentItemChanged() { Qt.callLater(root.fitHeaders); }
    }

    pageStack.defaultColumnWidth: Kirigami.Units.gridUnit * 28
    // Dynamic columns honor each list's width and its draggable divider
    // (Kirigami's default fixes every column at defaultColumnWidth).
    Binding {
        target: root.pageStack.columnView
        property: "columnResizeMode"
        value: root.pageStack.wideMode ? Kirigami.ColumnView.DynamicColumns
                                       : Kirigami.ColumnView.SingleColumn
    }
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
        // Pages are transparent: the rounded content panel is their background.
        if (page && page.background)
            page.background = null;
        // The activity capsule floats over the pages' bottom edge: give
        // every page room to scroll its last row clear of it.
        if (page && page.bottomPadding !== undefined) {
            const base = page.bottomPadding;
            page.bottomPadding = Qt.binding(() => base + root.bottomInset);
        }
        return page;
    }
    // Width of a list beside its details column: drag the divider to change
    // it (Updates, Installed, History share it); remembered across launches.
    property real listColumnWidth: App.listColumnWidth > 0 ? App.listColumnWidth
                                                           : Kirigami.Units.gridUnit * 30
    function rememberListWidth(width) {
        if (width > 0 && Math.abs(width - listColumnWidth) >= 1) {
            listColumnWidth = width;
            saveListWidth.restart();
        }
    }
    Timer {
        id: saveListWidth
        interval: 500
        onTriggered: App.saveListColumnWidth(Math.round(root.listColumnWidth))
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
        objectName: "sidebar"
        autoCollapsed: root.compact
    }

    // Activity bar under the pages (not the window footer, which Kirigami
    // lays out under the sidebar).
    ActivityBar {
        id: activity
        objectName: "activityBar"
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

    // Window chrome above everything: buttons, resize grips, the edge.
    Item {
        id: chrome
        parent: root.contentItem.parent
        anchors.fill: parent
        z: 1000

        WindowControls {
            id: windowControls
            objectName: "windowControls"
            z: 1000
            anchors.top: parent.top
            anchors.right: parent.right
            anchors.topMargin: 1
            anchors.rightMargin: Kirigami.Units.smallSpacing
            height: root.pageStack.globalToolBar.preferredHeight - 2
        }

        // Resize from the edges and corners (no system frame to grab).
        Repeater {
            model: [
                { e: Qt.TopEdge, c: Qt.SizeVerCursor }, { e: Qt.BottomEdge, c: Qt.SizeVerCursor },
                { e: Qt.LeftEdge, c: Qt.SizeHorCursor }, { e: Qt.RightEdge, c: Qt.SizeHorCursor },
                { e: Qt.TopEdge | Qt.LeftEdge, c: Qt.SizeFDiagCursor },
                { e: Qt.BottomEdge | Qt.RightEdge, c: Qt.SizeFDiagCursor },
                { e: Qt.TopEdge | Qt.RightEdge, c: Qt.SizeBDiagCursor },
                { e: Qt.BottomEdge | Qt.LeftEdge, c: Qt.SizeBDiagCursor }
            ]
            delegate: Item {
                required property var modelData
                objectName: "resizeGrip"
                readonly property int edges: modelData.e
                readonly property real grip: Kirigami.Units.smallSpacing * 1.5
                readonly property bool corner: (edges & (Qt.TopEdge | Qt.BottomEdge))
                                               && (edges & (Qt.LeftEdge | Qt.RightEdge))
                z: 1001
                visible: !windowControls.maximized
                x: (edges & Qt.RightEdge) ? parent.width - (corner ? grip * 3 : grip)
                 : (edges & Qt.LeftEdge) ? 0 : grip * 3
                y: (edges & Qt.BottomEdge) ? parent.height - (corner ? grip * 3 : grip)
                 : (edges & Qt.TopEdge) ? 0 : grip * 3
                width: corner ? grip * 3 : (edges & (Qt.LeftEdge | Qt.RightEdge)) ? grip : parent.width - grip * 6
                height: corner ? grip * 3 : (edges & (Qt.TopEdge | Qt.BottomEdge)) ? grip : parent.height - grip * 6
                HoverHandler { cursorShape: modelData.c }
                DragHandler {
                    target: null
                    onActiveChanged: if (active) root.startSystemResize(edges)
                }
            }
        }

        // A hairline edge, since there's no system frame or border.
        Rectangle {
            objectName: "windowEdge"
            z: 999
            anchors.fill: parent
            visible: !windowControls.maximized
            color: "transparent"
            radius: root.windowRadius
            border.width: 1
            border.color: root.hairline
        }
    }

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
