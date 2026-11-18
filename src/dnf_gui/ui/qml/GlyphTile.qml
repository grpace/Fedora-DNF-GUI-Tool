// A row's leading glyph on a soft rounded tile (Tools, Repositories,
// History): lighter than a bare 32px glyph, and the same footprint as the
// app icons on the package lists.
import QtQuick
import org.kde.kirigami as Kirigami

Rectangle {
    id: tile

    property string iconName
    property bool selected: false   // on a highlighted row

    readonly property real size: Kirigami.Units.iconSizes.medium
    readonly property color ink: selected ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.textColor

    implicitWidth: size
    implicitHeight: size
    radius: size * 0.26
    color: Qt.rgba(ink.r, ink.g, ink.b, selected ? 0.16 : 0.08)
    Accessible.ignored: true

    Kirigami.Icon {
        anchors.centerIn: parent
        implicitWidth: Math.round(tile.size * 0.625)
        implicitHeight: implicitWidth
        source: root.ico(tile.iconName, tile.enabled, color)
        color: tile.ink
    }
}
