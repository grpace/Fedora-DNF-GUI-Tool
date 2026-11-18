// An installed package or a repository search result.
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

QQC2.ItemDelegate {
    id: row

    required property int index
    required property string name
    required property string version
    required property string arch
    required property string repo
    required property string summary
    required property bool installed
    property bool findMode: false

    readonly property color dim: highlighted ? Kirigami.Theme.highlightedTextColor : Kirigami.ColorUtils.linearInterpolation(Kirigami.Theme.textColor, Kirigami.Theme.backgroundColor, 0.3)
    readonly property bool narrow: width < Kirigami.Units.gridUnit * 28

    text: name
    highlighted: ListView.isCurrentItem
    leftPadding: root.gutter
    rightPadding: root.gutter
    topPadding: Kirigami.Units.largeSpacing
    bottomPadding: Kirigami.Units.largeSpacing
    Accessible.description: version + (repo ? ", from " + repo : "") + (installed ? ", installed" : "")

    onClicked: {
        ListView.view.currentIndex = index;
        root.openPackageDetails(name);
    }
    Accessible.onPressAction: clicked()
    Keys.onReturnPressed: clicked()
    Keys.onEnterPressed: clicked()
    Keys.onMenuPressed: menu.popup(more, 0, more.height)
    Keys.onPressed: (event) => {
        if (event.key === Qt.Key_F10 && (event.modifiers & Qt.ShiftModifier)) {
            menu.popup(more, 0, more.height);
            event.accepted = true;
        }
    }

    contentItem: RowLayout {
        spacing: Kirigami.Units.largeSpacing
        AppIcon {
            name: row.name
            Layout.preferredWidth: Kirigami.Units.iconSizes.medium
            Layout.preferredHeight: Layout.preferredWidth
        }
        ColumnLayout {
            spacing: Kirigami.Units.smallSpacing / 2
            Layout.fillWidth: true
            QQC2.Label {
                text: row.name
                font.weight: Font.DemiBold
                elide: Text.ElideRight
                color: row.highlighted ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.textColor
                Layout.fillWidth: true
            }
            QQC2.Label {
                text: row.summary !== "" ? row.summary : row.version + (row.repo ? "  ·  " + row.repo : "")
                elide: Text.ElideRight
                color: row.dim
                font: Kirigami.Theme.smallFont
                Layout.fillWidth: true
            }
        }
        QQC2.Label {
            visible: row.summary !== "" && !row.narrow
            text: row.version
            color: row.dim
            font: Kirigami.Theme.smallFont
        }
        Pill {
            visible: row.findMode && row.installed
            text: "Installed"
            tone: "positive"
            selected: row.highlighted
        }
        QQC2.ToolButton {
            visible: row.findMode && !row.installed
            text: "Install"
            icon.source: root.ico("list-add", enabled)
            display: row.narrow ? QQC2.AbstractButton.IconOnly : QQC2.AbstractButton.TextBesideIcon
            enabled: !App.Runner.busy
            activeFocusOnTab: false
            Accessible.name: "Install " + row.name
            onClicked: App.Packages.install(row.name)
        }
        QQC2.ToolButton {
            id: more
            icon.source: root.ico("overflow-menu", enabled)
            text: "More Actions for " + row.name
            display: QQC2.AbstractButton.IconOnly
            activeFocusOnTab: false
            QQC2.ToolTip.text: "More Actions"
            QQC2.ToolTip.visible: hovered
            QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay
            onClicked: menu.popup(more, 0, more.height)
            QQC2.Menu {
                id: menu
                QQC2.MenuItem { text: "Show Details"; icon.source: root.ico("documentinfo", enabled); onTriggered: row.clicked() }
                QQC2.MenuItem {
                    text: "Copy Name"; icon.source: root.ico("edit-copy", enabled)
                    onTriggered: App.copyText(row.name)
                }
                QQC2.MenuSeparator { visible: row.installed }
                QQC2.MenuItem {
                    visible: row.installed
                    height: visible ? implicitHeight : 0
                    text: "Remove…"
                    icon.source: root.ico("edit-delete", enabled)
                    enabled: !App.Runner.busy
                    onTriggered: App.Packages.remove(row.name)
                }
            }
        }
    }
}
