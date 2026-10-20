# FAQ

### Is it safe to install updates while I'm using the computer?

Yes. It's what `sudo dnf upgrade` does, and it's how most Fedora users on the command line update. Running programs keep using the old version until you restart them. A few updates (the kernel, glibc, systemd and similar core pieces) only fully take effect after a reboot. DNF Package Manager checks for that after every upgrade and shows a **Reboot Required** banner when it applies.

Discover's offline approach, which installs everything during a restart, is more conservative. If you'd rather never update a running system, Discover is the better fit for you.

### Do I have to uninstall Discover?

No. The takeover only turns off Discover's *update* checks and notifications. Discover keeps working for browsing and installing apps, Flatpaks and Plasma add-ons. See [Switching from Discover](switching-from-discover.md).

### Will it conflict with Discover or PackageKit?

dnf and PackageKit lock the package database, so they can't change the system at the same time; one waits for the other. Conflicts in practice come from both apps checking for updates and notifying you, which the takeover turns off.

### What does "Update without Major" skip, and is that safe long term?

By default it skips the kernel (`kernel*`), firmware (`linux-firmware*`, `*-gpu-firmware`), NVIDIA and Mesa graphics drivers (`*nvidia*`, `akmod-*`, `mesa-*`) and the bootloader (`grub2-*`, `shim-*`). These are the updates most likely to need a reboot or affect the display. They're tagged **Major** on the Updates page.

It's meant for day-to-day updates, not forever. Kernel and driver updates include security fixes, so run **Upgrade All** regularly, for example on a day when a reboot suits you.

### What does the "Major" tag mean?

It marks an update that **Update without Major** will skip. It doesn't mean the package is frozen: **Upgrade All** and **Update Everything** still install it. Hover over the tag to see why a package counts as major: either it matches one of the core patterns above, or you clicked **Mark Major** on it.

### How does it know a new Fedora release is out?

It asks Fedora's release service, Bodhi (`bodhi.fedoraproject.org`), which GNOME Software also uses. Only releases marked *current* are offered, so you're never offered a beta or release candidate, and you can upgrade at most two releases at once, as Fedora supports. **Not Now** hides the offer until the next release.

### What does a Fedora release upgrade actually run?

Fedora's documented steps:

1. `dnf upgrade --refresh`
2. `dnf system-upgrade download --releasever=N`
3. `dnf system-upgrade reboot`, only when you click **Restart & Install**

If step 2 fails because some packages (often from a COPR or third-party repo) have no build for the new release yet, the app offers to retry with `--allowerasing`. Check the terminal output first to see which packages would be removed. A finished download can be cancelled from the Updates page (`dnf system-upgrade clean`).

On Fedora 40, which uses dnf4, release upgrades need dnf's system-upgrade plugin: `sudo dnf install dnf-plugin-system-upgrade`. Fedora 41 and later include it.

### Does it work on Silverblue, Kinoite or other Atomic desktops?

No. Atomic desktops manage the system with rpm-ostree, not dnf.

### Does it work on GNOME or other desktops?

Yes. It's a Qt app and works on any Fedora desktop that uses dnf. The Discover takeover only matters on KDE Plasma; GNOME Software has its own update settings.

### Why does it ask for my password?

Anything that changes the system runs through polkit (`pkexec`), the same password dialog other desktop tools use. To stop prompts for routine updates, enable **Settings → Password Prompts → Updates Only**. It covers exactly the Upgrade All, Security Only and Update without Major commands; everything else still asks.

### What does it connect to?

- Your configured repositories and mirrors (through dnf), and Flathub (through flatpak).
- `bodhi.fedoraproject.org`, to see whether a new Fedora release is out.
- `api.github.com`, to check for a newer version of this app. If you accept, the update is downloaded from GitHub and its checksum verified before installing.

There's no telemetry or analytics.

### Where are my settings stored?

- App settings: `~/.config/Greg.Tech/DNF Package Manager.conf`
- Login reminder: `~/.config/autostart/dnf-gui-update-checker.desktop`
- Passwordless rule (if enabled): `/etc/sudoers.d/90-dnf-gui`

### Something failed. How do I report it?

Open the **Terminal** page, click **Copy Output**, and paste the log into a [GitHub issue](https://github.com/grpace/Fedora-DNF-GUI-Tool/issues) along with your Fedora version (`cat /etc/fedora-release`).
