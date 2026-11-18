// Flatpak: installed apps (runtimes on request) and Flathub search.
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page

    readonly property var f: App.Flatpak
    property string mode: "installed"   // installed | find

    title: "Flatpak"

    actions: [
        Kirigami.Action {
            text: App.Updates.flatpakCount > 0 ? "Update All (" + App.Updates.flatpakCount + ")" : "Update All"
            icon.source: root.ico("download", enabled)
            enabled: page.f.available && !App.Runner.busy
            onTriggered: page.f.updateAll()
        },
        Kirigami.Action {
            text: "Refresh"
            icon.source: root.ico("view-refresh", enabled)
            enabled: page.f.available && !page.f.loading
            onTriggered: page.f.refresh()
        },
        Kirigami.Action {
            text: "Show Runtimes"
            icon.source: root.ico("view-list-details", enabled)
            checkable: true
            checked: page.f.showRuntimes
            displayHint: Kirigami.DisplayHint.AlwaysHide
            onTriggered: page.f.setShowRuntimes(checked)
        },
        Kirigami.Action {
            text: "Remove Unused Runtimes…"
            icon.source: root.ico("edit-clear-all", enabled)
            enabled: page.f.available && !App.Runner.busy
            displayHint: Kirigami.DisplayHint.AlwaysHide
            onTriggered: page.f.removeUnused()
        },
        Kirigami.Action {
            text: "Repair Installation…"
            icon.source: root.ico("tools-wizard", enabled)
            enabled: page.f.available && !App.Runner.busy
            displayHint: Kirigami.DisplayHint.AlwaysHide
            onTriggered: page.f.repair()
        }
    ]

    function focusSearch() {
        search.forceActiveFocus();
        search.selectAll();
    }

    header: QQC2.ToolBar {
        visible: page.f.available
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
                        { key: "find", label: "Find on Flathub" }
                    ]
                    delegate: FilterChip {
                        required property var modelData
                        active: page.mode === modelData.key
                        text: modelData.label
                        onClicked: {
                            page.mode = modelData.key;
                            if (modelData.key === "installed") {
                                search.text = page.f.installed.query;
                            } else {
                                search.text = page.f.searchQuery;
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
                placeholderText: page.mode === "installed" ? "Filter installed apps…"
                                                           : "Search Flathub, then press Enter…"
                Accessible.name: page.mode === "installed" ? "Filter installed apps" : "Search Flathub"
                autoAccept: page.mode === "installed"
                delaySearch: false
                onAccepted: page.mode === "installed" ? page.f.installed.query = text : page.f.search(text)
                onTextChanged: if (page.mode === "installed") page.f.installed.query = text
                KeyNavigation.down: list
            }
            QQC2.Button {
                visible: page.mode === "find"
                text: "Search"
                icon.source: root.ico("search", enabled)
                enabled: search.text.trim().length >= 2 && !page.f.searching
                onClicked: page.f.search(search.text)
            }
            Item { Layout.fillWidth: true }
        }
    }

    ListView {
        id: list
        model: page.mode === "installed" ? page.f.installed : page.f.results
        currentIndex: -1
        keyNavigationEnabled: true
        activeFocusOnTab: true
        Accessible.name: page.mode === "installed" ? "Installed Flatpak Apps" : "Flathub Results"
        section.property: page.mode === "installed" && page.f.showRuntimes ? "runtime" : ""
        section.delegate: SectionHeader {
            required property string section
            width: ListView.view.width
            text: section === "true" ? "Runtimes" : "Apps"
        }

        delegate: QQC2.ItemDelegate {
            id: row
            required property int index
            required property string name
            required property string appId
            required property string version
            required property string branch
            required property string origin
            required property string size
            required property string description
            required property bool runtime
            required property bool installed
            readonly property color dim: highlighted ? Kirigami.Theme.highlightedTextColor : Kirigami.ColorUtils.linearInterpolation(Kirigami.Theme.textColor, Kirigami.Theme.backgroundColor, 0.3)
            readonly property bool narrow: width < Kirigami.Units.gridUnit * 28

            width: ListView.view.width
            text: name
            highlighted: ListView.isCurrentItem
            leftPadding: root.gutter
            rightPadding: root.gutter
            topPadding: Kirigami.Units.largeSpacing
            bottomPadding: Kirigami.Units.largeSpacing
            Accessible.description: appId + (version ? ", version " + version : "")
            onClicked: ListView.view.currentIndex = index
            Keys.onMenuPressed: if (more.visible) menu.popup(more, 0, more.height)
            Accessible.onPressAction: clicked()
            // Re-evaluated after every scan (flatpakCount changes).
            readonly property bool hasUpdate: App.Updates.flatpakCount >= 0
                                              && App.Updates.flatpakHasUpdate(row.appId, row.branch)

            contentItem: RowLayout {
                spacing: Kirigami.Units.largeSpacing
                AppIcon {
                    name: row.name
                    appId: row.appId
                    runtime: row.runtime
                    Layout.preferredWidth: Kirigami.Units.iconSizes.medium
                    Layout.preferredHeight: Layout.preferredWidth
                }
                ColumnLayout {
                    spacing: Kirigami.Units.smallSpacing / 2
                    Layout.fillWidth: true
                    QQC2.Label {
                        text: row.name
                        font.weight: Font.DemiBold
                        elide: Text.ElideRight
                        color: row.highlighted ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.textColor
                        Layout.fillWidth: true
                    }
                    QQC2.Label {
                        text: page.mode === "find" && row.description !== "" ? row.description
                              : row.appId + (row.version ? "  ·  " + row.version : (row.branch ? "  ·  " + row.branch : ""))
                        elide: Text.ElideRight
                        color: row.dim
                        font: Kirigami.Theme.smallFont
                        Layout.fillWidth: true
                    }
                }
                // A status, not a button: these update with Update All.
                Pill {
                    visible: page.mode === "installed" && row.hasUpdate
                    text: "Update Available"
                    tone: "plain"
                    selected: row.highlighted
                }
                Pill {
                    visible: page.mode === "find" && row.installed
                    text: "Installed"
                    tone: "positive"
                    selected: row.highlighted
                }
                // Fixed width and tabular digits: sizes line up down the list.
                QQC2.Label {
                    visible: !row.narrow && (row.size !== "" || page.mode === "installed")
                    text: row.size
                    color: row.dim
                    font.pointSize: Kirigami.Theme.smallFont.pointSize
                    font.features: { "tnum": 1 }
                    horizontalAlignment: Text.AlignRight
                    elide: Text.ElideLeft
                    Layout.preferredWidth: Kirigami.Units.gridUnit * 4.5
                }
                QQC2.ToolButton {
                    visible: page.mode === "find" && !row.installed
                    text: "Install"
                    icon.source: root.ico("list-add", enabled)
                    display: row.narrow ? QQC2.AbstractButton.IconOnly : QQC2.AbstractButton.TextBesideIcon
                    enabled: !App.Runner.busy
                    Accessible.name: "Install " + row.name
                    onClicked: page.f.install(row.appId, row.origin)
                }
                QQC2.ToolButton {
                    id: more
                    visible: row.installed
                    icon.source: root.ico("overflow-menu", enabled)
                    text: "More Actions for " + row.name
                    display: QQC2.AbstractButton.IconOnly
                    QQC2.ToolTip.text: "More Actions"
                    QQC2.ToolTip.visible: hovered
                    QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay
                    onClicked: menu.popup(more, 0, more.height)
                    QQC2.Menu {
                        id: menu
                        QQC2.MenuItem {
                            visible: row.hasUpdate
                            height: visible ? implicitHeight : 0
                            text: "Update"
                            icon.source: root.ico("download", enabled)
                            enabled: !App.Runner.busy
                            onTriggered: page.f.updateApp(row.appId, row.branch)
                        }
                        QQC2.MenuItem { text: "Copy App ID"; icon.source: root.ico("edit-copy", enabled); onTriggered: App.copyText(row.appId) }
                        QQC2.MenuSeparator {}
                        QQC2.MenuItem {
                            text: "Remove…"
                            icon.source: root.ico("edit-delete", enabled)
                            enabled: !App.Runner.busy
                            onTriggered: page.f.remove(row.appId)
                        }
                    }
                }
            }
        }

        Kirigami.LoadingPlaceholder {
            anchors.centerIn: parent
            visible: page.mode === "installed" ? page.f.loading : page.f.searching
            text: page.mode === "installed" ? "Loading Flatpak Apps…" : "Searching Flathub…"
        }
        Kirigami.PlaceholderMessage {
            anchors.centerIn: parent
            width: parent.width - Kirigami.Units.gridUnit * 4
            visible: list.count === 0 && !(page.mode === "installed" ? page.f.loading : page.f.searching)
            icon.source: root.ico(!page.f.available ? "dialog-information" : "folder-flatpak", enabled)
            text: !page.f.available ? "Flatpak Isn't Installed"
                  : page.mode === "installed" ? (page.f.installed.query !== "" ? "No Apps Match" : "No Flatpak Apps Yet")
                  : page.f.searchError !== "" ? "Couldn't Search Flathub"
                  : (page.f.searchDone ? "Nothing Found on Flathub" : "Find Apps on Flathub")
            explanation: !page.f.available ? "Install the flatpak package to manage Flatpak apps here."
                  : page.mode === "installed" ? (page.f.installed.query !== "" ? "Try another name." : "Apps you install from Flathub show up here.")
                  : page.f.searchError !== "" ? page.f.searchError
                  : (page.f.searchDone ? "Try a different name." : "Search thousands of desktop apps by name.")
        }
    }
}
