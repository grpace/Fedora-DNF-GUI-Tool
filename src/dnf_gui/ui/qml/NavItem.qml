// One sidebar entry: icon, label and an optional count badge.
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

QQC2.ItemDelegate {
    id: item

    property string key
    property string label
    property string iconName
    property string iconFallback: "application-x-executable"
    property int badge: 0
    property bool collapsed: false
    property bool selectable: true
    property bool running: false
    signal triggered()

    readonly property bool current: selectable && App.currentPage === key

    text: badge > 0 ? label + ", " + badge + " pending" : label
    highlighted: current
    checkable: false
    padding: Kirigami.Units.largeSpacing
    implicitHeight: Kirigami.Units.gridUnit * 2.2

    Accessible.role: Accessible.PageTab
    Accessible.name: text
    Accessible.selected: current

    QQC2.ToolTip.text: label + (badge > 0 ? " (" + badge + ")" : "")
    QQC2.ToolTip.visible: collapsed && hovered
    QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay

    onClicked: selectable ? App.navigate(key) : triggered()

    contentItem: RowLayout {
        spacing: Kirigami.Units.largeSpacing
        Item {
            implicitWidth: Kirigami.Units.iconSizes.smallMedium
            implicitHeight: implicitWidth
            Layout.alignment: item.collapsed ? Qt.AlignHCenter : Qt.AlignLeft
            Kirigami.Icon {
                anchors.fill: parent
                source: item.iconName
                fallback: item.iconFallback
                color: item.highlighted ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.textColor
                isMask: false
            }
            // Badge dot on the icon when collapsed.
            Rectangle {
                visible: item.collapsed && item.badge > 0
                width: Kirigami.Units.smallSpacing * 2.5
                height: width
                radius: width / 2
                color: Kirigami.Theme.negativeTextColor
                anchors.top: parent.top
                anchors.right: parent.right
                anchors.margins: -Kirigami.Units.smallSpacing / 2
            }
        }
        QQC2.Label {
            text: item.label
            visible: !item.collapsed
            elide: Text.ElideRight
            color: item.highlighted ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.textColor
            Layout.fillWidth: true
        }
        QQC2.BusyIndicator {
            visible: item.running && !item.collapsed
            running: visible
            implicitWidth: Kirigami.Units.iconSizes.small
            implicitHeight: implicitWidth
        }
        Rectangle {
            visible: item.badge > 0 && !item.collapsed
            radius: height / 2
            color: item.highlighted ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.highlightColor
            implicitHeight: badgeLabel.implicitHeight + Kirigami.Units.smallSpacing
            implicitWidth: Math.max(implicitHeight, badgeLabel.implicitWidth + Kirigami.Units.largeSpacing)
            QQC2.Label {
                id: badgeLabel
                anchors.centerIn: parent
                text: item.badge
                font.weight: Font.DemiBold
                font.pointSize: Kirigami.Theme.smallFont.pointSize
                color: item.highlighted ? Kirigami.Theme.highlightColor : Kirigami.Theme.highlightedTextColor
            }
        }
    }
}
