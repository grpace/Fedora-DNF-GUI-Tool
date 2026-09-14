# Fedora DNF GUI Tool

Fedora DNF GUI Tool is a graphical package manager for Fedora Linux and KDE Plasma. It runs native DNF and Flatpak commands directly, displaying live terminal output for all system changes.

![License](https://img.shields.io/badge/license-GPL--3.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.12%2B-brightgreen.svg)
![Platform](https://img.shields.io/badge/platform-Fedora%20Linux-informational.svg)
![Version](https://img.shields.io/badge/version-1.1.1-orange.svg)

## Features

### Package Management

- **System updates.** View DNF, Flatpak, and security advisory counts on a single screen.
- **Combined upgrades.** Run DNF upgrade and Flatpak update sequentially in one terminal session.
- **Security advisories.** Apply security-specific updates via `dnf upgrade --security`.
- **Upgrade previews.** Review package counts and total download sizes before confirming an upgrade.
- **Reboot reminders.** Displays an alert with a reboot button when an update modifies the kernel or core system libraries.
- **Package details.** Inspect package version, architecture, repository, size, and license by selecting Details or double-clicking any package card.
- **Installed packages.** Search and filter installed RPM packages.
- **Clean removal.** Remove packages alongside orphaned dependencies.

### Flatpak Management

- **Installed applications.** Browse, filter, update, and uninstall installed Flatpaks.
- **Flathub catalog search.** Query and install apps directly from Flathub.
- **System maintenance.** Remove unused runtimes and repair installations with one click.

### System Overview

- **Environment details.** Displays Fedora release, Linux kernel, and KDE Plasma versions.
- **Hardware metrics.** Tracks CPU, GPU, memory, and disk usage.
- **Package totals.** Displays RPM and Flatpak package counts.

### Quick Tools

- **RPM Fusion.** Enable Free and Non-Free repositories.
- **Flathub.** Add the Flathub remote to Flatpak.
- **Firmware updates.** Query and install device firmware updates via `fwupdmgr`.
- **Maintenance.** Clear DNF cache, rebuild metadata, or run distribution synchronization.

### Repository Manager

- **Repository status.** List all system repositories with enabled and disabled states.
- **Toggle repositories.** Enable or disable software sources with a single toggle.
- **COPR repositories.** Add Fedora Community Outer Package Repositories by name.

### Transaction History

- **Audit history.** Review past DNF transactions and package changes.
- **Undo operations.** Roll back past installs, removals, or upgrades.
- **Transaction inspection.** View affected packages and execution timestamps.

### Settings

- **Discover coordination.** Disable KDE Discover notifier popups to avoid duplicate update alerts, with optional system-wide PackageKit masking.
- **Background reminders.** Schedule update checks at configurable intervals with automatic login autostart (`dnf-gui --check`).
- **Independent Flatpak alerts.** Choose whether to receive Flatpak notifications when routine RPM alerts are silenced.
- **Passwordless updates.** Optionally install a validated sudoers drop-in (`/etc/sudoers.d/90-dnf-gui`) allowing passwordless `dnf upgrade`. Package installations, removals, and repository modifications continue to require polkit authorization.

### Appearance

- **Themes.** Choose between dark and light modes matching KDE Plasma styling.
- **Adaptive icons.** Scalable vector icons adjust stroke and fill to match the active color palette.

### Live Terminal

- **Streaming output.** Standard output and standard error stream live during execution.
- **Process control.** Cancel running commands immediately with process group termination.
- **Status indicators.** Clear states for idle, running, completed, cancelled, and failed tasks.

### Application Updates

- **Automatic checks.** Checks GitHub releases on startup for new versions.
- **Integrated installer.** Downloads the release RPM and applies the upgrade via DNF.

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+1` through `Ctrl+9` | Switch pages |
| `Ctrl+R` | Refresh active page |
| `Ctrl+F` | Focus search field on Installed, Flatpak, and Repositories pages |

## Requirements

- Fedora Linux 40 or newer
- Python 3.12 or newer
- PyQt6 6.6.0 or newer
- DNF package manager
- polkit
- sudo
- Flatpak (optional)
- fwupd (optional)
- libnotify / `notify-send` (optional, for desktop notifications)
- dnf-utils-core / `needs-restarting` (optional, for kernel reboot detection)

## Installation

### RPM Package (Recommended)

1. Download `DNF-Package-Manager-v1.1.1.rpm` from [GitHub Releases](https://github.com/grpace/Fedora-DNF-GUI-Tool/releases/latest).
2. Install the package:
   ```bash
   sudo dnf install ~/Downloads/DNF-Package-Manager-*.rpm
   ```

DNF resolves required dependencies automatically.

### Source Installation

```bash
git clone https://github.com/grpace/Fedora-DNF-GUI-Tool.git
cd Fedora-DNF-GUI-Tool
sudo ./install.sh
```

`install.sh` installs Python dependencies, copies application files to `/opt/dnf-gui`, configures `/usr/bin/dnf-gui`, and registers the desktop launcher.

### Development Run

```bash
git clone https://github.com/grpace/Fedora-DNF-GUI-Tool.git
cd Fedora-DNF-GUI-Tool
PYTHONPATH=src python3 -m dnf_gui
```

### Build RPM

```bash
./build-rpm.sh
sudo dnf install ~/rpmbuild/RPMS/noarch/dnf-gui-*.noarch.rpm
```

## Uninstallation

```bash
sudo dnf remove dnf-gui
```

To remove source installations:

```bash
sudo ./install.sh remove
```

## Usage

Launch DNF Package Manager from the application menu or terminal:

```bash
dnf-gui
```

Run a headless check (returns exit code 2 when updates are pending):

```bash
dnf-gui --check
```

Privileged actions use polkit (`pkexec`) and prompt through standard system dialogs. If you enable the passwordless update setting in Settings, `dnf upgrade` commands run through sudo without a password prompt.

## Security

- **Unprivileged queries.** Search, inspection, and update checks run under user privileges without root access.
- **Polkit authentication.** Modifications invoke `pkexec` directly.
- **Scoped sudoers rule.** When enabled, the sudoers drop-in (`/etc/sudoers.d/90-dnf-gui`) restricts passwordless execution exclusively to `dnf upgrade` and `dnf update`.
- **Structured arguments.** Commands execute with explicit argument lists rather than raw shell strings.
- **Confirmation dialogs.** Potentially destructive operations require user confirmation before execution.

## Contributing

Submit pull requests and issue reports on [GitHub](https://github.com/grpace/Fedora-DNF-GUI-Tool).

Maintainers can refer to [RELEASING.md](RELEASING.md) for version bumping, packaging, and release steps.

## License

This project is licensed under the GPL-3.0 License. See [LICENSE](LICENSE) for details.

## Author

Greg.Tech — <https://greg.tech>
