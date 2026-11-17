// An inline message with a bold title. Width comes from the layout, never
// from the message's own implicit size (that loop is what Kirigami warns
// about inside ListView headers).
import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.InlineMessage {
    id: banner

    property string title
    property string body
    property string iconName

    Layout.fillWidth: true
    Layout.preferredWidth: parent ? parent.width - Kirigami.Units.largeSpacing * 2 : 0
    Layout.leftMargin: Kirigami.Units.largeSpacing
    Layout.rightMargin: Kirigami.Units.largeSpacing
    showCloseButton: false
    icon.name: iconName
    // Rich text, so dnf output in the body can't be read as markup.
    function escapeText(s) {
        return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }
    text: title ? "<b>" + escapeText(title) + "</b>" + (body ? "<br>" + escapeText(body) : "")
                : escapeText(body)
}
