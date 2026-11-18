// Tools: one-click setup and maintenance, grouped by purpose. Done steps
// say so instead of offering to run again.
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page

    readonly property var s: App.System

    title: "Tools"

    actions: [
        Kirigami.Action {
            text: "Refresh"
            icon.name: "view-refresh"
            onTriggered: page.s.refreshTools()
        }
    ]

    ListView {
        id: list
        model: page.s.tools
        currentIndex: -1
        keyNavigationEnabled: true
        activeFocusOnTab: true
        Accessible.name: "Tools"
        spacing: 0
        section.property: "section"
        section.delegate: Kirigami.ListSectionHeader {
            required property string section
            width: ListView.view.width
            text: section === "Repositories" ? "Software Sources" : "Maintenance"
        }

        delegate: QQC2.ItemDelegate {
            id: row
            required property var model
            required property int index
            required property string title
            required property string description
            required property bool destructive
            required property bool done
            readonly property bool isSource: ["rpmfusion_free", "rpmfusion_nonfree", "add_flathub"].indexOf(model.id) >= 0

            width: ListView.view.width
            text: title
            Accessible.description: description + (done ? " Already set up." : "")
            highlighted: ListView.isCurrentItem
            onClicked: {
                ListView.view.currentIndex = index;
                if (!(done && isSource) && !App.Runner.busy)
                    page.s.runTool(row.model.id);
            }
            Keys.onReturnPressed: clicked()
            Keys.onEnterPressed: clicked()
            Accessible.onPressAction: clicked()

            contentItem: RowLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Icon {
                    source: row.model.id === "add_flathub" ? "flatpak-discover"
                          : row.isSource ? "repository"
                          : row.model.id.indexOf("firmware") === 0 ? "cpu"
                          : row.model.id.indexOf("cache") >= 0 ? "edit-clear-all"
                          : "view-refresh"
                    fallback: "tools"
                    Layout.preferredWidth: Kirigami.Units.iconSizes.medium
                    Layout.preferredHeight: Layout.preferredWidth
                }
                ColumnLayout {
                    spacing: 0
                    Layout.fillWidth: true
                    QQC2.Label {
                        text: row.title
                        font.weight: Font.DemiBold
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }
                    QQC2.Label {
                        text: row.description
                        wrapMode: Text.Wrap
                        color: Kirigami.ColorUtils.linearInterpolation(Kirigami.Theme.textColor, Kirigami.Theme.backgroundColor, 0.3)
                        font: Kirigami.Theme.smallFont
                        Layout.fillWidth: true
                    }
                }
                Pill {
                    visible: row.done && row.isSource
                    text: "Set Up"
                    tone: "positive"
                }
                QQC2.Button {
                    id: runButton
                    activeFocusOnTab: false
                    visible: !(row.done && row.isSource)
                    text: row.model.action
                    icon.name: row.destructive ? "dialog-warning" : ""
                    enabled: !App.Runner.busy
                    Accessible.name: row.model.action + " " + row.title
                    onClicked: page.s.runTool(row.model.id)
                }
            }
        }
    }
}
