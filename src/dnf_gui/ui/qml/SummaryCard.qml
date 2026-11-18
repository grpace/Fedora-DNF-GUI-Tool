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

    contentItem: RowLayout {
        spacing: Kirigami.Units.largeSpacing * 2

        Item {
            implicitWidth: Kirigami.Units.iconSizes.huge
            implicitHeight: implicitWidth
            Layout.alignment: Qt.AlignTop
            visible: !root.compact
            QQC2.BusyIndicator {
                anchors.fill: parent
                running: card.checking
                visible: running
            }
            Kirigami.Icon {
                anchors.fill: parent
                visible: !card.checking
                source: card.phase === "uptodate" ? "update-none"
                      : card.phase === "failed" ? "network-disconnect"
                      : card.u.securityTotal > 0 ? "update-high"
                      : "update-medium"
            }
        }

        ColumnLayout {
            spacing: Kirigami.Units.smallSpacing
            Layout.fillWidth: true

            Kirigami.Heading {
                id: headline
                level: 2
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

            Flow {
                Layout.fillWidth: true
                Layout.topMargin: Kirigami.Units.largeSpacing
                spacing: Kirigami.Units.smallSpacing
                visible: !card.checking

                // The favorite update mode is the one main button.
                QQC2.Button {
                    id: mainButton
                    visible: card.phase === "ready" || (card.phase === "failed" && card.u.total > 0)
                    highlighted: true
                    enabled: !!card.fav.enabled && !App.Runner.busy
                    icon.name: card.fav.key === "security" ? "security-high" : "download"
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
                    icon.name: "arrow-down"
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
                                icon.name: modelData.favorite ? "starred-symbolic" : ""
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
                    icon.name: "view-refresh"
                    onClicked: card.u.check()
                }
            }
        }
    }
}
