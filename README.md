# 🚀 Fedora DNF GUI Tool

A modern, user-friendly graphical package manager for Fedora KDE — built to replace the Discovery app with something faster, cleaner, and more powerful.

![License](https://img.shields.io/badge/license-GPL--3.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.12%2B-brightgreen.svg)
![Platform](https://img.shields.io/badge/platform-Fedora%20Linux-informational.svg)

## ✨ Features

- **🔄 System Updates** — Check for and apply system updates with a single click
- **📦 Installed Packages** — Browse, search, and manage all installed packages
- **🔍 Package Search** — Search the entire DNF repository for new software
- **🗑️ Clean Uninstall** — Remove packages with proper dependency cleanup
- **💻 Live Terminal** — Watch real-time output of all DNF operations
- **🌙 Modern Dark Theme** — Beautiful KDE Breeze-inspired dark interface
- **⚡ Non-blocking UI** — All operations run in background threads

## 📋 Requirements

- Fedora Linux 40+ (tested on Fedora 43 KDE)
- Python 3.12+
- PyQt6
- DNF package manager

## 🛠️ Installation

### From Source

```bash
# Clone the repository
git clone https://github.com/gregtech/fedora-dnf-gui.git
cd fedora-dnf-gui

# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python -m src.dnf_gui
```

### Install PyQt6 on Fedora

```bash
# Via pip (recommended for development)
pip install PyQt6

# Via DNF (system-wide)
sudo dnf install python3-pyqt6
```

## 🚀 Usage

```bash
# Run from project root
python -m src.dnf_gui

# Or use the entry point after pip install
fedora-dnf-gui
```

**Note:** Some operations (install, update, remove) require root privileges. The application will prompt for your password via `pkexec` when needed.

## 🏗️ Project Structure

```
src/dnf_gui/
├── app.py              # Application entry point & initialization
├── core/
│   ├── dnf_backend.py  # DNF command execution layer
│   ├── package.py      # Package data models
│   └── worker.py       # Background thread workers
├── ui/
│   ├── main_window.py  # Main window & layout
│   ├── sidebar.py      # Navigation sidebar
│   ├── pages/          # Feature pages (updates, installed, search, terminal)
│   ├── widgets/        # Reusable UI components
│   └── styles/         # Theme & stylesheet definitions
└── utils/
    └── helpers.py      # Utility functions
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the GPL-3.0 License — see the [LICENSE](LICENSE) file for details.

## 👤 Author

**Greg.Tech** — [https://greg.tech](https://greg.tech)

---

*Built with ❤️ for the Fedora community*
