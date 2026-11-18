// A list section header on the page's spacing scale: its text lines up
// with the rows' content at the page gutter.
import QtQuick
import org.kde.kirigami as Kirigami

Kirigami.ListSectionHeader {
    leftPadding: root.gutter
    rightPadding: root.gutter
    topPadding: Kirigami.Units.gridUnit
    bottomPadding: Kirigami.Units.smallSpacing
}
