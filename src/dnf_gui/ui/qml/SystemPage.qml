// System: what this computer is and how it's doing, at a glance.
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page

    readonly property var s: App.System
    readonly property var i: s.info

    title: "System"

    actions: [
        Kirigami.Action {
            text: "Refresh"
            icon.name: "view-refresh"
            enabled: !page.s.loading
            onTriggered: page.s.refresh()
        },
        Kirigami.Action {
            text: "Copy System Details"
            icon.name: "edit-copy"
            enabled: page.s.loaded
            displayHint: Kirigami.DisplayHint.AlwaysHide
            onTriggered: App.copyText(
                "OS: " + (page.i.fedora_version || "") + "\nKernel: " + (page.i.kernel || "")
                + "\nDesktop: " + (page.i.desktop_env || "") + " (" + (page.i.display_server || "") + ")"
                + "\nCPU: " + (page.i.cpu_model || "") + "\nGPU: " + (page.i.gpu || "")
                + "\nMemory: " + (page.i.ram_total || ""))
        }
    ]

    component Meter: ColumnLayout {
        id: meter
        property string label
        property string valueText
        property string detail
        property real percent: 0
        spacing: Kirigami.Units.smallSpacing
        Layout.fillWidth: true
        RowLayout {
            Layout.fillWidth: true
            QQC2.Label { text: meter.label; font.weight: Font.DemiBold; Layout.fillWidth: true }
            QQC2.Label { text: meter.valueText; color: Kirigami.ColorUtils.linearInterpolation(Kirigami.Theme.textColor, Kirigami.Theme.backgroundColor, 0.3) }
        }
        QQC2.ProgressBar {
            from: 0; to: 100
            value: meter.percent
            Layout.fillWidth: true
            Accessible.name: meter.label + " " + Math.round(meter.percent) + " percent used"
        }
        QQC2.Label {
            visible: text !== ""
            text: meter.detail
            font: Kirigami.Theme.smallFont
            color: meter.percent >= 90 ? Kirigami.Theme.negativeTextColor : Kirigami.ColorUtils.linearInterpolation(Kirigami.Theme.textColor, Kirigami.Theme.backgroundColor, 0.3)
            wrapMode: Text.Wrap
            Layout.fillWidth: true
        }
    }

    component Card: Kirigami.Card {
        id: infoCard
        property string heading
        property string iconName
        default property alias content: body.data
        Layout.fillWidth: true
        header: RowLayout {
            spacing: Kirigami.Units.largeSpacing
            Kirigami.Icon {
                source: infoCard.iconName
                implicitWidth: Kirigami.Units.iconSizes.smallMedium
                implicitHeight: implicitWidth
            }
            Kirigami.Heading { level: 3; text: infoCard.heading; Layout.fillWidth: true }
        }
        contentItem: ColumnLayout {
            spacing: 0
            ColumnLayout { id: body; spacing: Kirigami.Units.largeSpacing; Layout.fillWidth: true }
            Item { Layout.fillHeight: true }
        }
    }

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing * 2

        // ── Overview ──
        RowLayout {
            spacing: Kirigami.Units.largeSpacing * 2
            Layout.fillWidth: true
            Kirigami.Icon {
                source: "fedora-logo-icon"
                fallback: "computer"
                Layout.preferredWidth: Kirigami.Units.iconSizes.huge
                Layout.preferredHeight: Layout.preferredWidth
            }
            ColumnLayout {
                spacing: Kirigami.Units.smallSpacing
                Layout.fillWidth: true
                Kirigami.Heading {
                    level: 1
                    text: page.i.fedora_version || "Loading…"
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }
                QQC2.Label {
                    text: [page.i.hostname, page.i.desktop_env, page.i.display_server]
                          .filter(x => !!x).join("  ·  ")
                    color: Kirigami.ColorUtils.linearInterpolation(Kirigami.Theme.textColor, Kirigami.Theme.backgroundColor, 0.3)
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }
                QQC2.Label {
                    visible: !!page.i.uptime
                    text: "Up " + page.i.uptime
                    color: Kirigami.ColorUtils.linearInterpolation(Kirigami.Theme.textColor, Kirigami.Theme.backgroundColor, 0.3)
                }
            }
        }

        Kirigami.CardsLayout {
            Layout.fillWidth: true
            maximumColumns: 2

            Card {
                heading: "Usage"
                iconName: "view-statistics"
                Meter {
                    label: "Memory"
                    percent: page.i.ram_percent || 0
                    valueText: (page.i.ram_used || "—") + " of " + (page.i.ram_total || "—")
                }
                Meter {
                    label: "Disk (/)"
                    percent: page.i.disk_percent || 0
                    valueText: (page.i.disk_used || "—") + " of " + (page.i.disk_total || "—")
                    detail: page.i.disk_free ? page.i.disk_free + " free"
                            + ((page.i.disk_percent || 0) >= 90 ? ". Updates may fail when the disk is this full." : "") : ""
                }
                Meter {
                    visible: !!page.i.swap_total
                    label: "Swap"
                    percent: page.i.swap_percent || 0
                    valueText: (page.i.swap_used || "—") + " of " + (page.i.swap_total || "—")
                }
                Meter {
                    visible: page.i.battery_percent !== "" && page.i.battery_percent !== undefined
                    label: "Battery"
                    percent: page.i.battery_percent || 0
                    valueText: (page.i.battery_percent || 0) + "%"
                    detail: [page.i.battery_status, page.i.battery_time].filter(x => !!x).join(", ")
                }
            }

            Card {
                heading: "Hardware"
                iconName: "cpu"
                Kirigami.FormLayout {
                    Layout.fillWidth: true
                    QQC2.Label {
                        Kirigami.FormData.label: "Processor:"
                        text: (page.i.cpu_model || "—") + (page.i.cpu_cores ? " (" + page.i.cpu_cores + " threads)" : "")
                        wrapMode: Text.Wrap
                        Layout.maximumWidth: Kirigami.Units.gridUnit * 16
                    }
                    QQC2.Label {
                        Kirigami.FormData.label: "Graphics:"
                        text: page.i.gpu || "—"
                        wrapMode: Text.Wrap
                        Layout.maximumWidth: Kirigami.Units.gridUnit * 16
                    }
                    QQC2.Label { Kirigami.FormData.label: "Architecture:"; text: page.i.architecture || "—" }
                    QQC2.Label { Kirigami.FormData.label: "Temperature:"; visible: !!page.i.cpu_temp; text: page.i.cpu_temp || "" }
                }
            }

            Card {
                heading: "Software"
                iconName: "preferences-system-linux"
                Kirigami.FormLayout {
                    Layout.fillWidth: true
                    QQC2.Label { Kirigami.FormData.label: "Kernel:"; text: page.i.kernel || "—" }
                    QQC2.Label {
                        Kirigami.FormData.label: "Packages:"
                        text: page.i.package_count ? page.i.package_count + " RPMs, " + (page.i.flatpak_count || 0) + " Flatpak apps" : "—"
                    }
                    QQC2.Label { Kirigami.FormData.label: "Shell:"; text: page.i.shell || "—" }
                    QQC2.Label { Kirigami.FormData.label: "Audio:"; visible: !!page.i.audio_server; text: page.i.audio_server || "" }
                }
            }

            Card {
                heading: "Security and Boot"
                iconName: "security-high"
                Kirigami.FormLayout {
                    Layout.fillWidth: true
                    QQC2.Label { Kirigami.FormData.label: "SELinux:"; text: page.i.selinux_status || "—" }
                    QQC2.Label { Kirigami.FormData.label: "Boot:"; text: page.i.boot_mode || "—" }
                    QQC2.Label { Kirigami.FormData.label: "Virtualization:"; visible: !!page.i.virtualization; text: page.i.virtualization || "" }
                    QQC2.Label { Kirigami.FormData.label: "IP address:"; visible: !!page.i.primary_ip; text: page.i.primary_ip || "" }
                }
            }
        }
    }
}
