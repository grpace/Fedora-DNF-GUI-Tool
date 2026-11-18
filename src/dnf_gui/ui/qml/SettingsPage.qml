// Settings in KDE's FormCard style. Changes apply as you make them.
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.kirigamiaddons.formcard as FormCard

FormCard.FormCardPage {
    id: page

    readonly property var s: App.Settings
    readonly property var u: App.Updates
    property bool showAdvancedDiscover: false

    title: "Settings"

    // A state color as text: pulled toward the text color so it stays
    // readable (the Pill.qml blend, scripts/check_contrast.py PILL_MIX).
    function toneText(tone) {
        const t = Kirigami.Theme.textColor;
        return Qt.rgba(tone.r + (t.r - tone.r) * 0.4, tone.g + (t.g - tone.g) * 0.4,
                       tone.b + (t.b - tone.b) * 0.4, 1);
    }
    // The Core packages field shows its start, not wherever the cursor
    // was left at the end of the text.
    function showHeldBack() {
        if (!heldBackField.activeFocus && !heldBackField.fieldActiveFocus) {
            heldBackField.text = page.s.heldBack;
            heldBackField.cursorPosition = 0;
        }
    }
    Component.onCompleted: heldBackField.cursorPosition = 0

    // The text field and FormCard's switches drop their bindings (the
    // switch delegate writes its own `checked`), so put the saved values
    // back whenever the settings change. Each switch saves only its own
    // field, so setting it to the saved value never saves anything.
    Connections {
        target: page.s
        function onChanged() {
            page.showHeldBack();
            if (remindSwitch.checked !== page.s.remindersEnabled)
                remindSwitch.checked = page.s.remindersEnabled;
            if (securitySwitch.checked !== page.s.securityOnly)
                securitySwitch.checked = page.s.securityOnly;
            if (flatpakSwitch.checked !== page.s.notifyFlatpak)
                flatpakSwitch.checked = page.s.notifyFlatpak;
        }
    }

    // Each reminder control saves only its own value, taking the others
    // from what's saved. A switch follows the saved value through its
    // binding, so a change that already matches (loading the page, one
    // switch updating before another) saves nothing; any real change does,
    // however it was made (mouse, keyboard, or a screen reader's toggle
    // action, which flips `checked` without emitting toggled()).
    function saveReminder(field, value) {
        const next = {
            enabled: s.remindersEnabled, securityOnly: s.securityOnly,
            notifyFlatpak: s.notifyFlatpak, hours: s.intervalHours
        };
        if (next[field] === value)
            return;
        next[field] = value;
        s.saveReminders(next.enabled, next.securityOnly, next.notifyFlatpak, next.hours);
    }

    // ── Updates ──
    FormCard.FormHeader { title: "Updates" }
    FormCard.FormCard {
        FormCard.FormComboBoxDelegate {
            id: favoriteBox
            text: "Main update button"
            description: "What the Updates page's main button and Ctrl+U run."
            model: page.u.modes
            textRole: "title"
            valueRole: "key"
            currentIndex: {
                for (let i = 0; i < page.u.modes.length; ++i)
                    if (page.u.modes[i].key === page.u.favorite)
                        return i;
                return 0;
            }
            onActivated: page.u.setFavorite(currentValue)
        }
        FormCard.FormDelegateSeparator {}
        FormCard.FormTextFieldDelegate {
            id: heldBackField
            label: "Core packages"
            text: page.s.heldBack
            placeholderText: "kernel*, *nvidia*, mesa-*"
            onAccepted: page.s.saveHeldBack(text)
        }
        FormCard.FormSectionText {
            text: "Update Without Core skips packages matching these comma-separated patterns "
                  + "(* matches anything). " + page.s.heldBackMessage
        }
        FormCard.FormButtonDelegate {
            text: "Save Core Packages"
            icon.source: root.ico("document-save", enabled)
            enabled: heldBackField.text !== page.s.heldBack
            onClicked: {
                page.s.saveHeldBack(heldBackField.text);
                heldBackField.text = page.s.heldBack;
            }
        }
        FormCard.FormDelegateSeparator {}
        FormCard.FormButtonDelegate {
            text: "Reset to Defaults"
            icon.source: root.ico("edit-reset", enabled)
            onClicked: {
                page.s.resetHeldBack();
                heldBackField.text = page.s.heldBack;
            }
        }
    }

    // ── Reminders ──
    FormCard.FormHeader { title: "Reminders" }
    FormCard.FormCard {
        FormCard.FormSwitchDelegate {
            id: remindSwitch
            text: "Remind me about pending updates"
            description: "Checks in the background, even while this app is closed, and sends a notification when updates are waiting."
            checked: page.s.remindersEnabled
            onCheckedChanged: page.saveReminder("enabled", checked)
        }
        FormCard.FormDelegateSeparator { above: remindSwitch; below: securitySwitch }
        FormCard.FormSwitchDelegate {
            id: securitySwitch
            text: "Only for security updates"
            description: "Stay quiet about routine updates."
            enabled: remindSwitch.checked
            checked: page.s.securityOnly
            onCheckedChanged: page.saveReminder("securityOnly", checked)
        }
        FormCard.FormDelegateSeparator { above: securitySwitch; below: flatpakSwitch }
        FormCard.FormSwitchDelegate {
            id: flatpakSwitch
            text: "Include Flatpak updates"
            enabled: remindSwitch.checked
            checked: page.s.notifyFlatpak
            onCheckedChanged: page.saveReminder("notifyFlatpak", checked)
        }
        FormCard.FormDelegateSeparator { above: flatpakSwitch; below: intervalBox }
        FormCard.FormComboBoxDelegate {
            id: intervalBox
            text: "Check"
            enabled: remindSwitch.checked
            model: page.s.intervals
            textRole: "label"
            valueRole: "hours"
            currentIndex: {
                for (let i = 0; i < page.s.intervals.length; ++i)
                    if (page.s.intervals[i].hours === page.s.intervalHours)
                        return i;
                return 1;
            }
            onActivated: page.saveReminder("hours", currentValue)
        }
        FormCard.FormDelegateSeparator {}
        FormCard.FormTextDelegate {
            text: "Last background check"
            description: page.s.lastCheck !== "" ? page.s.lastCheck : "Hasn't run yet."
        }
        FormCard.FormDelegateSeparator {}
        FormCard.FormButtonDelegate {
            text: "Send a Test Reminder"
            icon.source: root.ico("notifications", enabled)
            onClicked: page.s.testReminder()
        }
    }

    // ── Passwordless updates ──
    FormCard.FormHeader { title: "Passwordless Updates" }
    FormCard.FormCard {
        FormCard.AbstractFormDelegate {
            background: null
            focusPolicy: Qt.NoFocus
            Accessible.name: "Passwordless updates: " + page.s.passwordlessTitle + ". " + page.s.passwordlessText
            contentItem: RowLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Icon {
                    source: root.ico(page.s.passwordlessLevel === "positive" ? "security-high"
                                   : page.s.passwordlessLevel === "warning" ? "security-medium"
                                   : "security-low", enabled, color)
                    color: page.s.passwordlessLevel === "positive" ? Kirigami.Theme.positiveTextColor
                         : page.s.passwordlessLevel === "warning" ? Kirigami.Theme.neutralTextColor
                         : Kirigami.Theme.textColor
                    implicitWidth: Kirigami.Units.iconSizes.medium
                    implicitHeight: implicitWidth
                }
                ColumnLayout {
                    spacing: 0
                    Layout.fillWidth: true
                    QQC2.Label {
                        text: page.s.passwordlessTitle
                        font.weight: Font.DemiBold
                        color: page.s.passwordlessLevel === "warning" ? page.toneText(Kirigami.Theme.neutralTextColor)
                             : page.s.passwordlessLevel === "positive" ? page.toneText(Kirigami.Theme.positiveTextColor)
                             : Kirigami.Theme.textColor
                        Layout.fillWidth: true
                    }
                    QQC2.Label {
                        text: page.s.passwordlessText
                        wrapMode: Text.Wrap
                        Layout.fillWidth: true
                    }
                    Repeater {
                        model: page.s.passwordlessNotes
                        delegate: QQC2.Label {
                            required property string modelData
                            text: "• " + modelData
                            wrapMode: Text.Wrap
                            color: page.toneText(Kirigami.Theme.neutralTextColor)
                            Layout.fillWidth: true
                        }
                    }
                }
            }
        }
        FormCard.FormDelegateSeparator {}
        FormCard.FormComboBoxDelegate {
            id: scopeBox
            text: "Allow without a password"
            description: scopeBox.currentValue === "full"
                         ? "Every dnf command, including installs and removals. Any program running as you could install any package file as root: the same as full administrator access."
                         : "Only Upgrade All, Security Only and Update Without Core (any program running as you could run those too). Installs, removals and repo changes still ask."
            model: [{ key: "updates", label: "Updates Only (Recommended)" },
                    { key: "full", label: "All DNF Operations" }]
            textRole: "label"
            valueRole: "key"
            currentIndex: page.s.passwordlessScope === "full" ? 1 : 0
        }
        FormCard.FormDelegateSeparator {}
        FormCard.FormButtonDelegate {
            text: page.s.passwordlessLive === "off" ? "Turn On…" : "Turn On Again…"
            description: "Saves a checked permission rule for your account. You authenticate once."
            icon.source: root.ico("security-high", enabled)
            enabled: !App.Runner.busy
            onClicked: page.s.enablePasswordless(scopeBox.currentValue)
        }
        FormCard.FormDelegateSeparator { visible: page.s.passwordlessLive !== "off" || page.s.passwordlessScope !== "off" }
        FormCard.FormButtonDelegate {
            visible: page.s.passwordlessLive !== "off" || page.s.passwordlessScope !== "off"
            text: "Restore Password Prompts…"
            icon.source: root.ico("object-locked", enabled)
            enabled: !App.Runner.busy
            onClicked: page.s.disablePasswordless()
        }
    }

    // ── Discover ──
    FormCard.FormHeader { title: "KDE Discover" }
    FormCard.FormCard {
        FormCard.AbstractFormDelegate {
            background: null
            focusPolicy: Qt.NoFocus
            Accessible.name: page.s.discoverTitle + ". " + page.s.discoverText
            contentItem: RowLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Icon {
                    source: root.ico(page.s.discoverLevel === "positive" ? "emblem-success"
                                   : page.s.discoverLevel === "warning" ? "emblem-warning" : "plasmadiscover", enabled, color)
                    color: page.s.discoverLevel === "positive" ? Kirigami.Theme.positiveTextColor
                         : page.s.discoverLevel === "warning" ? Kirigami.Theme.neutralTextColor
                         : Kirigami.Theme.textColor
                    implicitWidth: Kirigami.Units.iconSizes.medium
                    implicitHeight: implicitWidth
                }
                ColumnLayout {
                    spacing: 0
                    Layout.fillWidth: true
                    QQC2.Label {
                        text: page.s.discoverLoading && page.s.discoverTitle === "" ? "Checking Discover…" : page.s.discoverTitle
                        font.weight: Font.DemiBold
                        Layout.fillWidth: true
                    }
                    QQC2.Label {
                        text: page.s.discoverText
                        wrapMode: Text.Wrap
                        Layout.fillWidth: true
                    }
                }
            }
        }
        FormCard.FormDelegateSeparator { visible: page.s.discoverInstalled }
        FormCard.FormButtonDelegate {
            visible: page.s.discoverInstalled && !page.s.discoverActive
            text: "Use This App for Updates…"
            description: "Turns off Discover's update checks and popups for you. Reversible, no password."
            icon.source: root.ico("system-software-update", enabled)
            onClicked: page.s.takeOver()
        }
        FormCard.FormButtonDelegate {
            visible: page.s.discoverInstalled && page.s.discoverActive
            text: "Let Discover Check Again"
            icon.source: root.ico("edit-undo", enabled)
            onClicked: page.s.restoreDiscover()
        }
        FormCard.FormDelegateSeparator { visible: page.s.discoverScheduled }
        FormCard.FormButtonDelegate {
            visible: page.s.discoverScheduled
            text: "Cancel Discover's Restart Update…"
            icon.source: root.ico("dialog-cancel", enabled)
            enabled: !App.Runner.busy
            onClicked: page.s.cancelRestartUpdate()
        }
        FormCard.FormDelegateSeparator { visible: page.s.discoverInstalled }
        FormCard.FormSwitchDelegate {
            id: advancedSwitch
            visible: page.s.discoverInstalled
            text: "Show advanced options"
            description: "System-wide controls for every account on this computer."
            checked: page.showAdvancedDiscover
            onToggled: page.showAdvancedDiscover = checked
        }
        FormCard.FormButtonDelegate {
            visible: page.showAdvancedDiscover && page.s.discoverInstalled
            text: "Turn Off for All Users…"
            icon.source: root.ico("system-lock-screen", enabled)
            enabled: !App.Runner.busy
            onClicked: page.s.disableDiscoverSystem()
        }
        FormCard.FormButtonDelegate {
            visible: page.showAdvancedDiscover && page.s.discoverInstalled
            text: "Turn Back On for All Users…"
            icon.source: root.ico("edit-undo", enabled)
            enabled: !App.Runner.busy
            onClicked: page.s.enableDiscoverSystem()
        }
        FormCard.FormButtonDelegate {
            visible: page.showAdvancedDiscover && page.s.discoverInstalled
            text: "Stop the Checker Now"
            icon.source: root.ico("process-stop", enabled)
            onClicked: page.s.stopDiscoverChecker()
        }
        FormCard.FormButtonDelegate {
            visible: page.showAdvancedDiscover && page.s.discoverInstalled
            text: "Uninstall the Update Checker…"
            icon.source: root.ico("edit-delete", enabled)
            enabled: !App.Runner.busy
            onClicked: page.s.removeDiscoverNotifier()
        }
        FormCard.FormButtonDelegate {
            text: "Refresh Status"
            icon.source: root.ico("view-refresh", enabled)
            onClicked: page.s.refreshDiscover()
        }
    }

    // ── About ──
    FormCard.FormHeader { title: "About" }
    FormCard.FormCard {
        FormCard.FormTextDelegate {
            text: "DNF Package Manager " + App.version
            description: App.appUpdate.available
                         ? "Version " + App.appUpdate.version + " is available."
                         : "Runs real dnf and Flatpak commands, so what you see is what your system does."
            leading: Kirigami.Icon {
                source: root.appIcon
                fallback: "system-software-update"
                implicitWidth: Kirigami.Units.iconSizes.medium
                implicitHeight: implicitWidth
            }
        }
        FormCard.FormDelegateSeparator { visible: !!App.appUpdate.canInstall }
        FormCard.FormButtonDelegate {
            visible: !!App.appUpdate.canInstall
            text: "Install Version " + (App.appUpdate.version || "") + "…"
            description: "Downloads the release and checks it against GitHub's digest before installing."
            icon.source: root.ico("download", enabled)
            enabled: !App.Runner.busy
            onClicked: App.installAppUpdate()
        }
        FormCard.FormDelegateSeparator {}
        FormCard.FormButtonDelegate {
            text: "View on GitHub"
            description: "github.com/grpace/Fedora-DNF-GUI-Tool"
            icon.source: root.ico("github", enabled)
            onClicked: App.openProject()
        }
        FormCard.FormButtonDelegate {
            text: "Check for App Updates"
            icon.source: root.ico("view-refresh", enabled)
            onClicked: App.checkAppUpdate()
        }
        FormCard.FormDelegateSeparator {}
        FormCard.FormButtonDelegate {
            text: "Release Notes"
            icon.source: root.ico("internet-services", enabled)
            onClicked: App.openReleases()
        }
        FormCard.FormDelegateSeparator {}
        FormCard.FormButtonDelegate {
            text: "Report a Problem"
            icon.source: root.ico("tools-report-bug", enabled)
            onClicked: Qt.openUrlExternally("https://github.com/grpace/Fedora-DNF-GUI-Tool/issues")
        }
    }
}
