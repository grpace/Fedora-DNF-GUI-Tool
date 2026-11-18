// Navigation drawer. Collapses to an icon rail on medium widths so a list
// and its details column still fit side by side on a laptop.
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.GlobalDrawer {
    id: drawer

    // Folds to icons on narrow windows; the header button overrides that
    // until the window crosses the width threshold again.
    property bool autoCollapsed: false
    property var userCollapsed: null
    onAutoCollapsedChanged: userCollapsed = null
    collapsed: userCollapsed === null ? autoCollapsed : userCollapsed

    modal: false
    collapsible: true
    collapseButtonVisible: false  // replaced by the header button
    collapsedSize: Kirigami.Units.gridUnit * 3.6  // a roomy icon rail
    // On the window color, no edge line: the content panel's border is the divider.
    background: Item {}
    showHeaderWhenCollapsed: true
    preferredSize: Kirigami.Units.gridUnit * 13  // expanded width; collapsing animates
    // Keep the nav entries (icons, badge dot, tooltips) as a rail.
    showContentWhenCollapsed: true
    padding: 0

    readonly property var sections: [
        { title: "Packages", items: [
            { key: "updates", label: "Updates", icon: "system-software-update" },
            { key: "installed", label: "Installed", icon: "package" },
            { key: "flatpak", label: "Flatpak", icon: "flatpak-discover", fallback: "folder-flatpak" } ] },
        { title: "System", items: [
            { key: "sysinfo", label: "System", icon: "computer" },
            { key: "tools", label: "Tools", icon: "tools" },
            { key: "repos", label: "Repositories", icon: "repository" },
            { key: "history", label: "History", icon: "view-history" },
            { key: "settings", label: "Settings", icon: "settings-configure" } ] }
    ]

    header: Kirigami.AbstractApplicationHeader {
        // Part of the title bar: on the window color, with no lines.
        separatorVisible: false
        Component.onCompleted: {
            background.color = "transparent";
            root.hideTopSeparator(this);
        }
        topPadding: Kirigami.Units.smallSpacing
        bottomPadding: Kirigami.Units.smallSpacing
        leftPadding: Kirigami.Units.largeSpacing
        rightPadding: Kirigami.Units.smallSpacing
        // Part of the app's title bar: drag to move, double-click to maximize.
        DragHandler {
            target: null
            onActiveChanged: if (active) root.startSystemMove()
        }
        TapHandler {
            acceptedButtons: Qt.LeftButton
            onDoubleTapped: root.toggleMaximized()
        }
        contentItem: RowLayout {
            spacing: Kirigami.Units.smallSpacing
            Kirigami.Icon {
                source: root.appIcon
                fallback: "system-software-update"
                implicitWidth: Kirigami.Units.iconSizes.smallMedium
                implicitHeight: implicitWidth
                visible: !drawer.collapsed
            }
            Kirigami.Heading {
                level: 4
                text: "DNF Package Manager"
                elide: Text.ElideRight
                visible: !drawer.collapsed
                Layout.fillWidth: true
            }
            QQC2.ToolButton {
                id: sidebarToggle
                objectName: "sidebarToggle"
                display: QQC2.AbstractButton.IconOnly
                icon.source: root.ico("sidebar-collapse", enabled)
                icon.width: Kirigami.Units.iconSizes.smallMedium
                icon.height: Kirigami.Units.iconSizes.smallMedium
                text: drawer.collapsed ? "Expand Sidebar" : "Collapse Sidebar"
                Accessible.name: text
                QQC2.ToolTip.text: text
                QQC2.ToolTip.visible: hovered
                QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay
                // On the icon rail it is as wide as the rail items, with the same hover.
                Layout.preferredWidth: Kirigami.Units.gridUnit * (drawer.collapsed ? 2.6 : 2.1)
                Layout.preferredHeight: Kirigami.Units.gridUnit * 2.1
                Layout.alignment: drawer.collapsed ? Qt.AlignHCenter : Qt.AlignRight
                background: Rectangle {
                    radius: Kirigami.Units.cornerRadius * (drawer.collapsed ? 1.6 : 1)
                    color: sidebarToggle.down ? Qt.rgba(Kirigami.Theme.highlightColor.r, Kirigami.Theme.highlightColor.g,
                                                        Kirigami.Theme.highlightColor.b, 0.3)
                         : sidebarToggle.hovered ? Qt.rgba(Kirigami.Theme.highlightColor.r, Kirigami.Theme.highlightColor.g,
                                                           Kirigami.Theme.highlightColor.b, 0.18)
                         : "transparent"
                    border.width: sidebarToggle.visualFocus ? 1 : 0
                    border.color: Kirigami.Theme.focusColor
                }
                // The desktop style draws a button's icon in its background,
                // which this one replaces, so the icon is drawn here.
                contentItem: Item {
                    Kirigami.Icon {
                        anchors.centerIn: parent
                        width: Kirigami.Units.iconSizes.smallMedium
                        height: width
                        source: sidebarToggle.icon.source
                    }
                }
                onClicked: drawer.userCollapsed = !drawer.collapsed
            }
        }
    }

    ColumnLayout {
        spacing: 0
        Layout.fillWidth: true
        Layout.fillHeight: true

        Repeater {
            model: drawer.sections
            delegate: ColumnLayout {
                id: section
                required property var modelData
                spacing: 0
                Layout.fillWidth: true

                // A quiet group label (no rule): small, dimmed, in line
                // with the entries' icons.
                QQC2.Label {
                    text: section.modelData.title
                    visible: !drawer.collapsed
                    font.pointSize: Kirigami.Theme.smallFont.pointSize
                    font.weight: Font.DemiBold
                    color: Kirigami.ColorUtils.linearInterpolation(Kirigami.Theme.textColor, Kirigami.Theme.backgroundColor, 0.3)
                    elide: Text.ElideRight
                    Accessible.role: Accessible.Heading
                    Layout.fillWidth: true
                    Layout.leftMargin: Kirigami.Units.smallSpacing + Kirigami.Units.largeSpacing
                    Layout.topMargin: Kirigami.Units.largeSpacing * 1.5
                    Layout.bottomMargin: Kirigami.Units.smallSpacing
                }
                Kirigami.Separator {
                    visible: drawer.collapsed && section.modelData.title !== "Packages"
                    Layout.fillWidth: true
                    Layout.topMargin: Kirigami.Units.smallSpacing
                    Layout.bottomMargin: Kirigami.Units.smallSpacing
                }
                Repeater {
                    model: section.modelData.items
                    delegate: NavItem {
                        required property var modelData
                        key: modelData.key
                        label: modelData.label
                        iconName: modelData.icon
                        iconFallback: modelData.fallback || "application-x-executable"
                        badge: modelData.key === "updates" ? App.updateBadge : 0
                        collapsed: drawer.collapsed
                        Layout.fillWidth: true
                    }
                }
            }
        }

        Item { Layout.fillHeight: true }

        NavItem {
            key: "activity"
            label: App.Runner.busy ? "Working…" : "Output"
            iconName: App.Runner.busy ? "view-refresh" : "utilities-terminal"
            collapsed: drawer.collapsed
            selectable: false
            onTriggered: App.toggleActivity(!App.activityExpanded)
            Layout.fillWidth: true
        }
        NavItem {
            key: "app-update"
            visible: !!App.appUpdate.available && !App.appUpdate.dismissed
            label: "Version " + (App.appUpdate.version || "") + " Available"
            iconName: "update-high"
            collapsed: drawer.collapsed
            selectable: false
            onTriggered: App.navigate("settings")
            Layout.fillWidth: true
        }
        // The version, and the project on GitHub.
        RowLayout {
            visible: !drawer.collapsed
            spacing: Kirigami.Units.smallSpacing
            Layout.fillWidth: true
            Layout.margins: Kirigami.Units.largeSpacing
            Layout.leftMargin: Kirigami.Units.smallSpacing + Kirigami.Units.largeSpacing
            Layout.rightMargin: Kirigami.Units.smallSpacing + Kirigami.Units.largeSpacing
            QQC2.Label {
                text: "Version " + App.version
                color: Kirigami.ColorUtils.linearInterpolation(Kirigami.Theme.textColor, Kirigami.Theme.backgroundColor, 0.3)
                font: Kirigami.Theme.smallFont
                Layout.fillWidth: true
            }
            QQC2.AbstractButton {
                id: githubLink
                objectName: "githubLink"
                text: "GitHub"
                hoverEnabled: true
                focusPolicy: Qt.TabFocus
                Accessible.role: Accessible.Link
                Accessible.name: "DNF Package Manager on GitHub"
                Accessible.onPressAction: clicked()
                QQC2.ToolTip.text: "github.com/grpace/Fedora-DNF-GUI-Tool"
                QQC2.ToolTip.visible: hovered
                QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay
                leftPadding: Kirigami.Units.smallSpacing * 1.5
                rightPadding: Kirigami.Units.smallSpacing * 2
                topPadding: Kirigami.Units.smallSpacing / 2
                bottomPadding: Kirigami.Units.smallSpacing / 2
                background: Rectangle {
                    radius: height / 2
                    color: githubLink.hovered || githubLink.visualFocus
                           ? Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.12)
                           : "transparent"
                    border.width: 1
                    border.color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b,
                                          githubLink.visualFocus ? 0.6 : 0.2)
                }
                contentItem: RowLayout {
                    spacing: Kirigami.Units.smallSpacing
                    Kirigami.Icon {
                        source: root.ico("github", true, color)
                        color: Kirigami.Theme.textColor
                        implicitWidth: Kirigami.Units.iconSizes.small
                        implicitHeight: implicitWidth
                    }
                    QQC2.Label {
                        text: githubLink.text
                        font: Kirigami.Theme.smallFont
                    }
                }
                HoverHandler { cursorShape: Qt.PointingHandCursor }
                onClicked: App.openProject()
            }
        }
    }
}
