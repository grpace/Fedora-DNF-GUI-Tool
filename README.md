# 🚀 Fedora DNF GUI Tool

A modern, user-friendly graphical package manager for Fedora KDE — a Discovery alternative that uses real DNF and Flatpak commands under the hood for reliable, terminal-grade updates.

![License](https://img.shields.io/badge/license-GPL--3.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.12%2B-brightgreen.svg)
![Platform](https://img.shields.io/badge/platform-Fedora%20Linux-informational.svg)
![Version](https://img.shields.io/badge/version-1.1.0-orange.svg)

## ✨ Features

### 📦 Package Management
- **🔄 System Updates** — DNF + Flatpak + security counts on one page
- **⚡ Update Everything** — DNF upgrade and Flatpak update back-to-back in a single terminal session
- **🛡️ Security Only** — Install just security advisories (`dnf upgrade --security`)
- **📏 Upgrade previews** — Package count and download size in every upgrade confirmation
- **↻ Reboot banner** — Tells you when a kernel/core-library update needs a reboot, with one-click reboot
- **🔍 Package details** — Details button (or double-click) on any card for version, repo, size, license
- **📦 Installed Packages** — Browse, search, and filter all installed RPM packages
- **🗑️ Clean Uninstall** — Remove packages with proper dependency cleanup

### 📱 Flatpak Manager
- **Browse installed Flatpak apps** with filter
- **Search Flathub** for new apps — search the entire Flathub catalog from the GUI
- **Install/Remove/Update** Flatpak applications
- **Clean up** unused runtimes and repair installations

### 🖥️ System Overview
- **Live system dashboard** — Fedora version, kernel, KDE Plasma version
- **Hardware info** — CPU, GPU, RAM usage, disk space with visual progress bars
- **Package counts** — RPM and Flatpak totals at a glance

### 🧰 Quick Tools (One-Click Actions)
- **RPM Fusion** — Enable Free and Non-Free repositories
- **Flathub** — Add the Flathub remote to Flatpak
- **Firmware Updates** — Check and apply BIOS/UEFI updates via fwupdmgr
- **System Maintenance** — Clean cache, rebuild metadata, distro-sync

### 🗂️ Repository Manager
- **View all repositories** — Enabled and disabled, with status indicators
- **Enable/Disable repos** with one click
- **Add COPR** — Community repositories via input dialog

### 📜 Transaction History
- **Browse DNF history** — See all past package operations
- **Undo transactions** — Reverse any past install/remove/upgrade
- **View details** — Expand any transaction for full package list

### ⚙️ Settings
- **Discover takeover** — Stop Discover's double updates: per-user notifier
  takeover (no root, reversible) or system-wide PackageKit hardening
- **Update reminders** — Background security reminders with configurable
  interval, plus an optional login check (`dnf-gui --check`)
- **Passwordless updates (opt-in)** — Make `dnf upgrade` passwordless via a
  validated per-user sudoers rule; installs and removals still ask

### 💻 Live Terminal
- **Real-time output** streaming from all package operations
- **Multi-step chains** — Update Everything streams each step in one view
- **Status indicator** — Idle / Running / Success / Error
- **Auto-scroll** and clear functionality

### 🔄 Auto-Update
- **Check for updates** on startup from GitHub releases
- **One-click install** — Download and install new versions from within the app

## ⌨️ Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+1..9` | Switch between pages |
| `Ctrl+R` | Refresh current page |
| `Ctrl+F` | Focus search (Installed, Flatpak, Repositories pages) |

**Update workflow:** the Updates page now shows DNF + Flatpak + Security counts
together, with **Update Everything** (DNF upgrade + Flatpak update in one
session) and **Security Only** (`dnf upgrade --security`). Open **Settings**
to hand updates over from Discover (per-user takeover or system-wide
PackageKit hardening) and to enable background security reminders
(`dnf-gui --check` at login).

## 📋 Requirements

- Fedora Linux 40+ (tested on Fedora 43 KDE)
- Python 3.12+
- PyQt6 ≥ 6.6.0
- DNF package manager
- polkit (for privileged operations)
- sudo (preinstalled on Fedora; used for the passwordless-updates option)
- Flatpak (optional, for Flatpak features)
- fwupd (optional, for firmware updates in Quick Tools)
- libnotify / `notify-send` (optional, for login-time reminder popups)
- dnf-utils-core / `needs-restarting` (optional, improves reboot detection)

## 🛠️ Installation

### Download RPM (Recommended)

**Easiest way** — download and install:

1. **[Download the RPM](https://github.com/grpace/Fedora-DNF-GUI-Tool/releases/latest)** — click `DNF-Package-Manager-vX.Y.Z.rpm` on the Releases page
2. Double-click the downloaded file to open in Software, or run:
   ```bash
   sudo dnf install ~/Downloads/dnf-gui-*.noarch.rpm
   ```

Dependencies (PyQt6, polkit) are installed automatically. Updates via `dnf update dnf-gui`.

### Install from Source

```bash
git clone https://github.com/grpace/Fedora-DNF-GUI-Tool.git
cd Fedora-DNF-GUI-Tool
sudo ./install.sh
```

The installer will install PyQt6, copy the app to `/opt/dnf-gui`, create the `dnf-gui` command, and add a desktop entry.

### Development Mode (No Install Needed)

```bash
git clone https://github.com/grpace/Fedora-DNF-GUI-Tool.git
cd Fedora-DNF-GUI-Tool
PYTHONPATH=src python3 -m dnf_gui
```

### Build an RPM (Maintainers)

```bash
./build-rpm.sh
sudo dnf install ~/rpmbuild/RPMS/noarch/dnf-gui-*.noarch.rpm
```

## 🗑️ Uninstall

To uninstall the Fedora DNF GUI Tool from your system, use the terminal:

```bash
sudo dnf remove dnf-gui
```

This will remove the application and its desktop entry. Any dependencies installed solely for this app may also be removed depending on your DNF configuration.

## 🚀 Usage

```bash
# After install — from anywhere
dnf-gui

# Headless update check (used by the login reminder, exits 2 if updates pending)
dnf-gui --check

# Or find "DNF Package Manager" in your KDE application menu
```

**Note:** Privileged operations (install, update, remove) use `pkexec` for polkit authentication — you'll be prompted for your password through the standard KDE dialog. Tired of typing it for every update? Settings → Password prompts can make `dnf upgrade` passwordless (one-time authentication, installs/removals still ask).


## 🏗️ Architecture

```
src/dnf_gui/
├── app.py                  # Application entry point (+ headless --check mode)
├── core/
│   ├── dnf_backend.py      # DNF subprocess interface (upgrade preview, reboot check)
│   ├── flatpak_backend.py  # Flatpak subprocess interface
│   ├── package.py          # Package data models (Package, UpdateInfo, UpgradePreview)
│   ├── system_info.py      # System info collector (/proc, lspci)
│   ├── updater.py          # App update checker (GitHub releases)
│   ├── worker.py           # QThread workers (18 worker types)
│   ├── security.py         # Security advisories (dnf updateinfo) + combined update
│   ├── discover_manager.py # Discover/PackageKit takeover (per-user + system)
│   ├── app_settings.py     # QSettings prefs + background reminder service
│   └── passwordless.py     # Scoped passwordless-updates sudoers manager
├── ui/
│   ├── main_window.py      # Main window orchestrator
│   ├── sidebar.py          # Navigation sidebar (9 pages)
│   ├── pages/
│   │   ├── updates_page.py       # System updates (combined, security, reboot banner)
│   │   ├── installed_page.py     # Installed packages (with search/filter)
│   │   ├── flatpak_page.py       # Flatpak manager (installed + Flathub search)
│   │   ├── system_info_page.py   # System dashboard
│   │   ├── toolkit_page.py       # Quick tools
│   │   ├── repo_manager_page.py  # Repository manager
│   │   ├── history_page.py       # Transaction history
│   │   ├── terminal_page.py      # Live terminal output
│   │   └── settings_page.py      # Discover, reminders, password prompts
│   ├── widgets/
│   │   ├── page_header.py        # Shared hero header with balanced grid alignment
│   │   ├── package_card.py       # Package display card (Details + double-click)
│   │   ├── package_details.py    # Package details dialog
│   │   └── progress_bar.py       # Animated progress bar
│   └── styles/
│       └── theme.py              # KDE Plasma 6 Breeze theme (Dark & Light, WCAG AA)
│   ├── icons.py              # Crisp scalable vector icon engine (theme-reactive)
└── utils/
    └── helpers.py                # Utility functions
```

## 🔐 Security

- **Read operations** — Run as normal user, no root needed
- **Write operations** — Use `pkexec` for polkit authentication
- **Passwordless updates (opt-in)** — Settings → Password prompts installs a
  validated, per-user sudoers file (`/etc/sudoers.d/90-dnf-gui`) covering
  only `dnf upgrade`/`update`. Installs, removals, repo changes and firmware
  updates still ask for your password. Delete the file (or Disable in the
  app) to restore prompts everywhere
- **No shell injection** — Commands built as argument lists
- **Confirmation dialogs** — Before every destructive operation
- **COPR warning** — Users are warned about community repos

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

**Maintainers:** See [RELEASING.md](RELEASING.md) for the release checklist.

## 📋 Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history and release notes.

## 📄 License

This project is licensed under the GPL-3.0 License — see the [LICENSE](LICENSE) file for details.

## 👤 Author

**Greg.Tech** — [https://greg.tech](https://greg.tech)

---

*Built ❤️ in Chicago*
