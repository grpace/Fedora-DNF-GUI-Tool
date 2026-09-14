# Changelog

All notable changes to Fedora DNF GUI Tool are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-09-14

### Added

- **Combined updates** — Updates page shows DNF + Flatpak + security counts together, with Update Everything (chained DNF + Flatpak session) and Security Only (`dnf upgrade --security`)
- **Upgrade previews** — Package count and total download size (via `repoquery`) in every upgrade confirmation
- **Reboot banner** — Amber banner with one-click reboot when a kernel/core-library update needs it (`needs-restarting` → sentinel file → kernel drift fallbacks)
- **Package details** — Details button and double-click on every package card, powered by the previously unused `PackageInfoWorker`
- **Settings page** — Discover takeover (per-user notifier override + optional system-wide PackageKit hardening), background update reminders with login check (`dnf-gui --check`), opt-in passwordless `dnf upgrade` via validated per-user sudoers rule
- **Light mode support** — Full light and dark theme switching with preference persistence in settings
- **Adaptive vector icons** — Dynamic programmatic stroke icons adapting to active theme colors with high-contrast fill toggles
- **Ctrl+F** — Focuses search on Installed, Flatpak, and Repositories pages (as the README always claimed)

### Fixed

- **UI polish across all pages** — Aligned repository badges, balanced repo card dimensions, scrollable history details, equalized Quick Tools button widths, and centered theme toggle
- **README accuracy** — Quick Tools list trimmed to what the page actually offers; architecture tree, shortcuts, and requirements updated
- Notifier-running check no longer false-positives on the app's own process arguments
- **Consistent buttons** — One theme-owned variant per intent (primary/success/accent/warning/danger/ghost + compact); all inline button styles removed, header buttons aligned by layout instead of margin hacks
- **Visible checkboxes** — Theme now styles `QCheckBox::indicator`, so Settings toggles actually show their state
- **Updates page remembers its scan** — Revisiting the page redisplays the last results instantly; rescans happen only via Check for Updates, fresh app start, or after a completed operation
- **Calmer layout** — Page content sits closer to the sidebar; header spacing restored to original after feedback
- **Settings Discover rewrite** — Plain-language section with one recommended action ("Use This App Instead"); system-wide and uninstall options moved behind a collapsed Advanced Options toggle; em dashes and jargon removed from all user-facing copy
- **First-run hint** — The Updates empty state points new users at Settings to make this app their default updater
- **Breathing room** — Card padding up (20 to 24/28px), list gaps 6/8 to 12px, section spacing 16 to 20px, wider action-bar gaps; headings keep their sidebar anchor
- **Compact header buttons** — Refresh/Clear next to page titles use the compact size so they align with the title text instead of crowding the top edge
- **Headings anchored to the sidebar** — Shared PageHeader component: titles sit at 8px by the sidebar while body content stays at 16px, on all 9 pages; title/subtitle pairing rebalanced (28px title, tighter gaps)
- **Settings Discover card redesign** — Status banner (green/amber/grey) with one contextual action instead of a button scatter; system-wide options grouped under captioned Advanced Options
- **Title case everywhere** — Buttons, section headers, and option labels use consistent Title Case; dialog titles cleaned up

### Removed

- Dead installer handlers (codecs, dev tools, VS Code, popular apps) that had no UI cards — the tool stays scoped to system updates, not package installation

## [1.0.1] - 2026-03-12

### Fixed

- Prevent crash on Transaction History page when clicking Refresh multiple times in quick succession by disallowing concurrent history loads

## [1.0.0] - 2026-03-12

### Added

- **DNF Package Management** — Install, remove, update packages; browse installed with search/filter
- **Flatpak Manager** — Browse installed apps, search Flathub, install/remove/update
- **System Info** — System overview dashboard with resource gauges and package stats
- **Quick Tools** — RPM Fusion, Flathub setup, firmware updates, system maintenance
- **Repository Manager** — Enable/disable repos, add COPR repositories
- **Transaction History** — View past transactions with full package lists and undo
- **Live Terminal** — Streaming output with auto-scroll and status indicators
- **Dark Theme** — Modern KDE-matching dark interface with Fedora blue accents
- **Desktop Integration** — Application launcher, icon, polkit integration
- **Packaging** — RPM spec file, build script, and install script
- **Auto-Update** — Update checker with direct RPM install via DNF

[1.1.0]: https://github.com/grpace/Fedora-DNF-GUI-Tool/releases/tag/v1.1.0
[1.0.1]: https://github.com/grpace/Fedora-DNF-GUI-Tool/releases/tag/v1.0.1
[1.0.0]: https://github.com/grpace/Fedora-DNF-GUI-Tool/releases/tag/v1.0.0
