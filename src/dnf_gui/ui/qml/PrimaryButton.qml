// The page's one main action: a filled button in a darkened accent color
// with white text (scripts/check_contrast.py PRIMARY_MIX: white on it
// passes WCAG AA in Breeze Light and Dark). Disabled, it looks like any
// disabled button.
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

QQC2.Button {
    id: control

    property string iconName

    // Accent darkened toward black: PRIMARY_MIX at rest, a little lighter
    // on hover, darker when pressed (all keep white text above 4.5:1).
    function shade(t) {
        const h = Kirigami.Theme.highlightColor;
        return Qt.rgba(h.r * (1 - t), h.g * (1 - t), h.b * (1 - t), 1);
    }
    readonly property color fill: down ? shade(0.40) : hovered ? shade(0.28) : shade(0.30)
    readonly property color fg: enabled ? "#ffffff" : Kirigami.Theme.disabledTextColor

    leftPadding: Kirigami.Units.largeSpacing * 1.5
    rightPadding: Kirigami.Units.largeSpacing * 1.5
    topPadding: Kirigami.Units.smallSpacing * 1.5
    bottomPadding: Kirigami.Units.smallSpacing * 1.5
    icon.source: root.ico(iconName, enabled, enabled ? "#ffffff" : undefined)

    background: Item {
        implicitHeight: Kirigami.Units.gridUnit * 1.6
        Rectangle {
            anchors.fill: parent
            radius: Kirigami.Units.cornerRadius
            color: control.enabled ? control.fill : Kirigami.Theme.backgroundColor
            border.width: control.enabled ? 0 : 1
            border.color: Kirigami.ColorUtils.linearInterpolation(
                Kirigami.Theme.backgroundColor, Kirigami.Theme.textColor, 0.2)
            Behavior on color { ColorAnimation { duration: Kirigami.Units.shortDuration } }
        }
        // Keyboard focus ring, just outside the fill.
        Rectangle {
            anchors.fill: parent
            anchors.margins: -3
            radius: Kirigami.Units.cornerRadius + 3
            color: "transparent"
            border.width: 2
            border.color: Kirigami.Theme.focusColor
            visible: control.visualFocus
        }
    }

    contentItem: RowLayout {
        spacing: Kirigami.Units.smallSpacing * 1.5
        Kirigami.Icon {
            visible: control.icon.source.toString() !== "" && control.display !== QQC2.AbstractButton.TextOnly
            source: control.icon.source
            implicitWidth: Kirigami.Units.iconSizes.small
            implicitHeight: implicitWidth
            Layout.alignment: Qt.AlignVCenter
        }
        QQC2.Label {
            visible: control.display !== QQC2.AbstractButton.IconOnly
            text: control.text
            textFormat: Text.PlainText
            color: control.fg
            font.weight: Font.DemiBold
            elide: Text.ElideRight
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignVCenter
            Accessible.ignored: true
        }
    }
}
