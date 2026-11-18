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
    leftPadding: root.gutter
    rightPadding: root.gutter
    topPadding: root.gutter
    bottomPadding: root.gutter  // Main.qml adds room for the activity capsule

    actions: [
        Kirigami.Action {
            text: "Refresh"
            icon.source: root.ico("view-refresh", enabled)
            enabled: !page.s.loading
            onTriggered: page.s.refresh()
        },
        Kirigami.Action {
            text: "Copy System Details"
            icon.source: root.ico("edit-copy", enabled)
            enabled: page.s.loaded
            displayHint: Kirigami.DisplayHint.AlwaysHide
            onTriggered: App.copyText(
                "OS: " + (page.i.fedora_version || "") + "\nKernel: " + (page.i.kernel || "")
                + "\nDesktop: " + (page.i.desktop_env || "") + " (" + (page.i.display_server || "") + ")"
                + "\nCPU: " + (page.i.cpu_model || "") + "\nGPU: " + (page.i.gpu || "")
                + "\nMemory: " + (page.i.ram_total || ""))
        }
    ]

    readonly property color dim: Kirigami.ColorUtils.linearInterpolation(
        Kirigami.Theme.textColor, Kirigami.Theme.backgroundColor, root.secondaryMix)

    // A usage bar: name and amount on one line, the bar right under it,
    // and an optional caption under the bar.
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
            QQC2.Label {
                text: meter.valueText
                color: page.dim
                font.features: { "tnum": 1 }
            }
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
            color: meter.percent >= 90 ? Kirigami.Theme.negativeTextColor : page.dim
            wrapMode: Text.Wrap
            Layout.fillWidth: true
        }
    }

    // Label and value pairs: a dimmed label column and wrapping values;
    // stacked (label right above its value) only in a really narrow card.
    // Pairs whose value is empty are left out.
    component Facts: GridLayout {
        id: facts
        property var rows: []   // [[label, value], ...]
        readonly property var shown: rows.filter(r => r[1] !== undefined && r[1] !== null && String(r[1]) !== "")
        readonly property bool stacked: width < Kirigami.Units.gridUnit * 15
        columns: stacked ? 1 : 2
        columnSpacing: Kirigami.Units.largeSpacing * 1.5
        rowSpacing: stacked ? 0 : Kirigami.Units.smallSpacing * 1.5
        Layout.fillWidth: true
        Repeater {
            model: facts.shown
            delegate: QQC2.Label {
                required property var modelData
                required property int index
                text: modelData[0]
                color: page.dim
                font: facts.stacked ? Kirigami.Theme.smallFont : Kirigami.Theme.defaultFont
                elide: Text.ElideRight
                Layout.row: facts.stacked ? index * 2 : index
                Layout.column: 0
                Layout.preferredWidth: facts.stacked ? -1 : Kirigami.Units.gridUnit * 6.5
                Layout.fillWidth: facts.stacked
                Layout.alignment: Qt.AlignTop | Qt.AlignLeft
                Layout.topMargin: facts.stacked && index > 0 ? Kirigami.Units.smallSpacing * 2 : 0
            }
        }
        Repeater {
            model: facts.shown
            delegate: QQC2.Label {
                required property var modelData
                required property int index
                text: String(modelData[1])
                textFormat: Text.PlainText
                wrapMode: Text.Wrap
                Layout.row: facts.stacked ? index * 2 + 1 : index
                Layout.column: facts.stacked ? 0 : 1
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignTop | Qt.AlignLeft
            }
        }
    }

    component Card: Kirigami.Card {
        id: infoCard
        property string heading
        property string iconName
        default property alias content: body.data
        padding: Kirigami.Units.largeSpacing * 2
        Layout.fillWidth: true
        Layout.preferredWidth: Kirigami.Units.gridUnit * 20
        // Each card is as tall as its content (no stretched empty blocks).
        Layout.alignment: Qt.AlignTop
        header: RowLayout {
            spacing: Kirigami.Units.largeSpacing
            Kirigami.Icon {
                source: root.ico(infoCard.iconName, enabled)
                implicitWidth: Kirigami.Units.iconSizes.smallMedium
                implicitHeight: implicitWidth
            }
            Kirigami.Heading {
                level: 4
                type: Kirigami.Heading.Type.Primary
                text: infoCard.heading
                Layout.fillWidth: true
            }
        }
        contentItem: ColumnLayout {
            spacing: 0
            ColumnLayout {
                id: body
                spacing: Kirigami.Units.largeSpacing * 1.5
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignTop
            }
            // Any spare height goes below the content, never between.
            Item { Layout.fillHeight: true }
        }
    }

    // One centered column: the overview and the cards share its left edge.
    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing * 2

        ColumnLayout {
            spacing: Kirigami.Units.largeSpacing * 2
            Layout.fillWidth: true
            Layout.maximumWidth: Kirigami.Units.gridUnit * 42
            Layout.alignment: Qt.AlignHCenter

            // ── Overview ──
            RowLayout {
                spacing: Kirigami.Units.largeSpacing * 2
                Layout.fillWidth: true
                Kirigami.Icon {
                    source: "fedora-logo-icon"
                    fallback: root.ico("computer", enabled)
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

            GridLayout {
                columns: width >= Kirigami.Units.gridUnit * 26 ? 2 : 1
                columnSpacing: Kirigami.Units.largeSpacing * 1.5
                rowSpacing: Kirigami.Units.largeSpacing * 1.5
                uniformCellWidths: true
                Layout.fillWidth: true

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
                                + (page.i.root_fs ? "  ·  " + page.i.root_fs : "")
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
                    Facts {
                        rows: [
                            ["Device", page.i.device || ""],
                            ["Processor", (page.i.cpu_model || "—") + (page.i.cpu_cores ? " (" + page.i.cpu_cores + " threads)" : "")],
                            ["Graphics", page.i.gpu || "—"],
                            ["Architecture", page.i.architecture || "—"],
                            ["Temperature", page.i.cpu_temp || ""]
                        ]
                    }
                }

                Card {
                    heading: "Software"
                    iconName: "preferences-system-linux"
                    Facts {
                        rows: [
                            ["Desktop", page.i.desktop || ""],
                            ["Kernel", page.i.kernel || "—"],
                            ["Packages", page.i.package_count ? page.i.package_count + " RPMs, " + (page.i.flatpak_count || 0) + " Flatpak apps" : "—"],
                            ["Shell", page.i.shell || "—"],
                            ["Audio", page.i.audio_server || ""],
                            ["Last update", page.i.last_update || ""]
                        ]
                    }
                }

                Card {
                    heading: "Security and Boot"
                    iconName: "security-high"
                    Facts {
                        rows: [
                            ["SELinux", page.i.selinux_status || "—"],
                            ["Boot", page.i.boot_mode || "—"],
                            ["Firmware", page.i.firmware || ""],
                            ["Virtualization", page.i.virtualization || ""],
                            ["IP address", page.i.primary_ip || ""]
                        ]
                    }
                }
            }
        }
    }
}
