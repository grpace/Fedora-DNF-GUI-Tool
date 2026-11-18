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
    // The trailing column every row shares (status or action).
    readonly property real actionWidth: Kirigami.Units.gridUnit * 6.5

    actions: [
        Kirigami.Action {
            text: "Refresh"
            icon.source: root.ico("view-refresh", enabled)
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
        section.delegate: SectionHeader {
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
            leftPadding: root.gutter
            rightPadding: root.gutter
            topPadding: Kirigami.Units.largeSpacing
            bottomPadding: Kirigami.Units.largeSpacing
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
                GlyphTile {
                    iconName: row.model.id === "add_flathub" ? "flatpak-discover"
                            : row.isSource ? "repository"
                            : row.model.id.indexOf("firmware") === 0 ? "cpu"
                            : row.model.id === "clean_cache" ? "edit-clear-all"
                            : row.model.id === "distro_sync" ? "distro-sync"
                            : "view-refresh"
                    selected: row.highlighted
                }
                ColumnLayout {
                    spacing: Kirigami.Units.smallSpacing / 2
                    Layout.fillWidth: true
                    QQC2.Label {
                        text: row.title
                        font.weight: Font.DemiBold
                        elide: Text.ElideRight
                        color: row.highlighted ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.textColor
                        Layout.fillWidth: true
                    }
                    QQC2.Label {
                        text: row.description
                        wrapMode: Text.Wrap
                        color: row.highlighted ? Kirigami.Theme.highlightedTextColor
                             : Kirigami.ColorUtils.linearInterpolation(Kirigami.Theme.textColor, Kirigami.Theme.backgroundColor, 0.3)
                        font: Kirigami.Theme.smallFont
                        Layout.fillWidth: true
                    }
                }
                // Done: a quiet status with a check, not a button. Status
                // and buttons share one fixed-width trailing column.
                Item {
                    visible: row.done && row.isSource
                    implicitHeight: doneRow.implicitHeight
                    Layout.preferredWidth: page.actionWidth
                    Layout.minimumWidth: page.actionWidth
                    Layout.maximumWidth: page.actionWidth
                    Accessible.role: Accessible.StaticText
                    Accessible.name: "Set Up"
                    RowLayout {
                        id: doneRow
                        anchors.centerIn: parent
                        spacing: Kirigami.Units.smallSpacing * 1.5
                        Kirigami.Icon {
                            source: root.ico("checkmark", true, color)
                            color: row.highlighted ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.positiveTextColor
                            implicitWidth: Kirigami.Units.iconSizes.small
                            implicitHeight: implicitWidth
                        }
                        QQC2.Label {
                            text: "Set Up"
                            font.weight: Font.DemiBold
                            // Positive tone pulled toward the text (Pill.qml, PILL_MIX).
                            readonly property color tone: Kirigami.Theme.positiveTextColor
                            color: row.highlighted ? Kirigami.Theme.highlightedTextColor
                                 : Qt.rgba(tone.r + (Kirigami.Theme.textColor.r - tone.r) * 0.4,
                                           tone.g + (Kirigami.Theme.textColor.g - tone.g) * 0.4,
                                           tone.b + (Kirigami.Theme.textColor.b - tone.b) * 0.4, 1)
                            Accessible.ignored: true
                        }
                    }
                }
                QQC2.ToolButton {
                    id: runButton
                    activeFocusOnTab: false
                    visible: !(row.done && row.isSource)
                    text: row.model.action
                    icon.source: root.ico(row.destructive ? "dialog-warning"
                                        : row.isSource ? "list-add"
                                        : row.model.id === "firmware_check" ? "search"
                                        : row.model.id === "clean_cache" ? "edit-clear-all"
                                        : "view-refresh", enabled)
                    enabled: !App.Runner.busy
                    Layout.preferredWidth: page.actionWidth
                    Layout.minimumWidth: page.actionWidth
                    Layout.maximumWidth: page.actionWidth
                    Accessible.name: row.model.action + " " + row.title
                    onClicked: page.s.runTool(row.model.id)
                }
            }
        }
    }
}
