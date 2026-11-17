// Small status label ("Critical", "Major"). Colors come from the Plasma
// color scheme; on a selected row it switches to the selection's text
// color so it stays readable on the highlight.
import QtQuick
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

Rectangle {
    id: pill

    property string text
    property string tone: "neutral"   // negative | neutral | info | positive
    property bool selected: false

    readonly property color toneColor: tone === "negative" ? Kirigami.Theme.negativeTextColor
                                     : tone === "positive" ? Kirigami.Theme.positiveTextColor
                                     : tone === "info" ? Kirigami.Theme.linkColor
                                     : Kirigami.Theme.neutralTextColor
    // Plasma's state colors are made for icons; as small text they need
    // pulling toward the text color to stay readable (scripts/check_contrast.py).
    // A plain RGB mix (ColorUtils.linearInterpolation goes through hue, so
    // orange toward gray turns green).
    readonly property color fg: selected ? Kirigami.Theme.highlightedTextColor
        : Qt.rgba(toneColor.r + (Kirigami.Theme.textColor.r - toneColor.r) * 0.4,
                  toneColor.g + (Kirigami.Theme.textColor.g - toneColor.g) * 0.4,
                  toneColor.b + (Kirigami.Theme.textColor.b - toneColor.b) * 0.4, 1)

    radius: height / 2
    color: "transparent"
    border.width: 1
    border.color: fg
    implicitHeight: label.implicitHeight + Kirigami.Units.smallSpacing / 2
    implicitWidth: label.implicitWidth + Kirigami.Units.largeSpacing * 1.5
    Accessible.role: Accessible.StaticText
    Accessible.name: text

    QQC2.Label {
        id: label
        anchors.centerIn: parent
        text: pill.text
        color: pill.fg
        font.pointSize: Kirigami.Theme.smallFont.pointSize
        font.weight: Font.DemiBold
    }
}
