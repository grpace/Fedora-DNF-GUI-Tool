// Repositories: enabled first, each with a switch that only changes once
// dnf has actually changed it.
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page

    readonly property var r: App.Repos

    title: "Repositories"

    actions: [
        Kirigami.Action {
            text: "Add COPR Repository…"
            icon.source: root.ico("list-add", enabled)
            enabled: !App.Runner.busy
            onTriggered: coprDialog.open()
        },
        Kirigami.Action {
            text: "Refresh"
            icon.source: root.ico("view-refresh", enabled)
            enabled: !page.r.loading
            onTriggered: page.r.refresh()
        }
    ]

    function focusSearch() {
        search.forceActiveFocus();
        search.selectAll();
    }

    header: QQC2.ToolBar {
        position: QQC2.ToolBar.Header
        contentItem: Kirigami.SearchField {
            id: search
            placeholderText: "Filter repositories…"
            Accessible.name: "Filter repositories"
            onTextChanged: page.r.repos.query = text
            KeyNavigation.down: list
        }
    }

    ListView {
        id: list
        model: page.r.repos
        currentIndex: -1
        keyNavigationEnabled: true
        activeFocusOnTab: true
        Accessible.name: "Repositories"
        section.property: "enabled"
        section.delegate: Kirigami.ListSectionHeader {
            required property string section
            width: ListView.view.width
            text: section === "true" ? "Enabled" : "Disabled"
        }

        delegate: QQC2.ItemDelegate {
            id: row
            required property var model
            required property int index
            required property string name
            readonly property bool copr: model.id.indexOf("copr:") === 0

            width: ListView.view.width
            text: name || model.id
            highlighted: ListView.isCurrentItem
            Accessible.description: (model.enabled ? "Enabled" : "Disabled") + ", " + model.id
            // The row and its switch both ask; nothing changes until dnf has.
            function requestToggle() {
                if (!App.Runner.busy)
                    page.r.setEnabled(row.model.id, !row.model.enabled);
            }
            onClicked: { ListView.view.currentIndex = index; requestToggle(); }
            Accessible.onPressAction: requestToggle()
            Keys.onReturnPressed: requestToggle()
            Keys.onEnterPressed: requestToggle()

            contentItem: RowLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Icon {
                    source: root.ico(row.copr ? "user-identity" : "repository", enabled, color)
                    color: row.highlighted ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.textColor
                    Layout.preferredWidth: Kirigami.Units.iconSizes.medium
                    Layout.preferredHeight: Layout.preferredWidth
                    opacity: row.model.enabled ? 1 : 0.5
                }
                ColumnLayout {
                    spacing: 0
                    Layout.fillWidth: true
                    QQC2.Label {
                        text: row.name || row.model.id
                        font.weight: Font.DemiBold
                        elide: Text.ElideRight
                        color: row.highlighted ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.textColor
                        Layout.fillWidth: true
                    }
                    QQC2.Label {
                        text: row.model.id + (row.copr ? "  ·  Community (COPR)" : "")
                        elide: Text.ElideMiddle
                        color: row.highlighted ? Kirigami.Theme.highlightedTextColor : Kirigami.ColorUtils.linearInterpolation(Kirigami.Theme.textColor, Kirigami.Theme.backgroundColor, 0.3)
                        font: Kirigami.Theme.smallFont
                        Layout.fillWidth: true
                    }
                }
                QQC2.Switch {
                    id: toggle
                    // Mirrors dnf's state; a click asks, and the list reloads after.
                    checked: row.model.enabled
                    enabled: !App.Runner.busy
                    Accessible.name: (row.model.enabled ? "Disable " : "Enable ") + (row.name || row.model.id)
                    onClicked: {
                        checked = Qt.binding(() => row.model.enabled);
                        row.requestToggle();
                    }
                }
            }
        }

        Kirigami.LoadingPlaceholder {
            anchors.centerIn: parent
            visible: page.r.loading && list.count === 0
            text: "Loading Repositories…"
        }
        Kirigami.PlaceholderMessage {
            anchors.centerIn: parent
            width: parent.width - Kirigami.Units.gridUnit * 4
            visible: list.count === 0 && !page.r.loading
            icon.source: root.ico("repository", enabled)
            text: page.r.error !== "" ? "Couldn't List Repositories" : "No Matching Repositories"
            explanation: page.r.error
        }
    }

    Kirigami.PromptDialog {
        id: coprDialog
        title: "Add COPR Repository"
        subtitle: "COPR repositories are built by the community, not Fedora. Only add ones you trust."
        standardButtons: Kirigami.Dialog.NoButton
        customFooterActions: [
            Kirigami.Action {
                text: "Add Repository"
                icon.source: root.ico("list-add", enabled)
                enabled: coprField.text.trim().indexOf("/") > 0
                onTriggered: { coprDialog.close(); page.r.addCopr(coprField.text); coprField.clear(); }
            },
            Kirigami.Action {
                text: "Cancel"
                icon.source: root.ico("dialog-cancel", enabled)
                onTriggered: coprDialog.close()
            }
        ]
        QQC2.TextField {
            id: coprField
            placeholderText: "owner/project"
            Accessible.name: "COPR repository, as owner slash project"
            onAccepted: if (text.trim().indexOf("/") > 0) { coprDialog.close(); page.r.addCopr(text); clear(); }
        }
        onOpened: coprField.forceActiveFocus()
    }
}
