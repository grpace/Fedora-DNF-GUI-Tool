// Window-level activity bar: what's running, its progress, and dnf's live
// output. Follows you between pages and stays after an operation ends so
// results and errors can be read; failures open the log automatically.
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

QQC2.Pane {
    id: bar

    readonly property var runner: App.Runner
    readonly property string status: runner.status
    readonly property bool expanded: App.activityExpanded

    padding: Kirigami.Units.largeSpacing
    Kirigami.Theme.colorSet: Kirigami.Theme.Window
    Kirigami.Theme.inherit: false

    background: Rectangle {
        color: Kirigami.Theme.backgroundColor
        Kirigami.Separator {
            anchors { top: parent.top; left: parent.left; right: parent.right }
        }
    }

    contentItem: ColumnLayout {
        spacing: Kirigami.Units.smallSpacing

        RowLayout {
            spacing: Kirigami.Units.largeSpacing
            Layout.fillWidth: true

            Item {
                implicitWidth: Kirigami.Units.iconSizes.smallMedium
                implicitHeight: implicitWidth
                QQC2.BusyIndicator {
                    anchors.fill: parent
                    visible: bar.runner.busy
                    running: visible
                }
                Kirigami.Icon {
                    anchors.fill: parent
                    visible: !bar.runner.busy
                    source: bar.status === "succeeded" ? "emblem-success"
                          : bar.status === "failed" ? "emblem-error"
                          : bar.status === "cancelled" ? "emblem-warning"
                          : "utilities-terminal"
                }
            }

            ColumnLayout {
                spacing: 0
                Layout.fillWidth: true
                QQC2.Label {
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                    font.weight: Font.DemiBold
                    text: bar.status === "auth" ? "Waiting for Your Password…"
                        : bar.runner.operation !== "" ? bar.runner.operation
                        : "Output"
                    Accessible.role: Accessible.StaticText
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                    font: Kirigami.Theme.smallFont
                    color: bar.status === "failed" ? Kirigami.Theme.negativeTextColor
                         : Kirigami.ColorUtils.linearInterpolation(Kirigami.Theme.textColor, Kirigami.Theme.backgroundColor, 0.3)
                    text: bar.status === "auth" ? "Approve the system prompt to continue."
                        : bar.runner.busy ? (bar.runner.cancelling ? "Cancelling…"
                                             : bar.runner.step || "Working…")
                        : bar.runner.statusText || "Nothing running."
                }
            }

            QQC2.Button {
                text: "Cancel"
                icon.name: "dialog-cancel"
                visible: bar.runner.busy
                enabled: !bar.runner.cancelling
                onClicked: bar.runner.cancel()
            }
            QQC2.ToolButton {
                text: bar.expanded ? "Hide Output" : "Show Output"
                icon.name: bar.expanded ? "arrow-down" : "arrow-up"
                display: root.compact ? QQC2.AbstractButton.IconOnly : QQC2.AbstractButton.TextBesideIcon
                QQC2.ToolTip.text: text + " (Ctrl+T)"
                QQC2.ToolTip.visible: hovered
                QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay
                onClicked: App.toggleActivity(!bar.expanded)
            }
            QQC2.ToolButton {
                icon.name: "window-close"
                text: "Close Output"
                display: QQC2.AbstractButton.IconOnly
                visible: !bar.runner.busy
                QQC2.ToolTip.text: text
                QQC2.ToolTip.visible: hovered
                QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay
                onClicked: App.closeActivity()
            }
        }

        QQC2.ProgressBar {
            Layout.fillWidth: true
            visible: bar.runner.busy
            from: 0; to: 1
            value: bar.runner.progress >= 0 ? bar.runner.progress : 0
            indeterminate: bar.runner.progress < 0
            Accessible.name: bar.runner.step || "Working"
        }

        // ── Log ──
        ColumnLayout {
            visible: bar.expanded
            spacing: Kirigami.Units.smallSpacing
            Layout.fillWidth: true

            QQC2.Frame {
                Layout.fillWidth: true
                Layout.preferredHeight: Math.min(Kirigami.Units.gridUnit * 14,
                                                 root.height * 0.4)
                padding: 0
                Kirigami.Theme.colorSet: Kirigami.Theme.View
                Kirigami.Theme.inherit: false
                background: Rectangle {
                    color: Kirigami.Theme.backgroundColor
                    border.color: Kirigami.ColorUtils.linearInterpolation(
                        Kirigami.Theme.backgroundColor, Kirigami.Theme.textColor, 0.2)
                    radius: Kirigami.Units.cornerRadius
                }

                ListView {
                    id: log
                    anchors.fill: parent
                    anchors.margins: Kirigami.Units.smallSpacing
                    clip: true
                    model: bar.runner.log
                    boundsBehavior: Flickable.StopAtBounds
                    Accessible.name: "Command Output"
                    QQC2.ScrollBar.vertical: QQC2.ScrollBar {}
                    property bool following: true
                    onMovementEnded: following = atYEnd
                    onCountChanged: if (following) positionViewAtEnd()
                    delegate: QQC2.Label {
                        required property string line
                        width: ListView.view.width - Kirigami.Units.largeSpacing
                        text: line
                        font.family: "monospace"
                        font.pointSize: Kirigami.Theme.smallFont.pointSize
                        wrapMode: Text.WrapAnywhere
                        textFormat: Text.PlainText
                        color: line.indexOf("✗") === 0 || line.indexOf("❌") >= 0
                               ? Kirigami.Theme.negativeTextColor
                               : line.indexOf("⚠") >= 0 ? Kirigami.Theme.neutralTextColor
                               : Kirigami.Theme.textColor
                    }
                    Kirigami.PlaceholderMessage {
                        anchors.centerIn: parent
                        width: parent.width - Kirigami.Units.gridUnit * 4
                        visible: log.count === 0
                        text: "No Output Yet"
                        explanation: "Commands you run show their output here."
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                QQC2.Button {
                    text: "Copy Output"
                    icon.name: "edit-copy"
                    enabled: log.count > 0
                    onClicked: bar.runner.copyToClipboard()
                }
                QQC2.Button {
                    text: "Clear"
                    icon.name: "edit-clear-history"
                    enabled: log.count > 0 && !bar.runner.busy
                    onClicked: bar.runner.clear()
                }
            }
        }
    }
}
