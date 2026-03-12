# 🚀 Fedora DNF GUI Tool

A modern, user-friendly graphical package manager for Fedora KDE — built to replace the Discovery app with something faster, cleaner, and more powerful.

![License](https://img.shields.io/badge/license-GPL--3.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.12%2B-brightgreen.svg)
![Platform](https://img.shields.io/badge/platform-Fedora%20Linux-informational.svg)
![Version](https://img.shields.io/badge/version-1.0.0-orange.svg)

## ✨ Features

### 📦 Package Management
- **🔄 System Updates** — Check for and apply system updates with a single click
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
- **Multimedia Codecs** — Install GStreamer plugins for MP3, MP4, H.264
- **Development Tools** — Install gcc, make, autoconf, Python dev, Node.js, Git
- **VS Code** — One-click install with Microsoft repo setup
- **Firmware Updates** — Check and apply BIOS/UEFI updates via fwupdmgr
- **System Maintenance** — Clean cache, rebuild metadata, distro-sync
- **Popular Apps** — Firefox, Thunderbird, GIMP, LibreOffice, Kdenlive, OBS Studio

### 🗂️ Repository Manager
- **View all repositories** — Enabled and disabled, with status indicators
- **Enable/Disable repos** with one click
- **Add COPR** — Community repositories via input dialog

### 📜 Transaction History
- **Browse DNF history** — See all past package operations
- **Undo transactions** — Reverse any past install/remove/upgrade
- **View details** — Expand any transaction for full package list

### 💻 Live Terminal
- **Real-time output** streaming from all package operations
- **Status indicator** — Idle / Running / Success / Error
- **Auto-scroll** and clear functionality

### 🔄 Auto-Update
- **Check for updates** on startup from GitHub releases
- **One-click install** — Download and install new versions from within the app

## ⌨️ Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+1..8` | Switch between pages |
| `Ctrl+R` | Refresh current page |
| `Ctrl+F` | Focus search input |

## 📋 Requirements

- Fedora Linux 40+ (tested on Fedora 43 KDE)
- Python 3.12+
- PyQt6 ≥ 6.6.0
- DNF package manager
- polkit (for privileged operations)
- Flatpak (optional, for Flatpak features)
- fwupd (optional, for firmware updates in Quick Tools)

## 🛠️ Installation

### Download RPM (Recommended)

**Easiest way** — download and install:

1. **[Download the RPM](https://github.com/gregtech/fedora-dnf-gui/releases/latest)** — click `DNF-Package-Manager-X.Y.Z.rpm` on the Releases page
2. Double-click the downloaded file to open in Software, or run:
   ```bash
   sudo dnf install ~/Downloads/dnf-gui-*.noarch.rpm
   ```

Dependencies (PyQt6, polkit) are installed automatically. Updates via `dnf update dnf-gui`.

### Install from Source

```bash
git clone https://github.com/gregtech/fedora-dnf-gui.git
cd fedora-dnf-gui
sudo ./install.sh
```

The installer will install PyQt6, copy the app to `/opt/dnf-gui`, create the `dnf-gui` command, and add a desktop entry.

### Development Mode (No Install Needed)

```bash
git clone https://github.com/gregtech/fedora-dnf-gui.git
cd fedora-dnf-gui
PYTHONPATH=src python3 -m dnf_gui
```

### Build an RPM (Maintainers)

```bash
./build-rpm.sh
sudo dnf install ~/rpmbuild/RPMS/noarch/dnf-gui-*.noarch.rpm
```

## 🚀 Usage

```bash
# After install — from anywhere
dnf-gui

# Or find "DNF Package Manager" in your KDE application menu
```

**Note:** Privileged operations (install, update, remove) use `pkexec` for polkit authentication — you'll be prompted for your password through the standard KDE dialog.


## 🏗️ Architecture

```
src/dnf_gui/
├── app.py                  # Application entry point
├── core/
│   ├── dnf_backend.py      # DNF subprocess interface (40+ commands)
│   ├── flatpak_backend.py  # Flatpak subprocess interface
│   ├── package.py          # Package data models
│   ├── system_info.py      # System info collector (/proc, lspci)
│   ├── updater.py          # App update checker (GitHub releases)
│   └── worker.py           # QThread workers (14 worker types)
├── ui/
│   ├── main_window.py      # Main window orchestrator
│   ├── sidebar.py          # Navigation sidebar (8 pages)
│   ├── pages/
│   │   ├── updates_page.py       # System updates
│   │   ├── installed_page.py     # Installed packages (with search/filter)
│   │   ├── flatpak_page.py       # Flatpak manager (installed + Flathub search)
│   │   ├── system_info_page.py   # System dashboard
│   │   ├── toolkit_page.py       # Quick tools
│   │   ├── repo_manager_page.py  # Repository manager
│   │   ├── history_page.py       # Transaction history
│   │   └── terminal_page.py      # Live terminal output
│   ├── widgets/
│   │   ├── package_card.py       # Package display card
│   │   └── progress_bar.py       # Animated progress bar
│   └── styles/
│       └── theme.py              # Dark theme QSS
└── utils/
    └── helpers.py                # Utility functions
```

## 🔐 Security

- **Read operations** — Run as normal user, no root needed
- **Write operations** — Use `pkexec` for polkit authentication
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

*Built with ❤️ for the Fedora community*
