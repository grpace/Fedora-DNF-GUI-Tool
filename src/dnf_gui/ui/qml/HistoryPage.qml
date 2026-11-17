// History: every dnf transaction, newest first; details and Undo beside it.
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page

    readonly property var h: App.History

    title: "History"

    actions: [
        Kirigami.Action {
            text: "Refresh"
            icon.name: "view-refresh"
            enabled: !page.h.loading
            onTriggered: page.h.refresh()
        }
    ]

    function focusSearch() {
        search.forceActiveFocus();
        search.selectAll();
    }

    header: QQC2.ToolBar {
        position: QQC2.ToolBar.Header
        contentItem: Kirigami.SearchField {
            id: search
            placeholderText: "Filter by command, action or number…"
            Accessible.name: "Filter transactions"
            onTextChanged: page.h.items.query = text
            KeyNavigation.down: list
        }
    }

    ListView {
        id: list
        model: page.h.items
        currentIndex: -1
        keyNavigationEnabled: true
        activeFocusOnTab: true
        Accessible.name: "Transactions"

        delegate: QQC2.ItemDelegate {
            id: row
            required property var model
            required property int index
            required property string command
            required property string date
            required property string altered
            readonly property color dim: highlighted ? Kirigami.Theme.highlightedTextColor : Kirigami.ColorUtils.linearInterpolation(Kirigami.Theme.textColor, Kirigami.Theme.backgroundColor, 0.3)
            readonly property string actionIcon: {
                const a = model.action.toLowerCase();
                if (a.indexOf("remov") >= 0 || a.indexOf("erase") >= 0) return "edit-delete";
                if (a.indexOf("install") >= 0) return "list-add";
                if (a.indexOf("downgrade") >= 0) return "go-down";
                return "system-software-update";
            }

            width: ListView.view.width
            text: "Transaction " + model.id + ": " + command
            highlighted: ListView.isCurrentItem
            Accessible.description: model.action + ", " + altered + " packages, " + date
            onClicked: {
                ListView.view.currentIndex = index;
                page.h.loadDetail(model.id);
                root.openColumn("HistoryDetailsPage.qml", { transactionId: model.id, command: command });
            }
            Accessible.onPressAction: clicked()
            Keys.onReturnPressed: clicked()
            Keys.onEnterPressed: clicked()

            contentItem: RowLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Icon {
                    source: row.actionIcon
                    Layout.preferredWidth: Kirigami.Units.iconSizes.medium
                    Layout.preferredHeight: Layout.preferredWidth
                }
                ColumnLayout {
                    spacing: 0
                    Layout.fillWidth: true
                    QQC2.Label {
                        text: row.command
                        font.weight: Font.DemiBold
                        elide: Text.ElideRight
                        color: row.highlighted ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.textColor
                        Layout.fillWidth: true
                    }
                    QQC2.Label {
                        text: "#" + row.model.id + "  ·  " + row.date
                              + (row.model.action ? "  ·  " + row.model.action : "")
                              + (row.altered ? "  ·  " + row.altered + (row.altered === "1" ? " package" : " packages") : "")
                        elide: Text.ElideRight
                        color: row.dim
                        font: Kirigami.Theme.smallFont
                        Layout.fillWidth: true
                    }
                }
                QQC2.ToolButton {
                    icon.name: "edit-undo"
                    text: "Undo…"
                    display: row.width < Kirigami.Units.gridUnit * 28 ? QQC2.AbstractButton.IconOnly
                                                                      : QQC2.AbstractButton.TextBesideIcon
                    enabled: !App.Runner.busy
                    Accessible.name: "Undo transaction " + row.model.id
                    QQC2.ToolTip.text: "Reverse this transaction"
                    QQC2.ToolTip.visible: hovered
                    QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay
                    onClicked: page.h.undo(row.model.id)
                }
            }
        }

        Kirigami.LoadingPlaceholder {
            anchors.centerIn: parent
            visible: page.h.loading && list.count === 0
            text: "Loading History…"
        }
        Kirigami.PlaceholderMessage {
            anchors.centerIn: parent
            width: parent.width - Kirigami.Units.gridUnit * 4
            visible: list.count === 0 && !page.h.loading
            icon.name: "view-history"
            text: page.h.error !== "" ? "Couldn't Load History"
                  : page.h.items.query !== "" ? "No Matching Transactions" : "No Transactions Yet"
            explanation: page.h.error
        }
    }
}
