# FAQ

### Is it safe to install updates while I'm using the computer?

Yes. It's what `sudo dnf upgrade` does, and it's how most Fedora users on the command line update. Running programs keep using the old version until you restart them. A few updates (the kernel, glibc, systemd and similar core pieces) only fully take effect after a reboot. DNF Package Manager checks for that after every upgrade and shows a **Restart to finish updating** notice when it applies.

Discover's offline approach, which installs everything during a restart, is more conservative. If you'd rather never update a running system, Discover is the better fit for you.

### Do I have to uninstall Discover?

No. The takeover only turns off Discover's *update* checks and notifications. Discover keeps working for browsing and installing apps, Flatpaks and Plasma add-ons. See [Switching from Discover](switching-from-discover.md).

### Will it conflict with Discover or PackageKit?

dnf and PackageKit lock the package database, so they can't change the system at the same time; one waits for the other. Conflicts in practice come from both apps checking for updates and notifying you, which the takeover turns off.

### What does "Update Without Core" skip, and is that safe long term?

By default it skips the kernel (`kernel*`), firmware (`linux-firmware*`, `*-gpu-firmware`), NVIDIA and Mesa graphics drivers (`*nvidia*`, `akmod-*`, `mesa-*`) and the bootloader (`grub2-*`, `shim-*`). These are the updates most likely to need a reboot or affect the display. They're tagged **Core** on the Updates page.

It's meant for day-to-day updates, not forever. Kernel and driver updates include security fixes, so run **Upgrade All** regularly, for example on a day when a reboot suits you.

### What does the "Core" tag mean?

It marks an update that **Update Without Core** will skip. It doesn't mean the package is frozen: **Upgrade All** and **Update Everything** still install it. Open the update to see why it counts as core: either it matches one of the core patterns above, or you chose **Treat as Core** for it.

### How does it know a new Fedora release is out?

It asks Fedora's release service, Bodhi (`bodhi.fedoraproject.org`), which GNOME Software also uses. Only releases marked *current* are offered, so you're never offered a beta or release candidate, and you can upgrade at most two releases at once, as Fedora supports. **Not Now** hides the offer until the next release.

### What does a Fedora release upgrade actually run?

Fedora's documented steps:

1. `dnf upgrade --refresh`
2. `dnf system-upgrade download --releasever=N`
3. `dnf system-upgrade reboot`, only when you click **Restart and Install**

If step 2 fails because some packages (often from a COPR or third-party repo) have no build for the new release yet, the app offers to retry with `--allowerasing`. Check the output first to see which packages would be removed. A finished download can be cancelled from the Updates page (`dnf system-upgrade clean`).

On Fedora 40, which uses dnf4, release upgrades need dnf's system-upgrade plugin: `sudo dnf install dnf-plugin-system-upgrade`. Fedora 41 and later include it.

### Does it work on Silverblue, Kinoite or other Atomic desktops?

No. Atomic desktops manage the system with rpm-ostree, not dnf.

### Why does the window have its own title bar?

So the sidebar can run to the top of the window, the way many modern desktop apps look. The page header works like a normal title bar: drag it to move the window, double-click it to maximize, and use the minimize, maximize and close buttons in the top-right corner. Resize from any edge or corner. Plasma's window shortcuts still work as usual, for example `Alt+F3` for the window menu or `Meta`-drag to move.

### Does it work on GNOME or other desktops?

Yes. It's a Qt app and works on any Fedora desktop that uses dnf. The Discover takeover only matters on KDE Plasma; GNOME Software has its own update settings.

### Why is a security update still listed after I ran Security Only?

dnf skips an update when installing it would break another package. This usually happens with a third-party package, for example RPM Fusion's `libheif-freeworld`, which requires one exact version of Fedora's `libheif`. When Fedora ships a security fix for `libheif`, the update has to wait until RPM Fusion publishes a matching `libheif-freeworld`. That usually takes a few days.

The Updates page shows a notice naming the package holding the update back, and the affected rows are tagged **Waiting**. Rerunning Security Only won't help until the matching update is out. If you can't wait, click **Details…** on that notice and choose **Force Install…**, which installs the update now by removing the blocking package. The confirmation lists what will be removed and how to reinstall it later.

### Why does it ask for my password?

Anything that changes the system runs through polkit (`pkexec`), the same password dialog other desktop tools use. To stop prompts for routine updates, use **Settings → Passwordless Updates → Turn On…** with **Updates Only**. It covers exactly the Upgrade All, Security Only and Update Without Core commands; everything else still asks.

### What does it connect to?

- Your configured repositories and mirrors (through dnf), and Flathub (through flatpak).
- `bodhi.fedoraproject.org`, to see whether a new Fedora release is out.
- `api.github.com`, to check for a newer version of this app. If you accept, the update is downloaded from GitHub and its checksum verified before installing.

There's no telemetry or analytics.

### Where are my settings stored?

- App settings: `~/.config/Greg.Tech/DNF Package Manager.conf`
- Update reminders: `~/.config/systemd/user/dnf-gui-update-checker.{timer,service}`. See the next run with `systemctl --user list-timers dnf-gui-update-checker.timer` and past runs with `journalctl --user -u dnf-gui-update-checker`.
- Passwordless rule (if enabled): `/etc/sudoers.d/90-dnf-gui`

### Something failed. How do I report it?

Open the output (**Show Output** on the status capsule at the bottom, the **Output** entry in the sidebar, or `Ctrl+T`), click **Copy Output**, and paste the log into a [GitHub issue](https://github.com/grpace/Fedora-DNF-GUI-Tool/issues) along with your Fedora version (`cat /etc/fedora-release`).
