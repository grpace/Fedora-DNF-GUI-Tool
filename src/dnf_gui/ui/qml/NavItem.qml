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
    signal triggered()

    readonly property bool current: selectable && App.currentPage === key

    text: badge > 0 ? label + ", " + badge + " pending" : label
    highlighted: current
    checkable: false
    padding: Kirigami.Units.largeSpacing
    implicitHeight: Kirigami.Units.gridUnit * 2.2
    Layout.leftMargin: Kirigami.Units.smallSpacing
    Layout.rightMargin: Kirigami.Units.smallSpacing

    // The count badge, expanded or collapsed: the darkened accent with
    // white text, or inverted on the selected entry (check_contrast.py
    // PRIMARY_MIX: both pairings pass AA in Breeze Light and Dark).
    readonly property color badgeColor: Qt.rgba(Kirigami.Theme.highlightColor.r * 0.7,
                                                Kirigami.Theme.highlightColor.g * 0.7,
                                                Kirigami.Theme.highlightColor.b * 0.7, 1)

    background: Rectangle {
        radius: Kirigami.Units.cornerRadius
        color: item.highlighted || item.down ? Kirigami.Theme.highlightColor
             : item.hovered ? Qt.rgba(Kirigami.Theme.highlightColor.r, Kirigami.Theme.highlightColor.g,
                                      Kirigami.Theme.highlightColor.b, 0.18)
             : "transparent"
        border.width: item.visualFocus ? 1 : 0
        border.color: item.highlighted ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.focusColor
    }

    Accessible.role: Accessible.PageTab
    Accessible.name: text
    Accessible.selected: current
    Accessible.onPressAction: clicked()

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
                source: root.ico(item.iconName, enabled, color)
                color: item.highlighted ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.textColor
            }
            // Badge dot on the icon when collapsed, ringed in the sidebar's
            // color so it stands off the icon and the highlight.
            Rectangle {
                visible: item.collapsed && item.badge > 0
                width: Kirigami.Units.smallSpacing * 2.5 + border.width * 2
                height: width
                radius: width / 2
                color: item.highlighted ? Kirigami.Theme.highlightedTextColor : item.badgeColor
                border.width: 2
                border.color: item.highlighted ? Kirigami.Theme.highlightColor : Kirigami.Theme.backgroundColor
                anchors.top: parent.top
                anchors.right: parent.right
                anchors.margins: -Kirigami.Units.smallSpacing / 2 - border.width
            }
        }
        QQC2.Label {
            text: item.label
            visible: !item.collapsed
            elide: Text.ElideRight
            color: item.highlighted ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.textColor
            Layout.fillWidth: true
        }
        Rectangle {
            visible: item.badge > 0 && !item.collapsed
            radius: height / 2
            color: item.highlighted ? Kirigami.Theme.highlightedTextColor : item.badgeColor
            implicitHeight: badgeLabel.implicitHeight + Kirigami.Units.smallSpacing
            implicitWidth: Math.max(implicitHeight, badgeLabel.implicitWidth + Kirigami.Units.largeSpacing)
            QQC2.Label {
                id: badgeLabel
                anchors.centerIn: parent
                text: item.badge
                font.weight: Font.DemiBold
                font.pointSize: Kirigami.Theme.smallFont.pointSize
                font.features: { "tnum": 1 }
                color: item.highlighted ? item.badgeColor : "#ffffff"
            }
        }
    }
}
