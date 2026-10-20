# Changelog

All notable changes to Fedora DNF GUI Tool are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2026-10-20

### Added

- **Update without Major** — New Updates-page button that upgrades everything except core packages (kernel, linux/GPU firmware, NVIDIA and Mesa graphics drivers, akmods, GRUB/shim). Which packages count as major is configurable under Settings → Update without Major. The confirmation dialog lists the major updates it will skip, and the download preview excludes them. Runs as a plain `dnf upgrade --exclude=…`, so passwordless "Updates only" mode covers it.
- **Simpler Updates page.** The four upgrade buttons are now one main button with a dropdown. The dropdown explains each mode and shows what it would install. Star a mode to make it the main button (remembered across restarts). `Ctrl+U` runs it from any page.
- **Update list filter** and a summary line ("N system updates · M major"). Packages that Update without Major will skip are tagged **Major**, with a tooltip explaining why.
- `Ctrl+T` opens the terminal, and `Ctrl+F` focuses the Updates filter. The Updates page already listed both shortcuts, but neither existed.
- **Search and install RPMs.** The Installed page is now **Packages**, with a Search Repositories tab covering every enabled repository. Results show the version, the source repository (e.g. RPM Fusion) and whether a package is already installed.
- **Installed → new version** on every update row, and **security tags with severity** (e.g. "Security · Critical"). A "Show" selector narrows the list to security updates or major updates.
- **Clean Up preview.** Before running `dnf autoremove`, the app lists exactly what would be removed, or says there's nothing to clean up.
- **Completion notifications.** A desktop notification reports success or failure when an operation finishes while the window isn't focused.
- **Copy Output** button on the terminal page.
- **Fedora release upgrades.** A banner appears when a newer Fedora release is out. Availability comes from Fedora's Bodhi release list, so betas are never offered, and upgrades go at most two releases ahead. The app runs Fedora's documented flow: update, `dnf system-upgrade download`, then restart and install when you choose. A failed download offers a retry with `--allowerasing`; a finished download can be installed or cancelled later. "Not now" hides the offer until the next release.
- **Mark Major / Unmark Major on every update row.** Makes Update without Major skip (or include) that package. Rows that are major because of a pattern such as `kernel*` say which pattern.
- Settings warns when the passwordless "Updates Only" rule no longer covers your list of major packages.
- **Cancel Discover's scheduled restart update.** If Discover has scheduled updates for your next restart, the Settings card says so and offers **Cancel Restart Update** (`pkcon offline-cancel`). "Use This App Instead" offers to cancel it in the same step, and "Turn Off for All Users" cancels it before masking the service. Detection reads the `/system-update` trigger rather than waking PackageKit.
- **New documentation:** the README positions the app as a Discover alternative, with an honest side-by-side comparison. New guides: [Switching from Discover](docs/switching-from-discover.md) and an [FAQ](docs/faq.md).

### Security

- **Passwordless "Updates only" no longer grants root.** The sudoers rule used `dnf upgrade *`, and sudoers `*` matches across arguments, so any program running as you could run `sudo -n dnf upgrade ./evil.rpm --nogpgcheck` (or load a dnf plugin) as root. The rule now lists only the exact command lines the app runs, with globs escaped. Settings flags the old rule and asks you to click Enable Passwordless again to replace it.
- **App self-update is verified.** The downloaded RPM is checked against the SHA-256 digest GitHub publishes for the release asset, redirects must stay on GitHub hosts, the file is written to a private `mkdtemp` directory, and dnf is invoked by its full path.

### Fixed

