"""The System page's extra facts: device, firmware, desktop, root
filesystem and last update. Every probe reads fixtures here, never this
machine, and gives None instead of raising."""

from unittest.mock import patch

from dnf_gui.core import system_info


def _dmi(tmp_path, **fields):
    for name, value in fields.items():
        (tmp_path / name).write_text(value + "\n")
    return str(tmp_path)


def test_device_is_vendor_and_model(tmp_path):
    base = _dmi(tmp_path, sys_vendor="LENOVO", product_name="ThinkPad X1 Carbon Gen 11")
    assert system_info._get_device(base) == "LENOVO ThinkPad X1 Carbon Gen 11"


def test_device_skips_placeholders_and_falls_back(tmp_path):
    base = _dmi(tmp_path, sys_vendor="ASUS", product_name="System Product Name",
                product_family="To be filled by O.E.M.", board_name="PRIME Z690M-PLUS D4")
    assert system_info._get_device(base) == "ASUS PRIME Z690M-PLUS D4"
    empty = tmp_path / "empty"
    empty.mkdir()
    assert system_info._get_device(_dmi(empty, sys_vendor="Default string",
                                        product_name="Default string")) is None
    assert system_info._get_device(str(tmp_path / "missing")) is None


def test_device_does_not_repeat_the_vendor(tmp_path):
    base = _dmi(tmp_path, sys_vendor="Framework", product_name="Framework Laptop 13")
    assert system_info._get_device(base) == "Framework Laptop 13"


def test_firmware_version_and_iso_date(tmp_path):
    base = _dmi(tmp_path, bios_version="03.05", bios_date="08/12/2024")
    assert system_info._get_firmware(base) == "03.05 (2024-08-12)"
    assert system_info._get_firmware(str(tmp_path / "missing")) is None


def test_root_filesystem_type(tmp_path):
    mounts = tmp_path / "mounts"
    mounts.write_text("rootfs / rootfs rw 0 0\n"
                      "/dev/nvme0n1p3 / btrfs rw,relatime,subvol=/root 0 0\n"
                      "/dev/nvme0n1p3 /home btrfs rw 0 0\n")
    assert system_info._get_root_fs(str(mounts)) == "btrfs"
    assert system_info._get_root_fs(str(tmp_path / "missing")) is None


def test_desktop_uses_the_installed_plasma_version():
    calls = []

    def run(cmd):
        calls.append(cmd)
        return "6.8.2"
    with patch.dict("os.environ", {"XDG_CURRENT_DESKTOP": "KDE"}):
        assert system_info._get_desktop("KDE (Plasma 6)", "Wayland", run) == "KDE Plasma 6.8.2 (Wayland)"
    # An argument list with an absolute rpm, never a shell.
    assert calls[0][0].endswith("/rpm") and calls[0][1:] == ["-q", "--qf", "%{VERSION}", "plasma-workspace"]


def test_desktop_falls_back_to_the_session_name():
    with patch.dict("os.environ", {"XDG_CURRENT_DESKTOP": "KDE"}):
        # rpm missing or not installed: keep what the session says.
        assert system_info._get_desktop("KDE", "X11", lambda cmd: None) == "KDE (X11)"
        assert system_info._get_desktop("KDE", "Wayland",
                                        lambda cmd: "package plasma-workspace is not installed") == "KDE (Wayland)"
    with patch.dict("os.environ", {"XDG_CURRENT_DESKTOP": "GNOME"}):
        assert system_info._get_desktop("GNOME", "Unknown", lambda cmd: "6.8.2") == "GNOME"
        assert system_info._get_desktop("Unknown", "Unknown", lambda cmd: None) is None


def test_last_update_is_the_newest_upgrade_not_any_transaction():
    listing = ("ID Command line             Date and time       Action(s) Altered\n"
               "215 install -y htop          2026-11-17 10:03:41                 1\n"
               "214 upgrade -y --refresh     2026-11-16 21:12:05                38\n"
               "213 remove -y gnome-tour     2026-11-14 10:03:41                 1\n")
    assert system_info._get_last_update(lambda cmd: listing) == "2026-11-16 09:12 PM"
    only_installs = ("ID Command line             Date and time       Action(s) Altered\n"
                     "215 install -y htop          2026-11-17 10:03:41                 1\n")
    assert system_info._get_last_update(lambda cmd: only_installs) is None
    assert system_info._is_upgrade({"command": "", "action": "E, I, U"})
    assert system_info._is_upgrade({"command": "", "action": "Upgrade"})
    assert not system_info._is_upgrade({"command": "install foo", "action": "Install"})
    assert system_info._get_last_update(lambda cmd: None) is None
    assert system_info._get_last_update(lambda cmd: "") is None


def test_run_quick_never_raises():
    with patch("subprocess.run", side_effect=OSError("nope")):
        assert system_info._run_quick(["/usr/bin/true"]) is None
    import subprocess
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("x", 3)):
        assert system_info._run_quick(["/usr/bin/true"]) is None
