// Details for one package, opened beside the Updates or Installed list.
// Shows the pending update (if any) and real `dnf info` metadata.
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page

    property string packageName
    readonly property var info: App.Packages.details
    readonly property bool loading: App.Packages.detailsLoading
    readonly property var update: {
        App.Updates.total;  // re-evaluate after every scan
        return App.Updates.updateFor(packageName);
    }
    readonly property bool hasUpdate: update.name !== undefined
    readonly property bool flatpak: update.kind === "flatpak"
    readonly property bool installed: hasUpdate || !!info.installed

    title: packageName
    Accessible.name: packageName + " details"
    leftPadding: root.gutter
    rightPadding: root.gutter
    topPadding: root.gutter

    actions: [
        Kirigami.Action {
            text: "Update"
            icon.source: root.ico("download", enabled)
            visible: page.hasUpdate && !page.flatpak
            enabled: !App.Runner.busy
            onTriggered: App.Updates.upgradePackage(page.packageName)
        },
        Kirigami.Action {
            text: "Update Flatpak Apps"
            icon.source: root.ico("download", enabled)
            visible: page.flatpak
            enabled: !App.Runner.busy
            onTriggered: App.Flatpak.updateAll()
        },
        Kirigami.Action {
            text: "Install"
            icon.source: root.ico("list-add", enabled)
            visible: !page.hasUpdate && !page.loading && !page.info.installed && !page.info.missing
            enabled: !App.Runner.busy
            onTriggered: App.Packages.install(page.packageName)
        },
        Kirigami.Action {
            text: page.update.majorActionLabel || "Treat as Core"
            icon.source: root.ico("flag", enabled)
            visible: page.hasUpdate && !page.flatpak
            enabled: !!page.update.canToggleMajor
            tooltip: page.update.majorTooltip || ""
            displayHint: Kirigami.DisplayHint.AlwaysHide
            onTriggered: App.Updates.toggleMajor(page.packageName)
        },
        Kirigami.Action {
            text: "Open Homepage"
            icon.source: root.ico("internet-services", enabled)
            visible: !!page.info.url
            displayHint: Kirigami.DisplayHint.AlwaysHide
            onTriggered: Qt.openUrlExternally(page.info.url)
        },
        Kirigami.Action {
            text: "Remove…"
            icon.source: root.ico("edit-delete", enabled)
            visible: !page.flatpak && !!page.info.installed
            enabled: !App.Runner.busy
            displayHint: Kirigami.DisplayHint.AlwaysHide
            onTriggered: App.Packages.remove(page.packageName)
        }
    ]

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing * 1.5

        RowLayout {
            spacing: Kirigami.Units.largeSpacing * 1.5
            Layout.fillWidth: true
            AppIcon {
                name: page.packageName
                appId: page.flatpak ? page.update.appId : ""
                Layout.preferredWidth: Kirigami.Units.iconSizes.large
                Layout.preferredHeight: Layout.preferredWidth
            }
            ColumnLayout {
                spacing: 0
                Layout.fillWidth: true
                Kirigami.Heading {
                    level: 2
                    type: Kirigami.Heading.Type.Primary
                    text: page.packageName
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }
                QQC2.Label {
                    text: page.flatpak ? page.update.appId : (page.info.summary || "")
                    visible: text !== ""
                    wrapMode: Text.Wrap
                    color: Kirigami.ColorUtils.linearInterpolation(Kirigami.Theme.textColor, Kirigami.Theme.backgroundColor, 0.3)
                    Layout.fillWidth: true
                }
            }
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: page.hasUpdate && !!page.update.security
            type: page.update.severity === "Critical" || page.update.severity === "Important"
                  ? Kirigami.MessageType.Error : Kirigami.MessageType.Warning
            icon.source: root.ico("security-low", enabled)
            text: "<b>" + (page.update.severity || "Security") + " security fix</b><br>"
                  + (page.update.waiting ? "Waiting on another repository. Security Only can't install it yet."
                                         : "Installed by Upgrade All and by Security Only.")
        }
        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: page.hasUpdate && !!page.update.major
            type: Kirigami.MessageType.Information
            icon.source: root.ico("flag", enabled)
            text: page.update.majorReason || ""
        }

        // ── Pending update ──
        // The two forms share one label column and sit at the header's
        // left edge, each under its own heading.
        Kirigami.Heading {
            visible: page.hasUpdate
            level: 4
            type: Kirigami.Heading.Type.Primary
            text: "Update"
            Layout.topMargin: Kirigami.Units.smallSpacing
        }
        Kirigami.FormLayout {
            id: updateForm
            visible: page.hasUpdate
            twinFormLayouts: [infoForm]
            Layout.fillWidth: false
            Layout.alignment: Qt.AlignLeft
            QQC2.Label {
                Kirigami.FormData.label: "Installed:"
                visible: !!page.update.fromVersion
                text: page.update.fromVersion || ""
            }
            QQC2.Label {
                Kirigami.FormData.label: "New version:"
                text: page.update.toVersion || ""
                font.weight: Font.DemiBold
            }
            QQC2.Label {
                Kirigami.FormData.label: "Download:"
                visible: !!page.update.size
                text: page.update.size || ""
            }
            QQC2.Label {
                Kirigami.FormData.label: "From:"
                visible: !!page.update.repo
                text: page.update.repo || ""
            }
        }

        // ── dnf info ──
        Kirigami.Heading {
            visible: !page.flatpak && !page.loading && !page.info.missing
            level: 4
            type: Kirigami.Heading.Type.Primary
            text: "Package"
            Layout.topMargin: Kirigami.Units.smallSpacing
        }
        Kirigami.FormLayout {
            id: infoForm
            visible: !page.flatpak && !page.loading && !page.info.missing
            twinFormLayouts: [updateForm]
            Layout.fillWidth: false
            Layout.alignment: Qt.AlignLeft
            QQC2.Label {
                Kirigami.FormData.label: "Version:"
                text: (page.info.version || "") + (page.info.release ? "-" + page.info.release : "")
            }
            QQC2.Label { Kirigami.FormData.label: "Architecture:"; text: page.info.arch || "" }
            QQC2.Label { Kirigami.FormData.label: "Repository:"; text: page.info.repo || "" }
            QQC2.Label {
                Kirigami.FormData.label: "Size:"
                visible: !!page.info.size
                text: page.info.size || ""
            }
            QQC2.Label {
                Kirigami.FormData.label: "Installed size:"
                visible: !!page.info.installedSize
                text: page.info.installedSize || ""
            }
            QQC2.Label {
                Kirigami.FormData.label: "License:"
                visible: !!page.info.license
                text: page.info.license || ""
                wrapMode: Text.Wrap
                Layout.maximumWidth: Kirigami.Units.gridUnit * 16
            }
            Kirigami.UrlButton {
                Kirigami.FormData.label: "Homepage:"
                visible: !!page.info.url
                url: page.info.url || ""
            }
        }

        QQC2.Label {
            visible: !page.flatpak && !!page.info.description
            text: page.info.description || ""
            wrapMode: Text.Wrap
            textFormat: Text.PlainText
            Layout.fillWidth: true
        }

        QQC2.BusyIndicator {
            visible: page.loading && !page.flatpak
            running: visible
            Layout.alignment: Qt.AlignHCenter
        }
        Kirigami.PlaceholderMessage {
            visible: !page.flatpak && !page.loading && !!page.info.missing
            Layout.fillWidth: true
            icon.source: root.ico("package-x-generic", enabled)
            text: "No Details Available"
            explanation: "dnf couldn't find information about this package."
        }
    }
}
