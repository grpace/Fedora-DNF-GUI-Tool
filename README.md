<div align="center">
  <img src="assets/icons/app_icon.svg" width="96" height="96" alt="DNF Package Manager Logo">
  <h1>DNF Package Manager</h1>
  <p><b>A graphical package manager for Fedora Linux and KDE Plasma.</b></p>
  <p>Native DNF and Flatpak package management with live terminal execution, security advisories, and system telemetry.</p>

  <p>
    <a href="https://github.com/grpace/Fedora-DNF-GUI-Tool/releases/latest">
      <img src="https://img.shields.io/badge/version-1.1.1-blue.svg" alt="Latest Release">
    </a>
    <img src="https://img.shields.io/badge/platform-Fedora%20Linux%2040%2B-51A2DA?logo=fedora&logoColor=white" alt="Fedora Linux">
    <img src="https://img.shields.io/badge/python-3.12%2B-3776AB?logo=python&logoColor=white" alt="Python Version">
    <img src="https://img.shields.io/badge/license-GPL--3.0-informational.svg" alt="License GPL-3.0">
  </p>
</div>

---

## Overview

DNF Package Manager provides a desktop interface for maintaining Fedora systems without obscuring the underlying package operations. It invokes standard DNF and Flatpak executables directly, streams execution logs in real time, and offers tools for repository management, rollback history, and update scheduling.

| Capability | Highlights |
|---|---|
| **Unified Updates** | Combined DNF and Flatpak upgrades, security-specific advisories, and download size previews. |
| **Package Management** | Search, inspect, and remove RPM packages and Flatpaks from a single application. |
| **Flathub Integration** | Search and install applications from the global Flathub remote. |
| **Discover Coordination** | Suppress duplicate update notifications from KDE Discover and manage PackageKit services. |
| **Process Control** | Cancel ongoing package transactions cleanly with process group termination. |
| **Live Terminal** | Stream command output line-by-line with execution timestamps and exit status indicators. |

---

## Features

### Unified Updates and Security

- **Combined updates view.** Monitor pending DNF packages, Flatpak applications, and security advisories from one dashboard.
- **Sequential upgrades.** Run system package upgrades and Flatpak updates consecutively in a single terminal session.
- **Security-focused upgrades.** Target CVE advisories exclusively with `dnf upgrade --security`.
- **Pre-upgrade transaction summaries.** Inspect total package counts and estimated download footprints before confirming transactions.
- **Reboot notifications.** Detect when kernel, systemd, or glibc upgrades require a reboot, with an integrated restart button.
- **Package inspection.** View package version, architecture, repository, installed size, and license metadata directly from package cards.

### RPM and Flatpak Management

- **Installed package browser.** Filter, search, and inspect all installed RPM packages.
- **Orphan cleanup.** Remove packages alongside orphaned dependencies to keep system state clean.
- **Flathub catalog search.** Discover, install, update, and remove Flatpak applications.
- **Runtime maintenance.** Reclaim disk space by pruning unreferenced Flatpak runtimes.

### System Tools and Telemetry

- **Hardware and distribution metrics.** Monitor CPU, GPU, memory, and disk usage alongside Fedora and KDE Plasma versions.
- **Quick repositories.** Toggle RPM Fusion Free, RPM Fusion Non-Free, and Flathub remotes.
- **Firmware updates.** Query and deploy device firmware updates via `fwupdmgr`.
- **Transaction history and rollback.** Audit historical DNF transactions and reverse accidental package installations or upgrades.

### Settings and Automation

- **Discover coordination.** Silence KDE Discover update prompts to prevent redundant desktop notifications, with optional PackageKit service masking.
- **Background update checker.** Configure scheduled update scans and enable an automatic login reminder (`dnf-gui --check`).
- **Granular alert rules.** Configure independent Flatpak update notifications when system package reminders are set to security-only mode.
- **Optional passwordless upgrades.** Create a validated sudoers drop-in (`/etc/sudoers.d/90-dnf-gui`) allowing unattended `dnf upgrade` execution while keeping package additions and removals protected.

### Desktop Integration

- **Appearance options.** Switch between dark and light themes styled for KDE Plasma Breeze.
- **Theme-reactive icons.** Vector icons automatically adjust strokes and fills to match system color schemes.
- **Interactive terminal.** Review live command output with auto-scrolling, clear controls, and responsive process cancellation.

---

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+1` through `Ctrl+9` | Navigate between pages |
| `Ctrl+R` | Refresh current view |
| `Ctrl+F` | Focus search input on Installed, Flatpak, and Repository pages |

---

## Requirements

- Fedora Linux 40 or newer
- Python 3.12 or newer
- PyQt6 6.6.0 or newer
- DNF package manager
- polkit (for administrative privileges)
- sudo (standard on Fedora installations)
- Flatpak (optional, for Flatpak features)
- fwupd (optional, for firmware upgrades)
- libnotify / `notify-send` (optional, for desktop alerts)
- dnf-utils-core / `needs-restarting` (optional, for enhanced reboot detection)

---

## Installation

### Method 1: Install RPM via DNF (Recommended)

Install the signed release package directly through DNF:

```bash
sudo dnf install https://github.com/grpace/Fedora-DNF-GUI-Tool/releases/latest/download/DNF-Package-Manager-v1.1.1.rpm
```

Alternatively, download `DNF-Package-Manager-v1.1.1.rpm` manually from [GitHub Releases](https://github.com/grpace/Fedora-DNF-GUI-Tool/releases/latest) and run:

```bash
sudo dnf install ~/Downloads/DNF-Package-Manager-*.rpm
```

### Method 2: Install from Source

```bash
git clone https://github.com/grpace/Fedora-DNF-GUI-Tool.git
cd Fedora-DNF-GUI-Tool
sudo ./install.sh
```

The installation script places application files in `/opt/dnf-gui`, configures `/usr/bin/dnf-gui`, and installs application icons and desktop entries.

### Method 3: Run Without Installation

Run the project directly from the source directory:

```bash
git clone https://github.com/grpace/Fedora-DNF-GUI-Tool.git
cd Fedora-DNF-GUI-Tool
PYTHONPATH=src python3 -m dnf_gui
```

---

## Usage

Launch the application through the KDE application launcher under System, or from the terminal:

```bash
dnf-gui
```

### Headless Update Checks

Run a non-interactive update check (used by the background login reminder):

```bash
dnf-gui --check
```

Exit status codes:
- `0`: System is up to date or check completed without action.
- `2`: Updates are pending.

---

## Uninstallation

To remove RPM installations:

```bash
sudo dnf remove dnf-gui
```

To remove source installations:

```bash
sudo ./install.sh remove
```

---

## Security Model

- **Unprivileged data access.** All query operations (search, update checks, package inspection, telemetry) execute with standard user permissions.
- **Standard polkit elevation.** Administrative tasks run through `pkexec`, prompting with standard desktop authorization dialogs.
- **Constrained sudoers configuration.** The optional passwordless upgrade rule restricts non-interactive privilege exclusively to `dnf upgrade` and `dnf update`. Package removals, installs, and repository modifications always require authorization.
- **Safe argument handling.** Operations execute through structured process argument lists without shell interpolation.

---

## Contributing

Contributions and bug reports are welcome on [GitHub](https://github.com/grpace/Fedora-DNF-GUI-Tool).

Maintainers can review [RELEASING.md](RELEASING.md) for version release and packaging procedures.

---

## License

Distributed under the GPL-3.0 License. See [LICENSE](LICENSE) for terms.

**Author:** Greg.Tech — <https://greg.tech>
