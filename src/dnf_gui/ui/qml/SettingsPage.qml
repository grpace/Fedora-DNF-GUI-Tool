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

    function saveReminders() {
        s.saveReminders(remindSwitch.checked, securitySwitch.checked, flatpakSwitch.checked,
                        s.intervals[intervalBox.currentIndex].hours);
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
            label: "Major packages"
            text: page.s.heldBack
            placeholderText: "kernel*, *nvidia*, mesa-*"
            onAccepted: page.s.saveHeldBack(text)
        }
        FormCard.FormSectionText {
            text: "Update Without Major skips packages matching these comma-separated patterns "
                  + "(* matches anything). " + page.s.heldBackMessage
        }
        FormCard.FormButtonDelegate {
            text: "Save Major Packages"
            icon.name: "document-save"
            enabled: heldBackField.text !== page.s.heldBack
            onClicked: page.s.saveHeldBack(heldBackField.text)
        }
        FormCard.FormDelegateSeparator {}
        FormCard.FormButtonDelegate {
            text: "Reset to Defaults"
            icon.name: "edit-reset"
            onClicked: page.s.resetHeldBack()
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
            onToggled: page.saveReminders()
        }
        FormCard.FormDelegateSeparator { above: remindSwitch; below: securitySwitch }
        FormCard.FormSwitchDelegate {
            id: securitySwitch
            text: "Only for security updates"
            description: "Stay quiet about routine updates."
            enabled: remindSwitch.checked
            checked: page.s.securityOnly
            onToggled: page.saveReminders()
        }
        FormCard.FormDelegateSeparator { above: securitySwitch; below: flatpakSwitch }
        FormCard.FormSwitchDelegate {
            id: flatpakSwitch
            text: "Include Flatpak updates"
            enabled: remindSwitch.checked
            checked: page.s.notifyFlatpak
            onToggled: page.saveReminders()
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
            onActivated: page.saveReminders()
        }
        FormCard.FormDelegateSeparator {}
        FormCard.FormTextDelegate {
            text: "Last background check"
            description: page.s.lastCheck !== "" ? page.s.lastCheck : "Hasn't run yet."
        }
        FormCard.FormDelegateSeparator {}
        FormCard.FormButtonDelegate {
            text: "Send a Test Reminder"
            icon.name: "notifications"
            onClicked: page.s.testReminder()
        }
    }

    // ── Passwordless updates ──
    FormCard.FormHeader { title: "Passwordless Updates" }
    FormCard.FormCard {
        FormCard.AbstractFormDelegate {
            background: null
            contentItem: RowLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Icon {
                    source: page.s.passwordlessLevel === "positive" ? "security-high"
                          : page.s.passwordlessLevel === "warning" ? "security-medium"
                          : "security-low"
                    implicitWidth: Kirigami.Units.iconSizes.medium
                    implicitHeight: implicitWidth
                }
                ColumnLayout {
                    spacing: 0
                    Layout.fillWidth: true
                    QQC2.Label {
                        text: page.s.passwordlessTitle
                        font.weight: Font.DemiBold
                        color: page.s.passwordlessLevel === "warning" ? Kirigami.Theme.neutralTextColor
                             : page.s.passwordlessLevel === "positive" ? Kirigami.Theme.positiveTextColor
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
                            color: Kirigami.Theme.neutralTextColor
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
                         ? "Every dnf command, including installs and removals. Any program running as you could change system packages."
                         : "Only Upgrade All, Security Only and Update Without Major. Installs, removals and repo changes still ask."
            model: [{ key: "updates", label: "Updates Only (Recommended)" },
                    { key: "full", label: "All DNF Operations" }]
            textRole: "label"
            valueRole: "key"
            currentIndex: page.s.passwordlessScope === "full" ? 1 : 0
        }
        FormCard.FormDelegateSeparator {}
        FormCard.FormButtonDelegate {
            text: page.s.passwordlessLive === "off" ? "Turn On…" : "Turn On Again…"
            description: "Installs a checked per-user sudoers rule. You authenticate once."
            icon.name: "security-high"
            enabled: !App.Runner.busy
            onClicked: page.s.enablePasswordless(scopeBox.currentValue)
        }
        FormCard.FormDelegateSeparator { visible: page.s.passwordlessLive !== "off" || page.s.passwordlessScope !== "off" }
        FormCard.FormButtonDelegate {
            visible: page.s.passwordlessLive !== "off" || page.s.passwordlessScope !== "off"
            text: "Restore Password Prompts…"
            icon.name: "object-locked"
            enabled: !App.Runner.busy
            onClicked: page.s.disablePasswordless()
        }
    }

    // ── Discover ──
    FormCard.FormHeader { title: "KDE Discover" }
    FormCard.FormCard {
        FormCard.AbstractFormDelegate {
            background: null
            contentItem: RowLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Icon {
                    source: page.s.discoverLevel === "positive" ? "emblem-success"
                          : page.s.discoverLevel === "warning" ? "emblem-warning" : "plasmadiscover"
                    fallback: "dialog-information"
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
            icon.name: "system-software-update"
            onClicked: page.s.takeOver()
        }
        FormCard.FormButtonDelegate {
            visible: page.s.discoverInstalled && page.s.discoverActive
            text: "Let Discover Check Again"
            icon.name: "edit-undo"
            onClicked: page.s.restoreDiscover()
        }
        FormCard.FormDelegateSeparator { visible: page.s.discoverScheduled }
        FormCard.FormButtonDelegate {
            visible: page.s.discoverScheduled
            text: "Cancel Discover's Restart Update…"
            icon.name: "dialog-cancel"
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
            icon.name: "system-lock-screen"
            enabled: !App.Runner.busy
            onClicked: page.s.disableDiscoverSystem()
        }
        FormCard.FormButtonDelegate {
            visible: page.showAdvancedDiscover && page.s.discoverInstalled
            text: "Turn Back On for All Users…"
            icon.name: "edit-undo"
            enabled: !App.Runner.busy
            onClicked: page.s.enableDiscoverSystem()
        }
        FormCard.FormButtonDelegate {
            visible: page.showAdvancedDiscover && page.s.discoverInstalled
            text: "Stop the Checker Now"
            icon.name: "process-stop"
            onClicked: page.s.stopDiscoverChecker()
        }
        FormCard.FormButtonDelegate {
            visible: page.showAdvancedDiscover && page.s.discoverInstalled
            text: "Uninstall the Update Checker…"
            icon.name: "edit-delete"
            enabled: !App.Runner.busy
            onClicked: page.s.removeDiscoverNotifier()
        }
        FormCard.FormButtonDelegate {
            text: "Refresh Status"
            icon.name: "view-refresh"
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
                source: "dnf-gui"
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
            icon.name: "download"
            enabled: !App.Runner.busy
            onClicked: App.installAppUpdate()
        }
        FormCard.FormDelegateSeparator {}
        FormCard.FormButtonDelegate {
            text: "Check for App Updates"
            icon.name: "view-refresh"
            onClicked: App.checkAppUpdate()
        }
        FormCard.FormDelegateSeparator {}
        FormCard.FormButtonDelegate {
            text: "Release Notes"
            icon.name: "internet-services"
            onClicked: App.openReleases()
        }
        FormCard.FormDelegateSeparator {}
        FormCard.FormButtonDelegate {
            text: "Report a Problem"
            icon.name: "tools-report-bug"
            onClicked: Qt.openUrlExternally("https://github.com/grpace/Fedora-DNF-GUI-Tool/issues")
        }
    }
}
