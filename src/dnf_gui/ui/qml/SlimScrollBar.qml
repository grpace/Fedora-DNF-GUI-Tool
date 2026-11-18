// A quiet scrollbar for the pages: a thin rounded handle over the content
// edge, no groove or border line. It shows while scrolling or when hovered,
// widens under the pointer, and can be dragged or clicked to page.
import QtQuick
import org.kde.kirigami as Kirigami

Item {
    id: bar

    property Flickable flickable
    readonly property real ratio: flickable ? flickable.visibleArea.heightRatio : 1
    readonly property real position: flickable ? flickable.visibleArea.yPosition : 0
    readonly property bool needed: !!flickable && ratio > 0 && ratio < 1
    readonly property bool engaged: hover.hovered || drag.active
    property bool recentlyMoved: false

    width: Kirigami.Units.smallSpacing * 3
    visible: needed
    Accessible.ignored: true  // the list itself scrolls with the keyboard

    function scrollTo(fraction) {
        const f = flickable;
        const range = Math.max(0, f.contentHeight - f.height);
        f.contentY = f.originY + Math.max(0, Math.min(range, fraction * f.contentHeight));
    }

    Connections {
        target: bar.flickable
        function onContentYChanged() {
            bar.recentlyMoved = true;
            fade.restart();
        }
    }
    Timer {
        id: fade
        interval: 1200
        onTriggered: bar.recentlyMoved = false
    }

    HoverHandler { id: hover }
    // Click above or below the handle: page up or down.
    TapHandler {
        onTapped: (point) => {
            const step = bar.ratio * 0.9;
            bar.scrollTo(point.position.y < handle.y ? bar.position - step : bar.position + step);
        }
    }

    Rectangle {
        id: handle
        readonly property real minimum: Kirigami.Units.gridUnit * 2
        width: bar.engaged ? Kirigami.Units.smallSpacing * 2 : Kirigami.Units.smallSpacing
        x: bar.width - width - 2
        height: Math.max(minimum, bar.ratio * bar.height)
        y: Math.min(bar.height - height, bar.position * bar.height)
        radius: width / 2
        color: Kirigami.Theme.textColor
        opacity: bar.engaged ? 0.55 : bar.recentlyMoved ? 0.35 : 0.0
        Behavior on width { NumberAnimation { duration: Kirigami.Units.shortDuration } }
        Behavior on opacity { NumberAnimation { duration: Kirigami.Units.longDuration } }

        DragHandler {
            id: drag
            target: null
            yAxis.enabled: true
            xAxis.enabled: false
            property real startPosition: 0
            onActiveChanged: if (active) startPosition = bar.position
            onTranslationChanged: bar.scrollTo(startPosition + translation.y / bar.height)
        }
    }
}
