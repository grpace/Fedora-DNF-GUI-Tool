// Updates: one clear status, one main action, and the pending updates
// grouped by what they mean (security, major, everything else, Flatpak).
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page

    readonly property var u: App.Updates
    // The main button's mode: the favorite, or what can run when it can't.
    readonly property var favoriteMode: {
        for (const m of u.modes)
            if (m.key === u.mainMode)
                return m;
        return u.modes.length ? u.modes[0] : ({});
    }
    readonly property bool busy: App.Runner.busy

    title: "Updates"
    supportsRefreshing: true
    onRefreshingChanged: if (refreshing) { u.check(); refreshing = false; }

    actions: [
        Kirigami.Action {
            text: "Check for Updates"
            icon.name: "view-refresh"
            tooltip: "Refresh repository metadata and scan again (Ctrl+R)"
            enabled: u.phase !== "checking"
            onTriggered: u.check()
        },
        Kirigami.Action {
            text: "Clean Up Unneeded Packages…"
            icon.name: "edit-clear-all"
            tooltip: "Remove dependencies nothing needs anymore (dnf autoremove)"
            displayHint: Kirigami.DisplayHint.AlwaysHide
            enabled: !page.busy
            onTriggered: u.autoremove()
        },
        Kirigami.Action {
            text: "Choose Major Packages…"
            icon.name: "configure"
            displayHint: Kirigami.DisplayHint.AlwaysHide
            onTriggered: App.navigate("settings")
        },
        Kirigami.Action {
            text: "Update History"
            icon.name: "view-history"
            displayHint: Kirigami.DisplayHint.AlwaysHide
            onTriggered: App.navigate("history")
        }
    ]

    // The filter field lives in the list header (its own component scope).
    property var searchField: null

    function focusSearch() {
        list.positionViewAtBeginning();
        if (searchField) {
            searchField.forceActiveFocus();
            searchField.selectAll();
        }
    }

    function showAllUpdates() {
        if (searchField)
            searchField.text = "";
        u.filtered.query = "";
        u.filtered.category = "all";
    }

    ListView {
        id: list
        model: page.u.filtered
        currentIndex: -1
        keyNavigationEnabled: true
        activeFocusOnTab: true
        Accessible.name: "Pending Updates"

        // The header (summary and banners) grows over a few frames when a
        // scan's results arrive: hold the top while it settles, then leave
        // scrolling alone. Any scrolling or keyboard move ends the hold.
        property string shownPhase: ""
        property bool settling: false
        Connections {
            target: page.u
            function onChanged() {
                const phase = page.u.phase;
                if (phase !== list.shownPhase) {
                    list.shownPhase = phase;
                    if (phase !== "checking" && phase !== "idle") {
                        list.settling = true;
                        list.positionViewAtBeginning();
                        settle.restart();
                    }
                }
            }
        }
        Timer {
            id: settle
            interval: 600
            onTriggered: list.settling = false
        }
        onOriginYChanged: if (settling) positionViewAtBeginning()
        onContentHeightChanged: if (settling) positionViewAtBeginning()
        onMovementStarted: settling = false
        onCurrentIndexChanged: settling = false

        section.property: "section"
        section.delegate: Kirigami.ListSectionHeader {
            required property string section
            width: ListView.view.width
            text: section
            QQC2.Label {
                text: section === "Security Fixes" ? "Included in Security Only"
                    : section === "Major Updates" ? "Kernel, drivers, firmware and bootloader · Update Without Major skips these"
                    : ""
                visible: text !== "" && !root.compact
                font: Kirigami.Theme.smallFont
                color: Kirigami.ColorUtils.linearInterpolation(Kirigami.Theme.textColor, Kirigami.Theme.backgroundColor, 0.3)
            }
        }

        header: ColumnLayout {
            id: header
            width: ListView.view.width
            spacing: Kirigami.Units.largeSpacing

            SummaryCard {
                Layout.fillWidth: true
                Layout.margins: Kirigami.Units.largeSpacing
                Layout.bottomMargin: 0
            }

            Banner {
                visible: page.u.rebootRequired
                type: Kirigami.MessageType.Warning
                title: page.u.rebootCertain ? "Restart to finish updating" : "A restart may be needed"
                body: page.u.rebootCertain
                      ? "Core system updates were installed. You can keep working; they take effect after you restart."
                      : "The app couldn't check whether the last update needs a restart. Restarting is the safe choice."
                actions: [
                    Kirigami.Action { text: "Restart Now…"; icon.name: "system-reboot"; onTriggered: page.u.reboot() },
                    Kirigami.Action { text: "Later"; onTriggered: page.u.dismissReboot() }
                ]
            }
            Banner {
                visible: !!App.appUpdate.available && !App.appUpdate.dismissed
                type: Kirigami.MessageType.Information
                iconName: "update-high"
                title: "DNF Package Manager " + (App.appUpdate.version || "") + " is available"
                body: "You have version " + App.version + ". The update is checked against GitHub's digest before it installs."
                actions: [
                    Kirigami.Action {
                        text: "Install Update"; icon.name: "download"
                        visible: !!App.appUpdate.canInstall
                        enabled: !page.busy
                        onTriggered: App.installAppUpdate()
                    },
                    Kirigami.Action { text: "Release Notes"; icon.name: "internet-services"; onTriggered: App.openReleases() },
                    Kirigami.Action { text: "Later"; onTriggered: App.dismissAppUpdate() }
                ]
            }
            Banner {
                visible: !!page.u.release.visible
                type: page.u.release.downloaded ? Kirigami.MessageType.Positive : Kirigami.MessageType.Information
                iconName: "system-upgrade"
                title: page.u.release.title || ""
                body: page.u.release.text || ""
                actions: [
                    Kirigami.Action {
                        text: page.u.release.primary || ""
                        icon.name: page.u.release.downloaded ? "system-reboot" : "system-upgrade"
                        enabled: !page.busy
                        onTriggered: page.u.releasePrimary()
                    },
                    Kirigami.Action {
                        text: "What's New"; icon.name: "help-about"
                        visible: !page.u.release.downloaded
                        onTriggered: page.u.openReleaseNotes()
                    },
                    Kirigami.Action { text: page.u.release.secondary || ""; onTriggered: page.u.releaseSecondary() }
                ]
            }
            Banner {
                visible: !!page.u.blocked.visible
                type: Kirigami.MessageType.Warning
                iconName: "security-medium"
                title: page.u.blocked.title || ""
                body: page.u.blocked.text || ""
                actions: [
                    Kirigami.Action {
                        text: "Details…"
                        icon.name: "documentinfo"
                        onTriggered: page.u.explainBlocked()
                    }
                ]
            }

            // ── Filter bar (stacks on narrow windows) ──
            GridLayout {
                visible: page.u.total > 0
                columns: root.compact ? 1 : 2
                columnSpacing: Kirigami.Units.smallSpacing
                rowSpacing: Kirigami.Units.smallSpacing
                Layout.fillWidth: true
                Layout.leftMargin: Kirigami.Units.largeSpacing
                Layout.rightMargin: Kirigami.Units.largeSpacing

                Kirigami.SearchField {
                    id: search
                    placeholderText: "Filter updates…"
                    Accessible.name: "Filter updates"
                    Component.onCompleted: page.searchField = search
                    Layout.fillWidth: true
                    Layout.maximumWidth: Kirigami.Units.gridUnit * 18
                    onTextChanged: page.u.filtered.query = text
                    KeyNavigation.down: list
                }
                RowLayout {
                spacing: 0
                Layout.alignment: root.compact ? Qt.AlignLeft : Qt.AlignRight
                Repeater {
                    model: [
                        { key: "all", label: "All", count: page.u.total },
                        { key: "security", label: "Security", count: page.u.securityTotal },
                        { key: "major", label: "Major", count: page.u.majorCount },
                        { key: "flatpak", label: "Flatpak", count: page.u.flatpakCount }
                    ]
                    delegate: QQC2.ToolButton {
                        required property var modelData
                        visible: modelData.key === "all" || modelData.count > 0
                        checkable: true
                        checked: page.u.filtered.category === modelData.key
                        text: root.compact ? modelData.label
                                           : modelData.label + " (" + modelData.count + ")"
                        onClicked: page.u.filtered.category = modelData.key
                        Accessible.role: Accessible.RadioButton
                        Accessible.name: modelData.label + ", " + modelData.count
                    }
                }
                }
            }
        }

        delegate: UpdateRow {
            width: ListView.view.width
            onOpenRequested: (name) => root.openPackageDetails(name)
        }

        footer: Item {
            width: ListView.view.width
            height: emptyMessage.visible ? emptyMessage.implicitHeight + Kirigami.Units.gridUnit * 4 : 0
            Kirigami.PlaceholderMessage {
                id: emptyMessage
                anchors.centerIn: parent
                width: parent.width - Kirigami.Units.gridUnit * 4
                visible: list.count === 0 && page.u.total > 0
                icon.name: "edit-find"
                text: "No Matching Updates"
                explanation: "Nothing pending matches this filter."
                helpfulAction: Kirigami.Action {
                    text: "Show All Updates"
                    icon.name: "edit-clear"
                    onTriggered: page.showAllUpdates()
                }
            }
        }
    }
}
