// Shows App.Prompts.current, one at a time. Destructive prompts focus the
// safe button, so Enter never confirms them by accident.
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.kirigami.dialogs as KDialogs

KDialogs.Dialog {
    id: dialog

    readonly property var prompt: App.Prompts.current
    readonly property bool hasPrompt: prompt.token !== undefined

    title: hasPrompt ? prompt.title : ""
    padding: inset
    preferredWidth: Kirigami.Units.gridUnit * 26
    showCloseButton: false
    closePolicy: QQC2.Popup.CloseOnEscape
    standardButtons: QQC2.Dialog.NoButton

    // The title, the body and the buttons share one left and right inset.
    readonly property real inset: Kirigami.Units.largeSpacing * 2
    header: KDialogs.DialogHeader {
        dialog: dialog
        leftPadding: dialog.inset
        rightPadding: dialog.inset
        topPadding: Kirigami.Units.largeSpacing * 1.5
        contentItem: KDialogs.DialogHeaderTopContent {
            dialog: dialog
        }
    }

    function answer(choice) {
        const token = prompt.token;
        close();
        App.Prompts.reply(token, choice);
    }

    function safeChoice() {
        if (!hasPrompt)
            return "";
        for (const b of prompt.buttons)
            if (b.id === "no")
                return "no";
        return prompt.defaultChoice;
    }

    onRejected: if (hasPrompt) answer(safeChoice())

    Connections {
        target: App.Prompts
        function onCurrentChanged() {
            if (dialog.hasPrompt) {
                dialog.open();
                defaultFocus.start();
                // Read the question out: focus lands on a button.
                body.Accessible.announce(dialog.prompt.title + ". " + dialog.prompt.text);
            } else if (dialog.opened) {
                dialog.close();
            }
        }
    }
    // Focus the default button once the buttons exist.
    Timer {
        id: defaultFocus
        interval: 0
        onTriggered: {
            for (let i = 0; i < buttons.count; ++i) {
                const b = buttons.itemAt(i);
                if (b && b.choice === dialog.prompt.defaultChoice)
                    b.forceActiveFocus();
            }
        }
    }

    ColumnLayout {
        id: body
        spacing: Kirigami.Units.largeSpacing

        RowLayout {
            spacing: Kirigami.Units.largeSpacing * 1.5
            Layout.fillWidth: true
            Kirigami.Icon {
                source: root.ico(dialog.prompt.level === "error" ? "dialog-error"
                               : dialog.prompt.level === "warning" ? "dialog-warning"
                               : "dialog-information", enabled, color)
                color: dialog.prompt.level === "error" ? Kirigami.Theme.negativeTextColor
                     : dialog.prompt.level === "warning" ? Kirigami.Theme.neutralTextColor
                     : Kirigami.Theme.highlightColor
                implicitWidth: Kirigami.Units.iconSizes.large
                implicitHeight: implicitWidth
                Layout.alignment: Qt.AlignTop
            }
            QQC2.Label {
                text: dialog.hasPrompt ? dialog.prompt.text : ""
                textFormat: Text.PlainText
                wrapMode: Text.Wrap
                Layout.fillWidth: true
                Layout.preferredWidth: Kirigami.Units.gridUnit * 20
            }
        }

        // Long package lists (autoremove, forced removals) scroll.
        QQC2.ScrollView {
            visible: dialog.hasPrompt && dialog.prompt.details.length > 0
            Layout.fillWidth: true
            Layout.preferredHeight: Math.min(Kirigami.Units.gridUnit * 10,
                                             detailsList.contentHeight + Kirigami.Units.largeSpacing)
            Kirigami.Theme.colorSet: Kirigami.Theme.View
            background: Rectangle { color: Kirigami.Theme.backgroundColor; radius: Kirigami.Units.cornerRadius }
            QQC2.TextArea {
                id: detailsList
                readOnly: true
                text: dialog.hasPrompt ? dialog.prompt.details.join("\n") : ""
                textFormat: TextEdit.PlainText
                wrapMode: TextEdit.Wrap
                font.family: "monospace"
                activeFocusOnTab: true
                background: null
                Accessible.name: "Packages"
            }
        }
    }

    footer: QQC2.DialogButtonBox {
        alignment: Qt.AlignRight
        leftPadding: dialog.inset
        rightPadding: dialog.inset
        topPadding: Kirigami.Units.largeSpacing
        bottomPadding: dialog.inset
        Repeater {
            id: buttons
            model: dialog.hasPrompt ? dialog.prompt.buttons : []
            delegate: QQC2.Button {
                required property var modelData
                required property int index
                readonly property string choice: modelData.id
                text: modelData.label
                // The confirming button of a destructive prompt looks it.
                icon.source: root.ico(dialog.prompt.destructive && index === 0 ? "dialog-warning" : "", enabled)
                highlighted: choice === dialog.prompt.defaultChoice
                QQC2.DialogButtonBox.buttonRole: QQC2.DialogButtonBox.ActionRole
                onClicked: dialog.answer(choice)
                Keys.onReturnPressed: clicked()
                Keys.onEnterPressed: clicked()
            }
        }
    }
}
