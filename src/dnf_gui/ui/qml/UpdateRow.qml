// One pending update. One focus stop per row: Enter opens details, the
// Menu key opens its actions.
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

QQC2.ItemDelegate {
    id: row

    required property int index
    required property string name
    required property string kind
    required property string fromVersion
    required property string toVersion
    required property string repo
    required property string size
    required property string severity
    required property bool security
    required property bool waiting
    required property bool major
    required property string majorReason
    required property bool canToggleMajor
    required property string majorActionLabel
    required property string majorTooltip
    required property string appId
    required property string iconName
    required property string tooltip

    signal openRequested(string name)

    readonly property bool flatpak: kind === "flatpak"
    readonly property color fg: highlighted ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.textColor
    readonly property color dim: highlighted ? Kirigami.Theme.highlightedTextColor : Kirigami.ColorUtils.linearInterpolation(Kirigami.Theme.textColor, Kirigami.Theme.backgroundColor, 0.3)
    readonly property bool narrow: width < Kirigami.Units.gridUnit * 30

    text: name
    highlighted: ListView.isCurrentItem
    Accessible.description: (severity ? severity + " security update. " : "")
                            + (major ? "Major update. " : "")
                            + (flatpak ? "Flatpak app. " : "")
                            + (fromVersion ? "From " + fromVersion + " to " + toVersion : toVersion)

    onClicked: {
        ListView.view.currentIndex = index;
        openRequested(name);
    }
    Keys.onReturnPressed: clicked()
    Keys.onEnterPressed: clicked()
    Keys.onMenuPressed: menu.popup(more, 0, more.height)

    QQC2.ToolTip.text: tooltip || majorReason
    QQC2.ToolTip.visible: hovered && (tooltip !== "" || majorReason !== "")
    QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay * 3

    contentItem: RowLayout {
        spacing: Kirigami.Units.largeSpacing

        Kirigami.Icon {
            source: row.iconName
            fallback: "package-x-generic"
            Layout.preferredWidth: Kirigami.Units.iconSizes.medium
            Layout.preferredHeight: Layout.preferredWidth
        }

        ColumnLayout {
            spacing: 0
            Layout.fillWidth: true

            // Name and badges: the name elides only when the row is
            // really too narrow for both.
            Item {
                id: nameLine
                Layout.fillWidth: true
                implicitHeight: Math.max(nameLabel.implicitHeight, pills.implicitHeight)
                QQC2.Label {
                    id: nameLabel
                    anchors.verticalCenter: parent.verticalCenter
                    width: Math.min(implicitWidth, nameLine.width
                                    - (pills.width > 0 ? pills.width + Kirigami.Units.smallSpacing : 0))
                    text: row.name
                    font.weight: Font.DemiBold
                    color: row.fg
                    elide: Text.ElideRight
                }
                Row {
                    id: pills
                    x: nameLabel.width + Kirigami.Units.smallSpacing
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: Kirigami.Units.smallSpacing
                    Pill {
                        visible: row.severity !== ""
                        text: row.severity
                        tone: row.severity === "Critical" || row.severity === "Important" ? "negative" : "neutral"
                        selected: row.highlighted
                    }
                    Pill {
                        visible: row.waiting
                        text: "Waiting"
                        tone: "neutral"
                        selected: row.highlighted
                    }
                    Pill {
                        visible: row.major
                        text: "Major"
                        tone: "info"
                        selected: row.highlighted
                    }
                }
            }
            QQC2.Label {
                Layout.fillWidth: true
                elide: Text.ElideMiddle
                color: row.dim
                font: Kirigami.Theme.smallFont
                text: row.flatpak ? row.appId + (row.toVersion ? "  ·  " + row.toVersion : "")
                                  : (row.fromVersion ? row.fromVersion + "  →  " : "") + row.toVersion
                                    + (row.repo && row.repo !== "updates" ? "  ·  " + row.repo : "")
            }
        }

        QQC2.Label {
            text: row.size
            visible: row.size !== "" && !row.narrow
            color: row.dim
            font: Kirigami.Theme.smallFont
        }
        QQC2.ToolButton {
            visible: !row.flatpak
            text: "Update"
            icon.name: "download"
            display: row.narrow ? QQC2.AbstractButton.IconOnly : QQC2.AbstractButton.TextBesideIcon
            enabled: !App.Runner.busy
            Accessible.name: "Update " + row.name
            QQC2.ToolTip.text: "Update only " + row.name
            QQC2.ToolTip.visible: hovered && row.narrow
            QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay
            onClicked: App.Updates.upgradePackage(row.name)
        }
        QQC2.ToolButton {
            id: more
            icon.name: "overflow-menu"
            text: "More Actions for " + row.name
            display: QQC2.AbstractButton.IconOnly
            QQC2.ToolTip.text: "More Actions"
            QQC2.ToolTip.visible: hovered
            QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay
            onClicked: menu.popup(more, 0, more.height)

            QQC2.Menu {
                id: menu
                QQC2.MenuItem {
                    text: "Show Details"
                    icon.name: "documentinfo"
                    onTriggered: row.clicked()
                }
                QQC2.MenuItem {
                    visible: !row.flatpak
                    height: visible ? implicitHeight : 0
                    text: row.majorActionLabel
                    icon.name: "flag"
                    enabled: row.canToggleMajor
                    onTriggered: App.Updates.toggleMajor(row.name)
                    QQC2.ToolTip.text: row.majorTooltip
                    QQC2.ToolTip.visible: hovered
                }
                QQC2.MenuItem {
                    visible: row.flatpak
                    height: visible ? implicitHeight : 0
                    text: "Open Flatpak Page"
                    icon.name: "folder-flatpak"
                    onTriggered: App.navigate("flatpak")
                }
                QQC2.MenuItem {
                    text: "Copy Name"
                    icon.name: "edit-copy"
                    onTriggered: App.copyText(row.flatpak ? row.appId : row.name)
                }
            }
        }
    }

}