- **Security advisory counts were always 0 on dnf5.** dnf5 treated `updateinfo list updates` as an advisory name. The query now uses `--updates --security`, counts unique advisories rather than per-package rows, and reads the dnf5 summary format. The optional metadata refresh now runs before the query instead of after it.
- **Crash when closing during background work.** Closing the window while a scan or command was running aborted with "QThread: Destroyed while thread is still running". The window now waits briefly for workers, warns if a package operation is still running, and exits cleanly.
- **Concurrent commands.** Starting a second operation while one is running is now refused, instead of losing track of the first one (which made Cancel do nothing).
- **History page broke other loads.** Opening History disconnected whichever worker was current, which could leave the Updates scan spinning forever or stop an app-update download.
- **Failed command starts** (e.g. missing binary) now finish through the normal path, so Update Everything chains stop and pending passwordless state resets.
- **Cancel on root operations** now says it can't stop a process running as root, instead of silently doing nothing.
- **Commands waiting for input hang forever.** stdin is now `/dev/null`, so a prompt fails fast.
- **UI freeze** during the hourly reminder check. It now runs on a background thread.
- **Firmware check** always reported failure (`$?` was read after `[` had replaced it).
- **Reboot detection fallback** now spots a newer installed kernel, not only a removed running one.
- **Login reminder for pip installs.** The autostart entry falls back to `python -m dnf_gui --check` when no `dnf-gui` launcher is on PATH.
- `dnf-gui --check --security-only` no longer permanently saves the security-only preference.
- `install.sh` replaces the installed package instead of copying over it (stale files and `__pycache__` lingered).
- Updates action bar wraps onto a second row in narrow windows instead of clipping button labels.
- Settings hint text read "makes  passwordless" (missing words).
- **Per-package Update and Details buttons on the Updates page did nothing.** They emitted signals the page never connected. Double-clicking a row now opens Details too, as 1.1.0 promised.
- **Sidebar kept the previous page highlighted.** The label of the last active page stayed accent-colored after switching pages.
- **Section headers sat about 4px right of the text below them.** Qt adds an automatic indent to any label styled with padding; it's now disabled globally, which also evens out the padding on badges.
- Separators drew as a heavy two-tone line instead of a 1px rule.
- **Translucent colors had the wrong hue.** Qt reads 8-digit hex as `#AARRGGBB`, but the theme wrote `#RRGGBBAA`. Danger buttons got purple borders and History transaction badges a green tint. All translucent colors now use `rgba()`, and a test guards against it.
- **Updating a single package used `dnf install`,** which can report "already installed" instead of upgrading. It now runs `dnf upgrade <package>`.
- The Settings field for major-package patterns had no input styling. All text fields now share one style.
- **"Turn Off for All Users" (Discover) wasn't reliably reversible.** It deleted `/etc/xdg/autostart/org.kde.discover.notifier.desktop`, a file owned by `plasma-discover-notifier`. "Turn Back On" never restored it, and a package update could recreate it, silently undoing the takeover. It now masks the notifier's systemd user unit for all users and sets a system-wide notification default, and both survive package updates. Turn Back On undoes everything and restores the file if an older version removed it.
- The Settings hint that Discover "may install updates when you restart" was based on whether PackageKit's offline-update service was *running*, which is only true during the restart itself, so it never showed. It now checks whether an update is actually scheduled.
- The Discover status banner kept the previous state's title color (e.g. a cyan title on the amber warning). "Advanced Options" was also shorter than the buttons beside it.
- **Dark bars around dropdown lists** (and potentially the update menu's corners). The theme's transparent widget background painted black in popup windows; popups are now translucent so their rounded panels float cleanly. Dropdown items also get proper padding and hover highlighting.
- **Rows cut off by a hard edge when scrolling.** Lists now fade out at the top (once scrolled) and bottom (while there's more below), and the scrollbar no longer touches the rows.
- **Possible crash after cancelling a root operation and closing the window.** The cancel escalation ran on a background thread that could emit on a destroyed worker; it now uses timers the worker owns.
- Possible abort about 3 seconds after launch: the app-update check deleted its worker thread while the thread was still finishing.

### Changed

- Removed unused workers (`UpdateCheckWorker`, `SecurityCheckWorker`, `GroupListWorker`) and dead handlers.
- Test suite is hermetic (no network/dnf calls from `MainWindow` tests; a temporary config directory instead of your real settings) and no longer aborts or segfaults at teardown.
- **Accessibility:** every theme color pair now meets WCAG AA (4.5:1) in both modes. Bright green and amber fills use dark text in dark mode, and light-mode amber and dark-mode red were adjusted. `scripts/check_contrast.py` now checks the pairs the stylesheet actually uses.
- Quick Tools icons follow the active theme instead of fixed dark-mode colors.
- Refresh buttons use the same neutral style on every page; Flatpak Repair is no longer styled as destructive.
- Package rows show the real package name (`kernel-core`, not "Kernel Core"), drop the badge that was repeated on every row, and use less padding. The per-row Update button is a neutral button, so the page's main button stands out.
- "Last Checked" shows "Today" for a check made today.
- The History transaction viewer uses the same console styling as the Terminal page.
- The desktop entry is defined once (`assets/dnf-gui.desktop`) and shared by the RPM and `install.sh`. AppStream metadata now validates, with screenshots and a content rating.
- `pip install` now also provides a `dnf-gui` command.
- `LICENSE` now contains the full GPL-3.0 text (it previously held only the preamble).
- README rewritten to match current behavior, with screenshots, a development section and an accurate security model.
- Removed dead code: unused DNF search, group and COPR-removal helpers; Flatpak runtime listing; unused helpers, theme aliases, palette keys and stylesheet rules.

## [1.1.1] - 2026-09-14

### Fixed

- **Live Terminal & Worker Execution** — Resolved crash caused by missing `input_submitted` signal on `TerminalPage`, unblocking background command execution for passwordless privilege enablement, package installs, and updates.
- **Immediate Operation Cancellation** — Wired terminal cancel button to kill process groups via `SIGTERM` with escalation to `SIGKILL`, updating status immediately to "Operation Cancelled".
- **Automatic Login Reminder Autostart** — Master "Remind Me About Pending Updates" switch now directly manages the login autostart entry (`~/.config/autostart/dnf-gui-update-checker.desktop`), removing the redundant duplicate sub-checkbox.
- **Independent Flatpak Reminders** — Flatpak update alerts notify independently even when "Security Updates Only" is selected for system packages.
- **Passwordless Scope Integrity** — Passwordless settings scope is only committed upon successful sudoers validation and rule installation, avoiding desynchronized settings on aborted operations.

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

[1.1.1]: https://github.com/grpace/Fedora-DNF-GUI-Tool/releases/tag/v1.1.1
[1.1.0]: https://github.com/grpace/Fedora-DNF-GUI-Tool/releases/tag/v1.1.0
[1.0.1]: https://github.com/grpace/Fedora-DNF-GUI-Tool/releases/tag/v1.0.1
[1.0.0]: https://github.com/grpace/Fedora-DNF-GUI-Tool/releases/tag/v1.0.0
