// One choice in a page's filter row (All / Security / Core, Installed /
// Find): a checkable tool button whose checked state always follows
// `active`, so a click can't leave it out of step with the page.
import QtQuick
import QtQuick.Controls as QQC2

QQC2.ToolButton {
    property bool active: false

    checkable: true
    checked: active
    // A click toggles `checked` and would break the binding: hand it back.
    onClicked: checked = Qt.binding(() => active)
    Accessible.role: Accessible.RadioButton
}
