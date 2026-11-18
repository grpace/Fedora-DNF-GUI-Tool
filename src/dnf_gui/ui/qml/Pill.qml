// Small status label ("Critical", "Core"): a status, never a verb. A soft
// tinted fill with tone-colored text, both from the Plasma color scheme;
// on a selected row it switches to the selection's text color so it stays
// readable on the highlight.
import QtQuick
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

Rectangle {
    id: pill

    property string text
    property string tone: "neutral"   // negative | neutral | info | positive | plain
    property bool selected: false

    readonly property color toneColor: tone === "negative" ? Kirigami.Theme.negativeTextColor
                                     : tone === "positive" ? Kirigami.Theme.positiveTextColor
                                     : tone === "info" ? Kirigami.Theme.linkColor
                                     : tone === "plain" ? Kirigami.Theme.textColor
                                     : Kirigami.Theme.neutralTextColor
    // Plasma's state colors are made for icons; as small text they need
    // pulling toward the text color to stay readable (scripts/check_contrast.py).
    // A plain RGB mix (ColorUtils.linearInterpolation goes through hue, so
    // orange toward gray turns green).
    readonly property color fg: selected ? Kirigami.Theme.highlightedTextColor
        : Qt.rgba(toneColor.r + (Kirigami.Theme.textColor.r - toneColor.r) * 0.4,
                  toneColor.g + (Kirigami.Theme.textColor.g - toneColor.g) * 0.4,
                  toneColor.b + (Kirigami.Theme.textColor.b - toneColor.b) * 0.4, 1)

    // The tone at 15% over the background (check_contrast.py PILL_FILL).
    readonly property real fillMix: 0.15
    readonly property color bg: Kirigami.Theme.backgroundColor

    radius: height / 2
    color: selected ? Qt.rgba(Kirigami.Theme.highlightedTextColor.r, Kirigami.Theme.highlightedTextColor.g,
                              Kirigami.Theme.highlightedTextColor.b, 0.2)
                    : Qt.rgba(bg.r + (toneColor.r - bg.r) * fillMix,
                              bg.g + (toneColor.g - bg.g) * fillMix,
                              bg.b + (toneColor.b - bg.b) * fillMix, 1)
    implicitHeight: label.implicitHeight + Kirigami.Units.smallSpacing
    implicitWidth: label.implicitWidth + Kirigami.Units.largeSpacing * 1.5
    Accessible.role: Accessible.StaticText
    Accessible.name: text

    QQC2.Label {
        id: label
        anchors.centerIn: parent
        text: pill.text
        textFormat: Text.PlainText
        color: pill.fg
        font.pointSize: Kirigami.Theme.smallFont.pointSize
        font.weight: Font.DemiBold
    }
}
