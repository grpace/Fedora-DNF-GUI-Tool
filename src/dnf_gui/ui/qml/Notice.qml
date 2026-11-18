// A compact one-row notice: tone icon, bold title, the body on the same
// line (dimmed, elided), a chevron that unfolds the full body when it
// doesn't fit, the actions (the first visible one is the primary, framed
// button; the rest are flat) and an icon-only dismiss button.
// Every text is plain text: screen readers get the sentence, never markup.
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

QQC2.Control {
    id: notice

    property string title
    property string body
    property string iconName
    property string tone: "warning"   // warning | information | positive | negative
    // The first visible action is the primary button.
    property list<Kirigami.Action> actions
    // Icon-only close button; its text is the tooltip and accessible name
    // ("Later", "Not Now").
    property Kirigami.Action dismissAction: null
    property bool expanded: false

    readonly property bool narrow: root.compact || width < Kirigami.Units.gridUnit * 30
    readonly property color toneColor: tone === "information" ? Kirigami.Theme.highlightColor
                                     : tone === "positive" ? Kirigami.Theme.positiveTextColor
                                     : tone === "negative" ? Kirigami.Theme.negativeTextColor
                                     : Kirigami.Theme.neutralTextColor
    // Tone at 12% over the view background (scripts/check_contrast.py NOTICE_MIX).
    readonly property real tintMix: 0.12
    readonly property color fill: Qt.rgba(
        Kirigami.Theme.backgroundColor.r + (toneColor.r - Kirigami.Theme.backgroundColor.r) * tintMix,
        Kirigami.Theme.backgroundColor.g + (toneColor.g - Kirigami.Theme.backgroundColor.g) * tintMix,
        Kirigami.Theme.backgroundColor.b + (toneColor.b - Kirigami.Theme.backgroundColor.b) * tintMix, 1)
    readonly property color dim: Qt.rgba(
        Kirigami.Theme.textColor.r + (fill.r - Kirigami.Theme.textColor.r) * 0.3,
        Kirigami.Theme.textColor.g + (fill.g - Kirigami.Theme.textColor.g) * 0.3,
        Kirigami.Theme.textColor.b + (fill.b - Kirigami.Theme.textColor.b) * 0.3, 1)

    readonly property var shownActions: {
        const list = [];
        for (let i = 0; i < actions.length; ++i)
            if (actions[i].visible)
                list.push(actions[i]);
        return list;
    }
    readonly property var primaryAction: shownActions.length > 0 ? shownActions[0] : null
    readonly property var extraActions: shownActions.slice(1)
    // The body has more to show than the row holds.
    readonly property bool bodyHidden: body !== "" && (narrow || inlineBody.truncated || titleLabel.truncated)

    Kirigami.Theme.colorSet: Kirigami.Theme.View
    Kirigami.Theme.inherit: false

    Layout.fillWidth: true
    leftPadding: Kirigami.Units.largeSpacing
    rightPadding: Kirigami.Units.smallSpacing
    topPadding: Kirigami.Units.smallSpacing
    bottomPadding: Kirigami.Units.smallSpacing

    Accessible.role: Accessible.AlertMessage
    Accessible.name: title
    Accessible.description: body

    background: Rectangle {
        radius: Kirigami.Units.cornerRadius
        color: notice.fill
        border.width: 1
        border.color: Qt.rgba(notice.toneColor.r, notice.toneColor.g, notice.toneColor.b, 0.25)
    }

    contentItem: ColumnLayout {
        spacing: 0

        RowLayout {
            spacing: Kirigami.Units.largeSpacing
            Layout.fillWidth: true
            Layout.minimumHeight: Kirigami.Units.gridUnit * 2

            Kirigami.Icon {
                source: root.ico(notice.iconName, true, color)
                color: notice.toneColor
                implicitWidth: Kirigami.Units.iconSizes.small
                implicitHeight: implicitWidth
                Layout.alignment: notice.expanded ? Qt.AlignTop : Qt.AlignVCenter
                Layout.topMargin: notice.expanded ? (Kirigami.Units.gridUnit * 2 - implicitHeight) / 2 : 0
                Accessible.ignored: true
            }
            QQC2.Label {
                id: titleLabel
                text: notice.title
                textFormat: Text.PlainText
                font.weight: Font.DemiBold
                elide: notice.expanded ? Text.ElideNone : Text.ElideRight
                wrapMode: notice.expanded ? Text.Wrap : Text.NoWrap
                Layout.fillWidth: notice.expanded || notice.narrow
                Layout.preferredWidth: implicitWidth
                Layout.maximumWidth: notice.expanded || notice.narrow ? -1 : Math.ceil(implicitWidth) + 1
                Layout.minimumWidth: Math.min(implicitWidth, Kirigami.Units.gridUnit * 5)
                Accessible.ignored: true
            }
            // The body on the same line, dimmed; fills what the title and
            // the buttons leave.
            QQC2.Label {
                id: inlineBody
                visible: !notice.narrow && !notice.expanded
                text: notice.body
                textFormat: Text.PlainText
                color: notice.dim
                elide: Text.ElideRight
                maximumLineCount: 1
                Layout.fillWidth: true
                Layout.preferredWidth: 0
                Layout.minimumWidth: 0
                Accessible.ignored: true
            }
            Item {
                visible: !inlineBody.visible && !titleLabel.Layout.fillWidth
                Layout.fillWidth: true
            }
            QQC2.ToolButton {
                id: chevron
                objectName: "noticeExpand"
                visible: notice.expanded || notice.bodyHidden
                display: QQC2.AbstractButton.IconOnly
                icon.source: root.ico(notice.expanded ? "arrow-up" : "arrow-down", enabled)
                text: notice.expanded ? "Hide Details" : "Show Details"
                Accessible.name: text
                QQC2.ToolTip.text: text
                QQC2.ToolTip.visible: hovered
                QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay
                onClicked: notice.expanded = !notice.expanded
                Layout.alignment: Qt.AlignVCenter
            }
            QQC2.Button {
                visible: notice.primaryAction !== null
                action: notice.primaryAction
                Layout.alignment: Qt.AlignVCenter
            }
            Repeater {
                model: notice.narrow ? [] : notice.extraActions
                delegate: QQC2.ToolButton {
                    required property var modelData
                    action: modelData
                    Layout.alignment: Qt.AlignVCenter
                }
            }
            // Narrow: the other actions fold into a menu.
            QQC2.ToolButton {
                id: moreButton
                visible: notice.narrow && notice.extraActions.length > 0
                display: QQC2.AbstractButton.IconOnly
                icon.source: root.ico("overflow-menu", enabled)
                text: "More Actions"
                Accessible.name: text
                Accessible.role: Accessible.ButtonMenu
                QQC2.ToolTip.text: text
                QQC2.ToolTip.visible: hovered
                QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay
                onClicked: moreMenu.popup(moreButton, 0, moreButton.height)
                Layout.alignment: Qt.AlignVCenter
                QQC2.Menu {
                    id: moreMenu
                    Repeater {
                        model: notice.narrow ? notice.extraActions : []
                        delegate: QQC2.MenuItem {
                            required property var modelData
                            action: modelData
                        }
                    }
                }
            }
            QQC2.ToolButton {
                visible: notice.dismissAction !== null && notice.dismissAction.visible
                display: QQC2.AbstractButton.IconOnly
                icon.source: root.ico("window-close", enabled)
                text: notice.dismissAction ? notice.dismissAction.text : ""
                enabled: notice.dismissAction ? notice.dismissAction.enabled : false
                Accessible.name: text
                QQC2.ToolTip.text: text
                QQC2.ToolTip.visible: hovered
                QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay
                onClicked: notice.dismissAction.trigger()
                Layout.alignment: Qt.AlignVCenter
            }
        }

        // The whole body, unfolded by the chevron.
        QQC2.Label {
            visible: notice.expanded && notice.body !== ""
            text: notice.body
            textFormat: Text.PlainText
            wrapMode: Text.Wrap
            Layout.fillWidth: true
            Layout.leftMargin: Kirigami.Units.iconSizes.small + Kirigami.Units.largeSpacing
            Layout.rightMargin: Kirigami.Units.largeSpacing
            Layout.bottomMargin: Kirigami.Units.smallSpacing
            Accessible.ignored: true
        }
    }
}
