// Installed: browse what's installed (instant filter), or search the
// repositories for something new (explicit search, never per keystroke).
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page

    readonly property var p: App.Packages
    property string mode: "installed"   // installed | find
    readonly property var sortLabels: ({ "name": "Name (A–Z)", "name_desc": "Name (Z–A)", "repo": "Repository" })

    title: "Installed"

    actions: [
        Kirigami.Action {
            text: "Refresh"
            icon.source: root.ico("view-refresh", enabled)
            enabled: !page.p.loading
            onTriggered: page.p.refresh()
        },
        Kirigami.Action {
            text: "Sort: " + page.sortLabels[page.p.sort]
            icon.source: root.ico("view-sort", enabled)
            visible: page.mode === "installed"
            Kirigami.Action { text: "Name (A–Z)"; checkable: true; checked: page.p.sort === "name"; onTriggered: page.p.setSort("name") }
            Kirigami.Action { text: "Name (Z–A)"; checkable: true; checked: page.p.sort === "name_desc"; onTriggered: page.p.setSort("name_desc") }
            Kirigami.Action { text: "Repository"; checkable: true; checked: page.p.sort === "repo"; onTriggered: page.p.setSort("repo") }
        }
    ]

    function focusSearch() {
        search.forceActiveFocus();
        search.selectAll();
    }

    header: QQC2.ToolBar {
        position: QQC2.ToolBar.Header
        leftPadding: root.gutter
        rightPadding: root.gutter
        topPadding: Kirigami.Units.largeSpacing
        bottomPadding: Kirigami.Units.largeSpacing
        contentItem: RowLayout {
            spacing: Kirigami.Units.largeSpacing
            RowLayout {
                spacing: 0
                Repeater {
                    model: [
                        { key: "installed", label: "Installed" },
                        { key: "find", label: "Find Packages" }
                    ]
                    delegate: FilterChip {
                        required property var modelData
                        active: page.mode === modelData.key
                        text: modelData.key === "installed" && page.p.installed.count > 0
                              && page.mode === "installed" && page.p.installed.query === ""
                              ? "Installed (" + page.p.installed.count + ")" : modelData.label
                        Accessible.name: modelData.label
                        onClicked: {
                            page.mode = modelData.key;
                            if (modelData.key === "installed") {
                                search.text = page.p.installed.query;
                            } else {
                                search.text = page.p.searchQuery;
                                search.forceActiveFocus();
                            }
                        }
                    }
                }
            }
            Kirigami.SearchField {
                id: search
                Layout.fillWidth: true
                Layout.maximumWidth: Kirigami.Units.gridUnit * 18
                Layout.preferredWidth: Kirigami.Units.gridUnit * 18
                placeholderText: page.mode === "installed" ? "Filter installed packages…"
                                                           : "Search Fedora's repositories, then press Enter…"
                Accessible.name: page.mode === "installed" ? "Filter installed packages" : "Search repositories"
                // Installed filters as you type; Find searches on Enter.
                autoAccept: page.mode === "installed"
                delaySearch: false
                onAccepted: page.mode === "installed" ? page.p.installed.query = text : page.p.search(text)
                onTextChanged: if (page.mode === "installed") page.p.installed.query = text
                KeyNavigation.down: list
            }
            QQC2.Button {
                visible: page.mode === "find"
                text: "Search"
                icon.source: root.ico("search", enabled)
                enabled: search.text.trim().length >= 2 && !page.p.searching
                onClicked: page.p.search(search.text)
            }
            Item { Layout.fillWidth: true }
        }
    }

    ListView {
        id: list
        model: page.mode === "installed" ? page.p.installed : page.p.results
        currentIndex: -1
        keyNavigationEnabled: true
        activeFocusOnTab: true
        Accessible.name: page.mode === "installed" ? "Installed Packages" : "Search Results"

        delegate: PackageRow {
            width: ListView.view.width
            findMode: page.mode === "find"
        }

        Kirigami.LoadingPlaceholder {
            anchors.centerIn: parent
            visible: page.mode === "installed" ? page.p.loading : page.p.searching
            text: page.mode === "installed" ? "Loading Installed Packages…" : "Searching…"
        }
        Kirigami.PlaceholderMessage {
            anchors.centerIn: parent
            width: parent.width - Kirigami.Units.gridUnit * 4
            visible: list.count === 0 && !(page.mode === "installed" ? page.p.loading : page.p.searching)
            icon.source: root.ico(page.mode === "find" && !page.p.searchDone ? "search" : "edit-find", enabled)
            text: page.mode === "installed"
                  ? (page.p.error !== "" ? "Couldn't List Packages"
                     : page.p.installed.query !== "" ? "No Installed Packages Match" : "Nothing Loaded Yet")
                  : (page.p.searchDone ? "No Packages Found" : "Find Something New")
            explanation: page.mode === "installed"
                  ? (page.p.error || (page.p.installed.query !== ""
                     ? "Try another name, or search the repositories instead." : ""))
                  : (page.p.searchDone ? "Nothing in your enabled repositories matches “" + page.p.searchQuery + "”."
                     : "Search by name or description across every enabled repository.")
            helpfulAction: Kirigami.Action {
                enabled: page.mode === "installed" && page.p.installed.query !== ""
                text: "Search Repositories for “" + page.p.installed.query + "”"
                icon.source: root.ico("search", enabled)
                onTriggered: {
                    const q = page.p.installed.query;
                    page.mode = "find";
                    search.text = q;
                    page.p.search(q);
                }
            }
        }
    }
}
