%global app_name    dnf-gui
%global app_module  dnf_gui
%global install_dir /opt/%{app_name}

Name:           %{app_name}
Version:        1.0.0
Release:        1%{?dist}
Summary:        Modern GUI package manager for Fedora Linux
License:        GPL-3.0-or-later
URL:            https://greg.tech
Vendor:         Greg.Tech <https://greg.tech>
Source0:        %{app_name}-%{version}.tar.gz
BuildArch:      noarch

Requires:       python3 >= 3.12
Requires:       python3-pyqt6
Requires:       polkit
Recommends:     flatpak
Recommends:     fwupd

%description
A modern, user-friendly graphical package manager for Fedora KDE.
Provides DNF package management, Flatpak support, system information,
quick tools, repository management, and transaction history with a
beautiful dark-themed interface.

Built by Greg.Tech — https://greg.tech

%prep
%setup -q

%install
# Application files
mkdir -p %{buildroot}%{install_dir}
cp -r src/%{app_module} %{buildroot}%{install_dir}/

# Launcher script
mkdir -p %{buildroot}%{_bindir}
cat > %{buildroot}%{_bindir}/%{app_name} << 'EOF'
#!/bin/bash
export PYTHONPATH="%{install_dir}:${PYTHONPATH}"
exec python3 -m %{app_module} "$@"
EOF
chmod 0755 %{buildroot}%{_bindir}/%{app_name}

# Desktop entry
mkdir -p %{buildroot}%{_datadir}/applications
cat > %{buildroot}%{_datadir}/applications/%{app_name}.desktop << EOF
[Desktop Entry]
Type=Application
Name=DNF Package Manager
GenericName=Package Manager
Comment=Modern GUI package manager for Fedora Linux — by Greg.Tech
Exec=%{_bindir}/%{app_name}
Icon=%{app_name}
Terminal=false
Categories=System;PackageManager;Settings;
Keywords=dnf;package;manager;update;install;remove;fedora;flatpak;
StartupNotify=true
StartupWMClass=dnf-package-manager
EOF

# Icon
mkdir -p %{buildroot}%{_datadir}/icons/hicolor/scalable/apps
cp assets/icons/app_icon.svg %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/%{app_name}.svg

# AppStream metadata (author, description for Discover/Software)
mkdir -p %{buildroot}%{_metainfodir}
cp packaging/dnf-gui.metainfo.xml %{buildroot}%{_metainfodir}/%{app_name}.metainfo.xml

%files
%license LICENSE
%doc README.md CHANGELOG.md RELEASING.md
%{install_dir}/
%{_bindir}/%{app_name}
%{_datadir}/applications/%{app_name}.desktop
%{_datadir}/icons/hicolor/scalable/apps/%{app_name}.svg
%{_metainfodir}/%{app_name}.metainfo.xml

%post
/usr/bin/update-desktop-database %{_datadir}/applications &>/dev/null || :
/usr/bin/gtk-update-icon-cache %{_datadir}/icons/hicolor &>/dev/null || :
/usr/bin/appstreamcli refresh --force &>/dev/null || :

%postun
/usr/bin/update-desktop-database %{_datadir}/applications &>/dev/null || :
/usr/bin/gtk-update-icon-cache %{_datadir}/icons/hicolor &>/dev/null || :
/usr/bin/appstreamcli refresh --force &>/dev/null || :

%changelog
* Wed Mar 12 2026 Greg.Tech <hello@greg.tech> - 1.0.0-1
- Initial release
- DNF package management (install, remove, update, search)
- Flatpak Manager with Flathub search
- System Info dashboard
- Quick Tools (RPM Fusion, codecs, dev tools, VS Code, fwupd, popular apps)
- Repository Manager with COPR support
- Transaction History with undo
- Auto-update checker
- Live terminal output
- Dark theme UI
