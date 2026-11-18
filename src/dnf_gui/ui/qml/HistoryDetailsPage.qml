// What one transaction changed (`dnf history info`), with Undo.
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page

    property string transactionId
    property string command
    readonly property var h: App.History

    title: "Transaction #" + transactionId

    actions: [
        Kirigami.Action {
            text: "Undo…"
            icon.source: root.ico("edit-undo", enabled)
            enabled: !App.Runner.busy
            onTriggered: page.h.undo(page.transactionId)
        },
        Kirigami.Action {
            text: "Copy Details"
            icon.source: root.ico("edit-copy", enabled)
            enabled: page.h.detailText !== ""
            displayHint: Kirigami.DisplayHint.AlwaysHide
            onTriggered: App.copyText(page.h.detailText)
        }
    ]

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing
        Kirigami.Heading {
            level: 2
            text: page.command
            wrapMode: Text.Wrap
            Layout.fillWidth: true
        }
        QQC2.BusyIndicator {
            visible: page.h.detailLoading
            running: visible
            Layout.alignment: Qt.AlignHCenter
        }
        QQC2.TextArea {
            visible: !page.h.detailLoading
            readOnly: true
            text: page.h.detailText
            textFormat: TextEdit.PlainText
            font.family: "monospace"
            font.pointSize: Kirigami.Theme.smallFont.pointSize
            wrapMode: TextEdit.Wrap
            selectByMouse: true
            background: null
            Layout.fillWidth: true
            Accessible.name: "Transaction details"
        }
    }
}
