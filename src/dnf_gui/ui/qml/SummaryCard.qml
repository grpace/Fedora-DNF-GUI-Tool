// The Updates page's status: checking, ready (with the main update button),
// up to date, or check failed. Never shows "up to date" when the check failed.
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.AbstractCard {
    id: card

    readonly property var u: App.Updates
    readonly property string phase: u.phase
    readonly property bool checking: phase === "checking" || phase === "idle"
    readonly property var fav: page.favoriteMode

    showClickFeedback: false
    Accessible.role: Accessible.Grouping
    Accessible.name: headline.text

    // Wide cards put the buttons beside the text, so the card stays short.
    readonly property bool wide: !root.compact && width > Kirigami.Units.gridUnit * 34
    readonly property color tone: phase === "uptodate" ? Kirigami.Theme.positiveTextColor
                                : phase === "failed" ? Kirigami.Theme.negativeTextColor
                                : u.securityTotal > 0 ? Kirigami.Theme.neutralTextColor
                                : Kirigami.Theme.highlightColor

    leftPadding: Kirigami.Units.largeSpacing * 2
    rightPadding: Kirigami.Units.largeSpacing * 2
    topPadding: Kirigami.Units.largeSpacing * 2
    bottomPadding: Kirigami.Units.largeSpacing * 2

    contentItem: GridLayout {
        columns: card.wide ? 3 : 2
        columnSpacing: Kirigami.Units.largeSpacing * 2
        rowSpacing: Kirigami.Units.largeSpacing * 1.5

        // Status icon in a circle tinted with its tone.
        Rectangle {
            readonly property real size: Kirigami.Units.iconSizes.large
            visible: !root.compact
            implicitWidth: size
            implicitHeight: size
            radius: size / 2
            color: Qt.rgba(card.tone.r, card.tone.g, card.tone.b, 0.12)
            Layout.row: 0
            Layout.column: 0
            Layout.rowSpan: card.wide ? 1 : 2
            Layout.alignment: card.wide ? Qt.AlignVCenter : Qt.AlignTop
            QQC2.BusyIndicator {
                anchors.fill: parent
                anchors.margins: Kirigami.Units.smallSpacing
                running: card.checking
                visible: running
            }
            Kirigami.Icon {
                anchors.centerIn: parent
                implicitWidth: Math.round(parent.size * 0.6)
                implicitHeight: implicitWidth
                visible: !card.checking
                source: root.ico(card.phase === "uptodate" ? "update-none"
                               : card.phase === "failed" ? "network-disconnect"
                               : "update-high", enabled, color)
                color: card.tone
            }
        }

        ColumnLayout {
            spacing: Kirigami.Units.smallSpacing / 2
            Layout.row: 0
            Layout.column: 1
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignVCenter

            Kirigami.Heading {
                id: headline
                level: 2
                type: Kirigami.Heading.Type.Primary
                wrapMode: Text.Wrap
                Layout.fillWidth: true
                text: card.checking ? "Checking for Updates…" : card.u.headline
            }
            QQC2.Label {
                Layout.fillWidth: true
                wrapMode: Text.Wrap
                text: card.checking
                      ? "Downloading the latest update lists. This can take a minute."
                      : card.u.summary
            }
            QQC2.Label {
                visible: !card.checking && card.u.lastChecked !== ""
                text: card.phase === "failed" ? "Couldn't reach the repositories just now."
                                              : "Last checked " + card.u.lastChecked
                font: Kirigami.Theme.smallFont
                color: Kirigami.ColorUtils.linearInterpolation(Kirigami.Theme.textColor, Kirigami.Theme.backgroundColor, 0.3)
                Layout.fillWidth: true
                wrapMode: Text.Wrap
            }
        }

        Flow {
            Layout.row: card.wide ? 0 : 1
            Layout.column: card.wide ? 2 : 1
            Layout.fillWidth: !card.wide
            Layout.alignment: card.wide ? (Qt.AlignVCenter | Qt.AlignRight) : Qt.AlignLeft
            spacing: Kirigami.Units.smallSpacing * 2
            visible: !card.checking

            // The favorite update mode is the one main button.
            PrimaryButton {
                id: mainButton
                visible: card.phase === "ready" || (card.phase === "failed" && card.u.total > 0)
                height: moreButton.implicitHeight
                enabled: !!card.fav.enabled && !App.Runner.busy
                iconName: card.fav.key === "security" ? "security-high" : "download"
                text: (card.fav.title || "") + (card.fav.count > 0 ? " (" + card.fav.count + ")" : "")
                QQC2.ToolTip.text: (card.fav.description || "") + " · " + (card.fav.detail || "")
                                   + (card.fav.key !== card.u.favorite ? " · Your chosen main option has nothing to install right now" : "")
                                   + " · Ctrl+U"
                QQC2.ToolTip.visible: hovered
                QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay
                onClicked: card.u.runFavorite()
            }
            QQC2.Button {
                id: moreButton
                visible: mainButton.visible
                text: "Other Ways to Update"
                // Breeze draws the menu arrow itself (ButtonMenu role).
                enabled: !App.Runner.busy
                onClicked: modeMenu.popup(moreButton, 0, moreButton.height)
                Accessible.role: Accessible.ButtonMenu

                QQC2.Menu {
                    id: modeMenu
                    Repeater {
                        model: card.u.modes
                        delegate: QQC2.MenuItem {
                            required property var modelData
                            text: modelData.title + "  ·  " + modelData.detail
                            enabled: modelData.enabled
                            icon.source: root.ico(modelData.favorite ? "starred-symbolic" : "", enabled)
                            onTriggered: card.u.runMode(modelData.key)
                        }
                    }
                    QQC2.MenuSeparator {}
                    QQC2.Menu {
                        title: "Main Button Runs"
                        Repeater {
                            model: card.u.modes
                            delegate: QQC2.MenuItem {
                                required property var modelData
                                text: modelData.title
                                checkable: true
                                checked: modelData.favorite
                                autoExclusive: true
                                onTriggered: card.u.setFavorite(modelData.key)
                            }
                        }
                    }
                }
            }
            QQC2.Button {
                visible: card.phase === "uptodate" || card.phase === "failed"
                highlighted: card.phase === "failed"
                text: "Check Again"
                icon.source: root.ico("view-refresh", enabled)
                onClicked: card.u.check()
            }
        }
    }
}
