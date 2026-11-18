// Updates: one clear status, one main action, and the pending updates
// grouped by what they mean (security, major, everything else, Flatpak).
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page

    // Beside a details column: drag the divider to resize this list.
    Kirigami.ColumnView.interactiveResizeEnabled: true
    Kirigami.ColumnView.minimumWidth: Kirigami.Units.gridUnit * 20
    Kirigami.ColumnView.maximumWidth: Math.max(Kirigami.Units.gridUnit * 20,
                                               root.pageStack.width - Kirigami.Units.gridUnit * 22)
    Kirigami.ColumnView.preferredWidth: root.listColumnWidth
    Kirigami.ColumnView.onPreferredWidthChanged: root.rememberListWidth(Kirigami.ColumnView.preferredWidth)

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
            icon.source: root.ico("view-refresh", enabled)
            tooltip: "Refresh repository metadata and scan again (Ctrl+R)"
            enabled: u.phase !== "checking"
            onTriggered: u.check()
        },
        Kirigami.Action {
            text: "Clean Up Unneeded Packages…"
            icon.source: root.ico("edit-clear-all", enabled)
            tooltip: "Remove dependencies nothing needs anymore (dnf autoremove)"
            displayHint: Kirigami.DisplayHint.AlwaysHide
            enabled: !page.busy
            onTriggered: u.autoremove()
        },
        Kirigami.Action {
            text: "Choose Core Packages…"
            icon.source: root.ico("configure", enabled)
            displayHint: Kirigami.DisplayHint.AlwaysHide
            onTriggered: App.navigate("settings")
        },
        Kirigami.Action {
            text: "Update History"
            icon.source: root.ico("view-history", enabled)
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
        section.delegate: SectionHeader {
            required property string section
            width: ListView.view.width
            text: section
            QQC2.Label {
                text: section === "Security Fixes" ? "Included in Security Only"
                    : section === "Core Updates" ? "Skipped by Update Without Core · kernel, drivers, firmware and bootloader"
                    : ""
                visible: text !== "" && !root.compact
                // Shrinks and elides in a narrow column instead of running
                // past its edge; the key phrase comes first.
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                Layout.maximumWidth: Math.ceil(implicitWidth) + 2  // rounding slack
                horizontalAlignment: Text.AlignRight
                elide: Text.ElideRight
                font: Kirigami.Theme.smallFont
                color: Kirigami.ColorUtils.linearInterpolation(Kirigami.Theme.textColor, Kirigami.Theme.backgroundColor, 0.3)
            }
        }

        header: ColumnLayout {
            id: header
            width: ListView.view.width
            spacing: Kirigami.Units.largeSpacing * 1.5

            SummaryCard {
                Layout.fillWidth: true
                Layout.leftMargin: root.gutter
                Layout.rightMargin: root.gutter
                Layout.topMargin: root.gutter
            }

            // ── Notices: one compact row each, most urgent first ──
            ColumnLayout {
                id: notices
                spacing: Kirigami.Units.smallSpacing
                // (Not the notices' own `visible`: that reads false while
                // this group is hidden, so it could never show again.)
                visible: page.u.rebootRequired || (!!App.appUpdate.available && !App.appUpdate.dismissed)
                         || !!page.u.release.visible || !!page.u.blocked.visible
                Layout.fillWidth: true
                Layout.leftMargin: root.gutter
                Layout.rightMargin: root.gutter

                Notice {
                    id: restartNotice
                    visible: page.u.rebootRequired
                    tone: "warning"
                    iconName: "system-reboot"
                    title: page.u.rebootCertain ? "Restart to finish updating" : "A restart may be needed"
                    body: page.u.rebootCertain
                          ? "Core system updates were installed. You can keep working; they take effect after you restart."
                          : "The app couldn't check whether the last update needs a restart. Restarting is the safe choice."
                    actions: [
                        Kirigami.Action { text: "Restart Now…"; icon.source: root.ico("system-reboot", enabled); onTriggered: page.u.reboot() }
                    ]
                    dismissAction: Kirigami.Action { text: "Later"; onTriggered: page.u.dismissReboot() }
                }
                Notice {
                    id: appNotice
                    visible: !!App.appUpdate.available && !App.appUpdate.dismissed
                    tone: "information"
                    iconName: "update-high"
                    title: "DNF Package Manager " + (App.appUpdate.version || "") + " is available"
                    body: "You have version " + App.version + ". The update is checked against GitHub's digest before it installs."
                    actions: [
                        Kirigami.Action {
                            text: "Install Update"; icon.source: root.ico("download", enabled)
                            visible: !!App.appUpdate.canInstall
                            enabled: !page.busy
                            onTriggered: App.installAppUpdate()
                        },
                        Kirigami.Action { text: "Release Notes"; icon.source: root.ico("internet-services", enabled); onTriggered: App.openReleases() }
                    ]
                    dismissAction: Kirigami.Action { text: "Later"; onTriggered: App.dismissAppUpdate() }
                }
                Notice {
                    id: releaseNotice
                    // "Not Now" dismisses; a downloaded upgrade's "Cancel
                    // Upgrade" is a real action, so it stays a button.
                    readonly property bool dismissable: !page.u.release.downloaded
                    visible: !!page.u.release.visible
                    tone: page.u.release.downloaded ? "positive" : "information"
                    iconName: "system-upgrade"
                    title: page.u.release.title || ""
                    body: page.u.release.text || ""
                    actions: [
                        Kirigami.Action {
                            text: page.u.release.primary || ""
                            icon.source: root.ico(page.u.release.downloaded ? "system-reboot" : "system-upgrade", enabled)
                            enabled: !page.busy
                            onTriggered: page.u.releasePrimary()
                        },
                        Kirigami.Action {
                            text: "What's New"; icon.source: root.ico("help-about", enabled)
                            visible: !page.u.release.downloaded
                            onTriggered: page.u.openReleaseNotes()
                        },
                        Kirigami.Action {
                            text: page.u.release.secondary || ""
                            visible: !releaseNotice.dismissable
                            onTriggered: page.u.releaseSecondary()
                        }
                    ]
                    dismissAction: Kirigami.Action {
                        text: page.u.release.secondary || "Not Now"
                        visible: releaseNotice.dismissable
                        onTriggered: page.u.releaseSecondary()
                    }
                }
                Notice {
                    id: blockedNotice
                    visible: !!page.u.blocked.visible
                    tone: "information"
                    iconName: "security-medium"
                    title: page.u.blocked.title || ""
                    body: page.u.blocked.text || ""
                    actions: [
                        Kirigami.Action {
                            text: "Details…"
                            icon.source: root.ico("documentinfo", enabled)
                            onTriggered: page.u.explainBlocked()
                        }
                    ]
                }
            }

            // ── Filter bar (stacks on narrow windows) ──
            GridLayout {
                visible: page.u.total > 0
                columns: root.compact ? 1 : 2
                columnSpacing: Kirigami.Units.largeSpacing
                rowSpacing: Kirigami.Units.smallSpacing
                Layout.fillWidth: true
                Layout.leftMargin: root.gutter
                Layout.rightMargin: root.gutter
                Layout.bottomMargin: Kirigami.Units.smallSpacing

                Kirigami.SearchField {
                    id: search
                    placeholderText: "Filter updates…"
                    Accessible.name: "Filter updates"
                    Component.onCompleted: page.searchField = search
                    Layout.fillWidth: true
                    Layout.maximumWidth: Kirigami.Units.gridUnit * 18
                    Layout.preferredWidth: Kirigami.Units.gridUnit * 18
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
                        { key: "major", label: "Core", count: page.u.majorCount },
                        { key: "flatpak", label: "Flatpak", count: page.u.flatpakCount }
                    ]
                    delegate: FilterChip {
                        required property var modelData
                        visible: modelData.key === "all" || modelData.count > 0
                        active: page.u.filtered.category === modelData.key
                        text: root.compact ? modelData.label
                                           : modelData.label + " (" + modelData.count + ")"
                        onClicked: page.u.filtered.category = modelData.key
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
                icon.source: root.ico("edit-find", enabled)
                text: "No Matching Updates"
                explanation: "Nothing pending matches this filter."
                helpfulAction: Kirigami.Action {
                    text: "Show All Updates"
                    icon.source: root.ico("edit-clear", enabled)
                    onTriggered: page.showAllUpdates()
                }
            }
        }
    }
}
