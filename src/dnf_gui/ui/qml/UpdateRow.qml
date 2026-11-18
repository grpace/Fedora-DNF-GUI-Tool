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
    required property string branch
    required property string iconName
    required property string tooltip

    signal openRequested(string name)

    readonly property bool flatpak: kind === "flatpak"
    readonly property color fg: highlighted ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.textColor
    readonly property color dim: highlighted ? Kirigami.Theme.highlightedTextColor : Kirigami.ColorUtils.linearInterpolation(Kirigami.Theme.textColor, Kirigami.Theme.backgroundColor, 0.3)
    readonly property bool narrow: width < Kirigami.Units.gridUnit * 30

    text: name
    highlighted: ListView.isCurrentItem
    leftPadding: root.gutter
    rightPadding: root.gutter
    topPadding: Kirigami.Units.largeSpacing
    bottomPadding: Kirigami.Units.largeSpacing
    Accessible.onPressAction: clicked()
    Accessible.description: (severity === "Security" ? "Security update. "
                             : severity ? severity + " security update. " : "")
                            + (waiting ? "Waiting on another repository. " : "")
                            + (size ? size + " download. " : "")
                            + (repo && repo !== "updates" ? "From " + repo + ". " : "")
                            + (major ? "Core update. " : "")
                            + (flatpak ? "Flatpak app. " : "")
                            + (fromVersion ? "From " + fromVersion + " to " + toVersion : toVersion)

    onClicked: {
        ListView.view.currentIndex = index;
        openRequested(name);
    }
    Keys.onReturnPressed: clicked()
    Keys.onEnterPressed: clicked()
    Keys.onMenuPressed: menu.popup(more, 0, more.height)
    Keys.onPressed: (event) => {
        if (event.key === Qt.Key_F10 && (event.modifiers & Qt.ShiftModifier)) {
            menu.popup(more, 0, more.height);
            event.accepted = true;
        }
    }

    QQC2.ToolTip.text: tooltip || majorReason
    QQC2.ToolTip.visible: hovered && (tooltip !== "" || majorReason !== "")
    QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay * 3

    contentItem: RowLayout {
        spacing: Kirigami.Units.largeSpacing

        AppIcon {
            name: row.name
            appId: row.flatpak ? row.iconName : ""
            Layout.preferredWidth: Kirigami.Units.iconSizes.medium
            Layout.preferredHeight: Layout.preferredWidth
        }

        ColumnLayout {
            spacing: Kirigami.Units.smallSpacing / 2
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
                    width: Math.max(0, Math.min(implicitWidth, nameLine.width
                                    - (pills.width > 0 ? pills.width + Kirigami.Units.smallSpacing * 1.5 : 0)))
                    text: row.name
                    font.weight: Font.DemiBold
                    color: row.fg
                    elide: Text.ElideRight
                }
                Row {
                    id: pills
                    x: nameLabel.width + Kirigami.Units.smallSpacing * 1.5
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: Kirigami.Units.smallSpacing * 1.5
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
                        text: "Core"
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

        // Fixed width and tabular digits: sizes line up down the list.
        QQC2.Label {
            text: row.size
            visible: !row.narrow
            color: row.dim
            font.pointSize: Kirigami.Theme.smallFont.pointSize
            font.features: { "tnum": 1 }
            horizontalAlignment: Text.AlignRight
            elide: Text.ElideLeft
            Layout.preferredWidth: Kirigami.Units.gridUnit * 4.5
        }
        QQC2.ToolButton {
            id: updateButton
            text: "Update"
            icon.source: root.ico("download", enabled)
            display: row.narrow ? QQC2.AbstractButton.IconOnly : QQC2.AbstractButton.TextBesideIcon
            enabled: !App.Runner.busy
            activeFocusOnTab: false  // one Tab stop per row
            Accessible.name: "Update " + row.name
            QQC2.ToolTip.text: "Update only " + row.name
            QQC2.ToolTip.visible: hovered && row.narrow
            QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay
            // A Flatpak row updates just that app (and branch).
            onClicked: row.flatpak ? App.Flatpak.updateApp(row.appId, row.branch)
                                   : App.Updates.upgradePackage(row.name)
        }
        QQC2.ToolButton {
            id: more
            icon.source: root.ico("overflow-menu", enabled)
            text: "More Actions for " + row.name
            display: QQC2.AbstractButton.IconOnly
            activeFocusOnTab: false
            QQC2.ToolTip.text: "More Actions"
            QQC2.ToolTip.visible: hovered
            QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay
            onClicked: menu.popup(more, 0, more.height)

            QQC2.Menu {
                id: menu
                QQC2.MenuItem {
                    text: "Show Details"
                    icon.source: root.ico("documentinfo", enabled)
                    onTriggered: row.clicked()
                }
                QQC2.MenuItem {
                    visible: !row.flatpak
                    height: visible ? implicitHeight : 0
                    text: row.majorActionLabel
                    icon.source: root.ico("flag", enabled)
                    enabled: row.canToggleMajor
                    onTriggered: App.Updates.toggleMajor(row.name)
                    QQC2.ToolTip.text: row.majorTooltip
                    QQC2.ToolTip.visible: hovered
                }
                QQC2.MenuItem {
                    visible: row.flatpak
                    height: visible ? implicitHeight : 0
                    text: "Open Flatpak Page"
                    icon.source: root.ico("folder-flatpak", enabled)
                    onTriggered: App.navigate("flatpak")
                }
                QQC2.MenuItem {
                    text: "Copy Name"
                    icon.source: root.ico("edit-copy", enabled)
                    onTriggered: App.copyText(row.flatpak ? row.appId : row.name)
                }
            }
        }
    }

}
