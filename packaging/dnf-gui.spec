%global app_name    dnf-gui
%global app_module  dnf_gui
%global install_dir /opt/%{app_name}

Name:           %{app_name}
Version:        1.2.0
Release:        1%{?dist}
Summary:        Discover alternative for Fedora: updates you can see and control
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
Recommends:     libnotify

%description
The Discover alternative for Fedora KDE. Every action runs the real DNF
and Flatpak commands with live output, updates install right away
instead of waiting for a restart, and one click turns off Discover's
update checks.

Includes combined DNF, Flatpak and security updates; "Update without
Major" to skip kernel, graphics driver, firmware and
bootloader updates; guided Fedora release upgrades; repository search and
install; update reminders; repository and COPR management; transaction
history with undo; and light and dark themes.

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

# Desktop entry (shared with install.sh)
install -Dm644 assets/dnf-gui.desktop %{buildroot}%{_datadir}/applications/%{app_name}.desktop

# Icon
mkdir -p %{buildroot}%{_datadir}/icons/hicolor/scalable/apps
cp assets/icons/app_icon.svg %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/%{app_name}.svg

# AppStream metadata (author, description for Discover/Software)
mkdir -p %{buildroot}%{_metainfodir}
cp packaging/dnf-gui.metainfo.xml %{buildroot}%{_metainfodir}/%{app_name}.metainfo.xml

%files
%license LICENSE
%doc README.md CHANGELOG.md
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
* Tue Oct 20 2026 Greg.Tech <hello@greg.tech> - 1.2.0-1
- Add Update without Major: upgrade everything except kernel, graphics drivers, firmware and bootloader (configurable)
- Search the repositories and install RPMs from the new Packages page
- Guided Fedora release upgrades (dnf system-upgrade) with an availability banner
- Mark Major / Unmark Major per package on the Updates page
- Single update button with a favorite mode; security tags and installed -> new versions on update rows
- Clean Up preview, completion notifications, and a Copy Output button
- Security: passwordless rule now lists exact upgrade commands instead of a root-equivalent wildcard
- Security: verify app self-updates against the release SHA-256 digest
- Fix security advisory counts on dnf5, crash on close during background work, concurrent commands
- Accessibility: all theme colors meet WCAG AA contrast in light and dark modes
- Single shared desktop entry and valid AppStream metadata

* Mon Sep 14 2026 Greg.Tech <hello@greg.tech> - 1.1.1-1
- Fix terminal worker crash on command execution and uncancelable operations
- Clean process group isolation and SIGTERM/SIGKILL escalation on cancellation
- Automatically sync login autostart reminder checker with master reminder switch
- Independent Flatpak update checks and notifications alongside Security Updates Only
- Defer passwordless setting update until privilege rule installation succeeds

* Mon Sep 14 2026 Greg.Tech <hello@greg.tech> - 1.1.0-1
- Combined DNF + Flatpak + security view on Updates page (Update Everything, Security Only)
- Upgrade previews (package count + download size) and reboot-required banner
- Package details dialog (Details button / double-click, all pages)
- New Settings page: Discover takeover, update reminders with login check, opt-in passwordless updates
- Light and dark theme support with adaptive vector icons and UI polish across all pages
- Working Ctrl+F search focus; sidebar grows to 9 pages (Ctrl+1..9)

* Thu Mar 12 2026 Greg.Tech <hello@greg.tech> - 1.0.1-1
- Fix History page crash when rapidly clicking Refresh by preventing concurrent history loads

* Thu Mar 12 2026 Greg.Tech <hello@greg.tech> - 1.0.0-1
- Initial release
- DNF package management (install, remove, update, search)
- Flatpak Manager with Flathub search
- System Info dashboard
- Quick Tools (RPM Fusion, codecs, dev tools, VS Code, fwupd, popular apps)
- Repository Manager with COPR support
- Transaction History with undo
- Auto-update checker
