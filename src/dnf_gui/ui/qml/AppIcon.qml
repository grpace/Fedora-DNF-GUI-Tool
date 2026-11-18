// A package's picture: the app's own icon when the package is an app
// (from AppStream), a Flatpak's exported icon, or else a tinted tile with
// the package's first letter, so a list of libraries isn't a wall of
// identical boxes.
import QtQuick
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

Item {
    id: tile

    property string name
    property string appId          // Flatpak application id
    property bool runtime: false   // Flatpak runtime: a puzzle-piece glyph

    // White text on each passes WCAG AA (scripts/check_contrast.py, TILE_COLORS).
    readonly property var tileColors: ["#2563eb", "#4f46e5", "#7c3aed", "#be185d",
                                       "#c2410c", "#0f766e", "#15803d", "#0e7490"]
    readonly property var info: App.appIconsReady ? App.appIcon(name) : ({})
    readonly property string letter: {
        const m = String(name).match(/[A-Za-z0-9]/);
        return m ? m[0].toUpperCase() : "?";
    }
    readonly property color tint: {
        let h = 0;
        for (let i = 0; i < name.length; ++i)
            h = (h * 31 + name.charCodeAt(i)) % 9973;
        return tileColors[h % tileColors.length];
    }

    implicitWidth: Kirigami.Units.iconSizes.medium
    implicitHeight: implicitWidth
    Accessible.ignored: true

    Kirigami.Icon {
        id: image
        anchors.fill: parent
        source: tile.runtime ? root.ico("application-x-sharedlib", enabled, color)
              : tile.appId !== "" ? tile.appId
              : (tile.info.theme || tile.info.file || "")
        fallback: tile.runtime || tile.appId !== "" ? "" : (tile.info.file || "")
        color: Kirigami.Theme.textColor
        visible: String(source) !== "" && valid
    }

    Rectangle {
        anchors.fill: parent
        anchors.margins: parent.width * 0.06
        visible: !image.visible
        radius: width * 0.26
        color: tile.tint
        QQC2.Label {
            anchors.centerIn: parent
            text: tile.letter
            color: "#ffffff"
            font.weight: Font.Bold
            font.pixelSize: parent.height * 0.5
        }
    }
}
