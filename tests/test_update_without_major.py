"""Tests for 'Update without Major' (upgrade with core packages held back)."""

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from dnf_gui.core.dnf_backend import (
    DEFAULT_HELD_BACK_PATTERNS, DNFBackend, is_held_back,
    parse_held_back_patterns,
)
from dnf_gui.core.package import Package, PackageStatus, UpdateInfo, UpgradePreview
from dnf_gui.core.passwordless import SCOPE_UPDATES, maybe_passwordless

_app = None


def setUpModule():
    global _app
    _app = QApplication.instance() or QApplication([])


def _backend():
    with patch("shutil.which", return_value="/usr/bin/dnf5"):
        return DNFBackend()


class TestHeldBackMatching(unittest.TestCase):
    def test_defaults_hold_back_core_packages(self):
        for name in ("kernel", "kernel-core", "kernel-modules-extra",
                     "linux-firmware", "amd-gpu-firmware", "akmod-nvidia",
                     "xorg-x11-drv-nvidia-libs", "nvidia-settings",
                     "mesa-dri-drivers", "grub2-efi-x64", "shim-x64"):
            self.assertTrue(is_held_back(name, DEFAULT_HELD_BACK_PATTERNS), name)

    def test_defaults_let_regular_packages_through(self):
        for name in ("firefox", "kmod", "kmod-libs", "glibc", "systemd",
                     "xorg-x11-drv-libinput", "plasma-desktop"):
            self.assertFalse(is_held_back(name, DEFAULT_HELD_BACK_PATTERNS), name)

    def test_parse_patterns(self):
        valid, invalid = parse_held_back_patterns(
            "kernel*, mesa-*\n*nvidia*  kernel*, bad;rm, --all")
        self.assertEqual(valid, ["kernel*", "mesa-*", "*nvidia*"])
        self.assertEqual(invalid, ["bad;rm", "--all"])


class TestCommand(unittest.TestCase):
    def test_builds_plain_dnf_upgrade_with_excludes(self):
        cmd = _backend().build_upgrade_without_major_command(["kernel*", "mesa-*"])
        self.assertEqual(cmd[:4], ["pkexec", "/usr/bin/dnf5", "upgrade", "-y"])
        self.assertIn("--refresh", cmd)
        self.assertEqual(cmd[-1], "--exclude=kernel*,mesa-*")

    def test_drops_unsafe_patterns(self):
        cmd = _backend().build_upgrade_without_major_command(
            ["kernel*", "--setopt=x", "a b"])
        self.assertEqual(cmd[-1], "--exclude=kernel*")

    def test_covered_by_passwordless_updates_scope(self):
        cmd = _backend().build_upgrade_without_major_command(["kernel*"])
        self.assertEqual(maybe_passwordless(cmd, SCOPE_UPDATES)[:2], ["sudo", "-n"])


class TestPreviewFiltering(unittest.TestCase):
    def test_excluding_recomputes_count_and_size(self):
        output = ("firefox 125.0-1.fc44 x86_64 1000\n"
                  "kernel-core 6.18.5-200.fc44 x86_64 5000\n"
                  "mesa-libGL 25.1-1.fc44 x86_64 300\n")
        with patch.object(DNFBackend, "_run", return_value=output):
            preview = _backend().get_upgrade_preview()
        self.assertEqual(preview.count, 3)
        minor = preview.excluding(DEFAULT_HELD_BACK_PATTERNS)
        self.assertEqual(minor.count, 1)
        self.assertEqual(minor.total_bytes, 1000)
        self.assertTrue(minor.sizes_known)

    def test_excluding_everything_has_no_preview(self):
        preview = UpgradePreview(count=1, total_bytes=5, sizes_known=True,
                                 entries=[("kernel", 5)])
        self.assertFalse(preview.excluding(["kernel*"]).has_preview)


class TestUpdatesPageButton(unittest.TestCase):
    def _info(self, *names):
        return UpdateInfo(packages=[
            Package(name=n, version="1", status=PackageStatus.UPDATE_AVAILABLE)
            for n in names])

    def test_enabled_only_when_non_core_updates_pending(self):
        from dnf_gui.ui.pages.updates_page import UpdatesPage
        page = UpdatesPage()
        page.display_updates(self._info("kernel", "kernel-core", "mesa-libGL"))
        self.assertFalse(page._action_button.is_mode_enabled("minor"))
        self.assertEqual(page.held_back_package_names(),
                         ["kernel", "kernel-core", "mesa-libGL"])

        page.display_updates(self._info("kernel", "firefox"))
        self.assertTrue(page._action_button.is_mode_enabled("minor"))
        self.assertEqual(page.minor_package_names(), ["firefox"])

    def test_custom_patterns_update_button(self):
        from dnf_gui.ui.pages.updates_page import UpdatesPage
        page = UpdatesPage()
        page.display_updates(self._info("firefox"))
        self.assertTrue(page._action_button.is_mode_enabled("minor"))
        page.set_held_back_patterns(["firefox"])
        self.assertFalse(page._action_button.is_mode_enabled("minor"))

    def test_empty_disables(self):
        from dnf_gui.ui.pages.updates_page import UpdatesPage
        page = UpdatesPage()
        page.display_updates(UpdateInfo())
        self.assertFalse(page._action_button.is_mode_enabled("minor"))


if __name__ == "__main__":
    unittest.main()
