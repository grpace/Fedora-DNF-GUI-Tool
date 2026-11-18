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
    implicitHeight: Kirigami.Units.gridUnit * (collapsed ? 2.8 : 2.2)
    Layout.leftMargin: Kirigami.Units.smallSpacing
    Layout.rightMargin: Kirigami.Units.smallSpacing

    // The count badge, expanded or collapsed: the darkened accent with
    // white text, or inverted on the selected entry (check_contrast.py
    // PRIMARY_MIX: both pairings pass AA in Breeze Light and Dark).
    readonly property color badgeColor: Qt.rgba(Kirigami.Theme.highlightColor.r * 0.7,
                                                Kirigami.Theme.highlightColor.g * 0.7,
                                                Kirigami.Theme.highlightColor.b * 0.7, 1)

    // Expanded: a full-width rounded row. Collapsed to the icon rail: a
    // rounded square centered on the icon, for both selection and hover.
    background: Item {
        Rectangle {
            anchors.centerIn: parent
            width: item.collapsed ? Math.min(parent.width, Kirigami.Units.gridUnit * 2.6) : parent.width
            height: item.collapsed ? width : parent.height
            radius: Kirigami.Units.cornerRadius * (item.collapsed ? 1.6 : 1)
            color: item.highlighted || item.down ? Kirigami.Theme.highlightColor
                 : item.hovered ? Qt.rgba(Kirigami.Theme.highlightColor.r, Kirigami.Theme.highlightColor.g,
                                          Kirigami.Theme.highlightColor.b, 0.18)
                 : "transparent"
            border.width: item.visualFocus ? 1 : 0
            border.color: item.highlighted ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.focusColor
        }
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
            // The count on the icon's corner when collapsed, ringed in the
            // color behind it so it stands off the icon and the highlight.
            Rectangle {
                visible: item.collapsed && item.badge > 0
                height: Math.round(Kirigami.Units.gridUnit * 0.95) + border.width * 2
                width: Math.max(height, railCount.implicitWidth + Kirigami.Units.smallSpacing * 1.5 + border.width * 2)
                radius: height / 2
                color: item.highlighted ? Kirigami.Theme.highlightedTextColor : item.badgeColor
                border.width: 2
                border.color: item.highlighted ? Kirigami.Theme.highlightColor : Kirigami.Theme.backgroundColor
                x: parent.width - width / 2
                y: -height / 2 + Kirigami.Units.smallSpacing / 2
                QQC2.Label {
                    id: railCount
                    anchors.fill: parent
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    text: item.badge > 99 ? "99+" : item.badge
                    font.weight: Font.Bold
                    font.pixelSize: Math.round(Kirigami.Units.gridUnit * 0.6)
                    font.features: { "tnum": 1 }
                    color: item.highlighted ? item.badgeColor : "#ffffff"
                }
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
            implicitHeight: Math.round(Kirigami.Units.gridUnit * 1.15)
            implicitWidth: Math.max(implicitHeight, badgeLabel.implicitWidth + Kirigami.Units.largeSpacing)
            QQC2.Label {
                id: badgeLabel
                anchors.fill: parent
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                topPadding: 0
                bottomPadding: 0
                text: item.badge
                font.weight: Font.DemiBold
                font.pointSize: Kirigami.Theme.smallFont.pointSize
                font.features: { "tnum": 1 }
                color: item.highlighted ? item.badgeColor : "#ffffff"
            }
        }
    }
}
