%global app_name    dnf-gui
%global app_module  dnf_gui
%global install_dir /opt/%{app_name}

Name:           %{app_name}
Version:        2.0.0
Release:        1%{?dist}
Summary:        Discover alternative for Fedora: updates you can see and control
License:        GPL-3.0-or-later AND MIT
URL:            https://greg.tech
Vendor:         Greg.Tech <https://greg.tech>
Source0:        %{app_name}-%{version}.tar.gz
BuildArch:      noarch

Requires:       python3 >= 3.12
Requires:       python3-pyqt6
# The interface is Kirigami (QML); each module it imports, by its provide.
Requires:       qt6qml(QtQuick)
Requires:       qt6qml(QtQuick.Controls)
Requires:       qt6qml(QtQuick.Layouts)
Requires:       qt6qml(QtQuick.Shapes)
Requires:       qt6qml(org.kde.kirigami)
Requires:       qt6qml(org.kde.kirigamiaddons.formcard)
Requires:       qt6qml(org.kde.desktop)
Requires:       breeze-icon-theme
Requires:       polkit
Recommends:     flatpak
Recommends:     fwupd
Recommends:     libnotify

%description
The Discover alternative for Fedora KDE. Every action runs the real DNF
and Flatpak commands with live output, updates install right away
instead of waiting for a restart, and one click turns off Discover's
update checks.

Includes combined DNF, Flatpak and security updates; "Update Without
Core" to skip kernel, graphics driver, firmware and bootloader updates;
guided Fedora release upgrades; repository search and install; update
reminders; repository and COPR management; transaction history with undo;
and a native KDE Plasma (Kirigami) interface that follows your Plasma
colors.

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
# -P and no empty PYTHONPATH entry: never import from the current directory.
export PYTHONPATH="%{install_dir}${PYTHONPATH:+:$PYTHONPATH}"
# KDE look for the Qt Quick interface (outside Plasma too).
export QT_QUICK_CONTROLS_STYLE="${QT_QUICK_CONTROLS_STYLE:-org.kde.desktop}"
exec /usr/bin/python3 -P -m %{app_module} "$@"
EOF
chmod 0755 %{buildroot}%{_bindir}/%{app_name}

# Desktop entry (shared with install.sh)
install -Dm644 assets/dnf-gui.desktop %{buildroot}%{_datadir}/applications/%{app_name}.desktop

# Icon
mkdir -p %{buildroot}%{_datadir}/icons/hicolor/scalable/apps
cp src/%{app_module}/ui/app_icon.svg %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/%{app_name}.svg

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
* Tue Nov 17 2026 Greg.Tech <hello@greg.tech> - 2.0.0-1
- New native KDE Plasma interface (Kirigami): follows your Plasma colors and fonts
- Updates page: one clear status, one main button, updates grouped by security, major and Flatpak
- Package and transaction details open beside the list
- Output follows you between pages, with live progress, Cancel and Copy Output
- Confirmations show one at a time; destructive ones default to No
- Rebuilt Installed, Flatpak, History, Repositories, System, Tools and Settings pages
- Keyboard and screen reader support throughout; text meets WCAG AA in Breeze Light and Dark
- The app restarts itself after installing its own update
- Security: privileged tools run from system paths only, never $PATH; self-updates are re-verified as root on a root-only copy; the passwordless rule is checked with visudo before it goes live
- New app icon; own title bar, a floating status capsule for running commands, bold icons and app icons on package rows
- Compact notices; "Major" updates are now "Core" updates; update single Flatpaks from the Updates page
- More on the System page: device, firmware, Plasma version, root filesystem, last update

* Mon Nov 16 2026 Greg.Tech <hello@greg.tech> - 1.5.1-1
- Pass the desktop entry id to setDesktopFileName (no startup warning from Qt)

* Mon Nov 16 2026 Greg.Tech <hello@greg.tech> - 1.5.0-1
- Clicking an update reminder opens the Updates page; View Updates and Show Output buttons
- Notifications carry the app icon and desktop entry, with clearer titles and text
- Opening the app again brings the running window forward (--page opens a given page)
- Closing the window during an operation no longer kills dnf; it finishes in the background
- A failed update check no longer reports the system as up to date
- dnf5 fixes: reboot banner sees core library updates, package details, list headers, history order
- Flatpak installs use the remote the app comes from; dnf4 repo enable/disable works
- Launcher never imports Python modules from the current directory

* Sun Nov 01 2026 Greg.Tech <hello@greg.tech> - 1.4.0-1
- Explain security updates dnf skips because a dependency isn't ready (e.g. RPM Fusion libheif-freeworld): Updates page banner, Waiting tags and count
- Security Only explains when there's nothing installable yet instead of rerunning dnf
- Force Install for waiting security updates, listing exactly what would be removed
- Report skipped packages after every update run
- Reminders ignore security advisories that can't be installed yet

* Sun Nov 01 2026 Greg.Tech <hello@greg.tech> - 1.3.0-1
- Update reminders now work while the app is closed: a per-user systemd timer follows the Check Every setting instead of a login-only autostart entry, with a catch-up check at login when one is due
- Failed reminder checks no longer silence reminders for a whole interval; they wait for the network and retry at most three times
- The per-user reminder skips quietly after the app is uninstalled
- dnf-gui --check skips the update check when reminders are off

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
