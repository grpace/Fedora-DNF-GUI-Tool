// Minimize, maximize/restore and close for the app's own title bar (the
// window has no system frame): quiet icon buttons in the top-right corner;
// Close turns red on hover, like other desktop apps.
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Row {
    id: controls

    readonly property bool maximized: root.visibility === Window.Maximized
                                      || root.visibility === Window.FullScreen
    spacing: 0
    Accessible.role: Accessible.ToolBar
    Accessible.name: "Window"

    component WindowButton: QQC2.AbstractButton {
        id: button
        property string iconName
        property bool danger: false
        width: Kirigami.Units.gridUnit * 2.4
        height: controls.height
        display: QQC2.AbstractButton.IconOnly
        focusPolicy: Qt.NoFocus  // KWin's shortcuts cover the keyboard
        hoverEnabled: true
        Accessible.role: Accessible.Button
        Accessible.name: text
        Accessible.onPressAction: clicked()
        QQC2.ToolTip.text: text
        QQC2.ToolTip.visible: hovered
        QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay

        background: Rectangle {
            color: button.danger && button.hovered ? "#c42b1c"
                 : button.pressed ? Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                                            Kirigami.Theme.textColor.b, 0.16)
                 : button.hovered ? Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                                            Kirigami.Theme.textColor.b, 0.09)
                 : "transparent"
        }
        contentItem: Item {
            Kirigami.Icon {
                anchors.centerIn: parent
                width: Kirigami.Units.iconSizes.small
                height: width
                source: root.ico(button.iconName, true,
                                 button.danger && button.hovered ? "#ffffff" : color)
                color: root.active ? Kirigami.Theme.textColor : Kirigami.Theme.disabledTextColor
            }
        }
    }

    WindowButton {
        text: "Minimize"
        iconName: "window-minimize"
        onClicked: root.showMinimized()
    }
    WindowButton {
        text: controls.maximized ? "Restore" : "Maximize"
        iconName: controls.maximized ? "window-restore" : "window-maximize"
        onClicked: root.toggleMaximized()
    }
    WindowButton {
        text: "Close"
        iconName: "window-close"
        danger: true
        onClicked: root.close()
    }
}
