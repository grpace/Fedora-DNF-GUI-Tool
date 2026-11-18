// What's running, as a floating capsule over the bottom of the pages: a
// progress ring, the operation and its current step, Cancel, and the output.
// Show Output grows the capsule into a panel with dnf's live log. It follows
// you between pages and stays after an operation ends so the result can be
// read; failures open the log automatically.
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import QtQuick.Shapes
import org.kde.kirigami as Kirigami

Item {
    id: bar

    readonly property var runner: App.Runner
    readonly property string status: runner.status
    readonly property bool expanded: App.activityExpanded
    readonly property bool busy: runner.busy
    readonly property bool determinate: busy && runner.progress >= 0
    // Space the pages leave free under them: the capsule's own height, so
    // the open log floats over the page instead of squeezing it.
    readonly property real reservedHeight: capsuleHeight + Kirigami.Units.largeSpacing * 2
    readonly property real capsuleHeight: Kirigami.Units.gridUnit * 3
    readonly property color dimText: Kirigami.ColorUtils.linearInterpolation(
        Kirigami.Theme.textColor, Kirigami.Theme.backgroundColor, 0.3)
    readonly property color stateColor: status === "failed" ? Kirigami.Theme.negativeTextColor
                                      : status === "succeeded" ? Kirigami.Theme.positiveTextColor
                                      : status === "cancelled" ? Kirigami.Theme.neutralTextColor
                                      : Kirigami.Theme.highlightColor

    implicitHeight: card.height + Kirigami.Units.largeSpacing * 2
    Kirigami.Theme.colorSet: Kirigami.Theme.View
    Kirigami.Theme.inherit: false

    // Say when an operation needs a password, finishes or fails: a screen
    // reader user waiting in the window gets no desktop notification.
    property string spokenStatus: ""
    Connections {
        target: bar.runner
        function onChanged() {
            const s = bar.runner.status;
            // A finished run's text can change after it ends ("… Skipped").
            const key = s + ":" + (s === "succeeded" ? bar.runner.statusText : "");
            if (key === bar.spokenStatus)
                return;
            bar.spokenStatus = key;
            const op = bar.runner.operation;
            const message = s === "auth" ? op + ": waiting for your password"
                          : s === "succeeded" ? op + ": " + bar.runner.statusText
                          : s === "failed" ? op + " failed. The output is open."
                          : s === "cancelled" ? op + " was cancelled."
                          : "";
            if (message !== "")
                card.Accessible.announce(message);
            if (s === "failed")
                focusLog.restart();  // after the log opens
        }
    }
    Timer {
        id: focusLog
        interval: 50
        onTriggered: logArea.forceActiveFocus()
    }

    // Close the log and give focus back to the page you were on.
    function closeLog() {
        App.toggleActivity(false);
        root.pageStack.get(root.pageStack.depth - 1).forceActiveFocus();
    }

    Kirigami.ShadowedRectangle {
        id: card

        readonly property real pad: Kirigami.Units.largeSpacing
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: Kirigami.Units.largeSpacing
        width: Math.min(parent.width - Kirigami.Units.largeSpacing * 2,
                        bar.expanded ? Kirigami.Units.gridUnit * 56 : Kirigami.Units.gridUnit * 34)
        height: bar.expanded ? Math.min(Kirigami.Units.gridUnit * 22, root.height * 0.55)
                             : bar.capsuleHeight
        radius: bar.expanded ? Kirigami.Units.gridUnit : height / 2
        color: Kirigami.Theme.backgroundColor
        border.width: 1
        border.color: Kirigami.ColorUtils.linearInterpolation(
            Kirigami.Theme.backgroundColor, Kirigami.Theme.textColor, 0.15)
        shadow.size: Kirigami.Units.gridUnit * 1.2
        shadow.yOffset: 2
        shadow.color: Qt.rgba(0, 0, 0, 0.28)
        Accessible.role: Accessible.Grouping
        Accessible.name: "Activity"

        // Clicks and scrolls on the panel stay on it, not the list beneath.
        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.AllButtons
            onWheel: (wheel) => wheel.accepted = true
        }

        Behavior on width { NumberAnimation { duration: Kirigami.Units.longDuration; easing.type: Easing.OutCubic } }
        Behavior on height { NumberAnimation { duration: Kirigami.Units.longDuration; easing.type: Easing.OutCubic } }
        Behavior on radius { NumberAnimation { duration: Kirigami.Units.longDuration; easing.type: Easing.OutCubic } }

        ColumnLayout {
            anchors.fill: parent
            anchors.leftMargin: card.pad * 1.25
            anchors.rightMargin: card.pad
            anchors.topMargin: 0
            anchors.bottomMargin: bar.expanded ? card.pad : 0
            spacing: Kirigami.Units.smallSpacing
            clip: true

            // ── The capsule row ──
            RowLayout {
                spacing: Kirigami.Units.largeSpacing
                Layout.fillWidth: true
                Layout.preferredHeight: bar.capsuleHeight
                Layout.maximumHeight: bar.capsuleHeight

                // Progress ring with the percentage, a spinner when dnf gives
                // no count, or the result's icon once it ends.
                Item {
                    id: indicator
                    readonly property real size: Kirigami.Units.gridUnit * 2
                    implicitWidth: size
                    implicitHeight: size
                    Layout.alignment: Qt.AlignVCenter

                    Shape {
                        anchors.fill: parent
                        visible: bar.determinate
                        preferredRendererType: Shape.CurveRenderer
                        ShapePath {
                            strokeColor: Kirigami.ColorUtils.linearInterpolation(
                                Kirigami.Theme.backgroundColor, Kirigami.Theme.textColor, 0.15)
                            strokeWidth: indicator.size * 0.11
                            fillColor: "transparent"
                            PathAngleArc {
                                centerX: indicator.size / 2; centerY: indicator.size / 2
                                radiusX: indicator.size / 2 - indicator.size * 0.08
                                radiusY: radiusX
                                startAngle: 0; sweepAngle: 360
                            }
                        }
                        ShapePath {
                            strokeColor: Kirigami.Theme.highlightColor
                            strokeWidth: indicator.size * 0.11
                            fillColor: "transparent"
                            capStyle: ShapePath.RoundCap
                            PathAngleArc {
                                centerX: indicator.size / 2; centerY: indicator.size / 2
                                radiusX: indicator.size / 2 - indicator.size * 0.08
                                radiusY: radiusX
                                startAngle: -90
                                sweepAngle: Math.max(2, 360 * bar.runner.progress)
                                Behavior on sweepAngle { NumberAnimation { duration: Kirigami.Units.longDuration } }
                            }
                        }
                    }
                    QQC2.Label {
                        anchors.centerIn: parent
                        visible: bar.determinate
                        text: Math.round(bar.runner.progress * 100)
                        font.pixelSize: indicator.size * 0.32
                        font.weight: Font.DemiBold
                        font.features: { "tnum": 1 }
                        Accessible.ignored: true
                    }
                    QQC2.BusyIndicator {
                        anchors.fill: parent
                        visible: bar.busy && !bar.determinate
                        running: visible
                    }
                    Kirigami.Icon {
                        anchors.fill: parent
                        anchors.margins: indicator.size * 0.08
                        visible: !bar.busy
                        source: root.ico(bar.status === "succeeded" ? "emblem-success"
                                       : bar.status === "failed" ? "dialog-cancel"
                                       : bar.status === "cancelled" ? "emblem-warning"
                                       : "utilities-terminal", enabled, color)
                        color: bar.status === "idle" ? Kirigami.Theme.textColor : bar.stateColor
                    }
                }

                ColumnLayout {
                    spacing: 0
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignVCenter
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
                        color: bar.status === "failed" ? Kirigami.Theme.negativeTextColor : bar.dimText
                        text: bar.status === "auth" ? "Approve the system prompt to continue."
                            : bar.busy ? (bar.runner.cancelling ? "Cancelling…"
                                         : bar.runner.step || "Working…")
                            : bar.runner.statusText || "Nothing running."
                    }
                }

                QQC2.ToolButton {
                    text: "Cancel"
                    icon.source: root.ico("dialog-cancel", enabled)
                    display: root.compact ? QQC2.AbstractButton.IconOnly : QQC2.AbstractButton.TextBesideIcon
                    // Downloads of the app's own update can't be cancelled.
                    visible: bar.busy && bar.runner.cancellable
                    enabled: !bar.runner.cancelling
                    Accessible.name: text
                    QQC2.ToolTip.text: text
                    QQC2.ToolTip.visible: hovered && display === QQC2.AbstractButton.IconOnly
                    onClicked: bar.runner.cancel()
                    Layout.alignment: Qt.AlignVCenter
                }
                QQC2.ToolButton {
                    text: bar.expanded ? "Hide Output" : "Show Output"
                    icon.source: root.ico(bar.expanded ? "arrow-down" : "utilities-terminal", enabled)
                    display: root.compact ? QQC2.AbstractButton.IconOnly : QQC2.AbstractButton.TextBesideIcon
                    checkable: false
                    Accessible.name: text
                    QQC2.ToolTip.text: text + " (Ctrl+T)"
                    QQC2.ToolTip.visible: hovered
                    QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay
                    onClicked: App.toggleActivity(!bar.expanded)
                    Layout.alignment: Qt.AlignVCenter
                }
                QQC2.ToolButton {
                    icon.source: root.ico("window-close", enabled)
                    text: "Close Output"
                    display: QQC2.AbstractButton.IconOnly
                    visible: !bar.busy
                    Accessible.name: text
                    QQC2.ToolTip.text: text
                    QQC2.ToolTip.visible: hovered
                    QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay
                    onClicked: App.closeActivity()
                    Layout.alignment: Qt.AlignVCenter
                }
            }

            // Thin progress line under the row while the log is open (the
            // ring is still there; this one spans the panel).
            Rectangle {
                visible: bar.expanded && bar.busy
                Layout.fillWidth: true
                Layout.preferredHeight: 3
                radius: 1.5
                color: Kirigami.ColorUtils.linearInterpolation(
                    Kirigami.Theme.backgroundColor, Kirigami.Theme.textColor, 0.12)
                Rectangle {
                    height: parent.height
                    radius: parent.radius
                    width: parent.width * (bar.determinate ? bar.runner.progress : 0.3)
                    color: Kirigami.Theme.highlightColor
                    Behavior on width { NumberAnimation { duration: Kirigami.Units.longDuration } }
                }
            }

            // ── Log ──
            Rectangle {
                visible: bar.expanded
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: Kirigami.Units.cornerRadius * 2
                Kirigami.Theme.colorSet: Kirigami.Theme.Window
                Kirigami.Theme.inherit: false
                color: Kirigami.Theme.backgroundColor

                // Read-only text, so the keyboard and screen readers can move
                // through it like any document.
                QQC2.ScrollView {
                    id: logScroll
                    anchors.fill: parent
                    anchors.margins: Kirigami.Units.smallSpacing
                    QQC2.TextArea {
                        id: logArea
                        readOnly: true
                        textFormat: TextEdit.PlainText
                        wrapMode: TextEdit.WrapAnywhere
                        font.family: "monospace"
                        font.pointSize: Kirigami.Theme.smallFont.pointSize
                        selectByMouse: true
                        activeFocusOnTab: true
                        background: null
                        Accessible.name: "Command output"
                        Keys.onEscapePressed: (event) => {
                            bar.closeLog();
                            event.accepted = true;
                        }
                    }
                }
                Connections {
                    target: bar.runner.log
                    function onAppended(text) {
                        logArea.append(text);
                        if (!logArea.activeFocus)
                            logArea.cursorPosition = logArea.length;  // follow the end
                    }
                    function onCleared() { logArea.clear(); }
                }
                Kirigami.PlaceholderMessage {
                    anchors.centerIn: parent
                    width: parent.width - Kirigami.Units.gridUnit * 4
                    visible: bar.runner.log.count === 0
                    icon.source: root.ico("utilities-terminal", enabled)
                    text: "No Output Yet"
                    explanation: "Commands you run show their output here."
                }
            }

            RowLayout {
                visible: bar.expanded
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                QQC2.ToolButton {
                    text: "Copy Output"
                    icon.source: root.ico("edit-copy", enabled)
                    enabled: bar.runner.log.count > 0
                    onClicked: bar.runner.copyToClipboard()
                }
                QQC2.ToolButton {
                    text: "Clear"
                    icon.source: root.ico("edit-clear-history", enabled)
                    enabled: bar.runner.log.count > 0 && !bar.busy
                    onClicked: bar.runner.clear()
                }
            }
        }
    }
}
