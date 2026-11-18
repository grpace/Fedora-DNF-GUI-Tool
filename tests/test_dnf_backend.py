"""Tests for the DNF backend module."""

import unittest
import subprocess
from unittest.mock import patch, MagicMock

from dnf_gui.core.package import Package, PackageStatus
from dnf_gui.core.dnf_backend import DNFBackend


class TestPackageModel(unittest.TestCase):
    """Tests for the Package data model."""

    def test_from_dnf_line_basic(self):
        """Test parsing a basic DNF list output line."""
        line = "firefox.x86_64  125.0-1.fc43  @updates"
        pkg = Package.from_dnf_line(line)
        
        self.assertEqual(pkg.name, "firefox")
        self.assertEqual(pkg.arch, "x86_64")
        self.assertEqual(pkg.version, "125.0")
        self.assertEqual(pkg.release, "1.fc43")
        self.assertEqual(pkg.repo, "@updates")

    def test_from_dnf_line_no_arch(self):
        """Test parsing a line without architecture."""
        line = "bash  5.2.26-1.fc43  @anaconda"
        pkg = Package.from_dnf_line(line)
        
        self.assertIsNotNone(pkg)
        self.assertEqual(pkg.name, "bash")

    def test_from_dnf_line_empty(self):
        """Test parsing an empty line returns None."""
        pkg = Package.from_dnf_line("")
        self.assertIsNone(pkg)

    def test_full_version(self):
        """Test full_version property."""
        pkg = Package(name="test", version="1.0", release="2.fc43")
        self.assertEqual(pkg.full_version, "1.0-2.fc43")

    def test_full_version_no_release(self):
        """Test full_version without release."""
        pkg = Package(name="test", version="1.0")
        self.assertEqual(pkg.full_version, "1.0")


class TestDNFBackend(unittest.TestCase):
    """Tests for the DNF backend."""

    def setUp(self):
        self.backend = DNFBackend()

    @patch("dnf_gui.core.dnf_backend.subprocess.run")
    def test_list_installed_parses_output(self, mock_run):
        """Test that list_installed correctly parses DNF output."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="firefox.x86_64  125.0-1.fc43  @updates\nbash.x86_64  5.2.26-1.fc43  @anaconda\n"
        )
        
        packages = self.backend.list_installed()
        
        self.assertEqual(len(packages), 2)
        self.assertEqual(packages[0].name, "firefox")
        self.assertEqual(packages[1].name, "bash")

    @patch("dnf_gui.core.dnf_backend.subprocess.run")
    def test_list_installed_handles_error(self, mock_run):
        """Test that list_installed returns empty list on failure."""
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        
        packages = self.backend.list_installed()
        
        self.assertEqual(packages, [])

    def test_build_upgrade_command(self):
        """Test upgrade command construction."""
        cmd = self.backend.build_upgrade_command()
        self.assertIn("pkexec", cmd)
        self.assertIn("upgrade", cmd)
        self.assertIn("-y", cmd)
        self.assertIn("--refresh", cmd)

    def test_build_remove_command(self):
        """Test remove command construction."""
        cmd = self.backend.build_remove_command("firefox")
        self.assertIn("pkexec", cmd)
        self.assertIn("remove", cmd)
        self.assertIn("firefox", cmd)
        self.assertIn("-y", cmd)


# Real output captured from dnf5 5.x on Fedora 45 (`dnf5 -C list --installed -q`).
DNF5_LIST_INSTALLED = """\
Installed packages
7zip.x86_64                                          26.04-1.fc45                           updates
Box2D.x86_64                                         3.1.1-3.fc45                           fedora
ImageMagick.x86_64                                   1:7.1.2.35-1.fc45                      updates
"""

# dnf4 format: capitalized header, "@repo", and a long name.arch wrapped
# onto its own line with version/repo on the next one.
DNF4_LIST_INSTALLED = """\
Installed Packages
bash.x86_64                         5.2.26-1.fc39                    @anaconda
python3-some-really-long-package-name-here.noarch
                                    1.2.3-4.fc39                     @updates
zstd.x86_64                         1.5.5-4.fc39                     @fedora
"""

# `dnf5 -C info -q bash` on Fedora 45 (installed package).
DNF5_INFO_INSTALLED = """\
Installed packages
Name            : bash
Epoch           : 0
Version         : 5.3.15
Release         : 2.fc45
Architecture    : x86_64
Installed size  : 8.5 MiB
Source          : bash-5.3.15-2.fc45.src.rpm
From repository : fedora
Summary         : The GNU Bourne Again shell
URL             : https://www.gnu.org/software/bash
License         : GPL-3.0-or-later
Description     : The GNU Bourne Again shell (Bash) is a shell or command language
                : interpreter that is compatible with the Bourne shell (sh). Bash
                : incorporates useful features from the Korn shell (ksh) and the C shell
                : (csh). Most sh scripts can be run by bash without modification.
Vendor          : Fedora Project
"""

# `dnf5 -C info -q hello` on Fedora 45 (not installed; blank continuation line).
DNF5_INFO_AVAILABLE = """\
Available packages
Name           : hello
Epoch          : 0
Version        : 2.12.3
Release        : 2.fc45
Architecture   : x86_64
Download size  : 94.6 KiB
Installed size : 238.3 KiB
Source         : hello-2.12.3-2.fc45.src.rpm
Repository     : fedora
Summary        : Prints a familiar, friendly greeting
URL            : https://www.gnu.org/software/hello/
License        : GPL-3.0-or-later AND GFDL-1.3-or-later
Description    : The GNU Hello program produces a familiar, friendly greeting.
               : Yes, this is another implementation of the classic program that
               : 
               : prints a greeting.
Vendor         : Fedora Project
"""

# dnf5 info for an installed package that also has an update available.
DNF5_INFO_INSTALLED_WITH_UPDATE = """\
Installed packages
Name            : kernel-core
Version         : 7.2.15
Release         : 100.fc45
Architecture    : x86_64
From repository : updates
Summary         : The Linux kernel

Name            : kernel-core
Version         : 7.3.3
Release         : 300.fc45
Architecture    : x86_64
From repository : updates
Summary         : The Linux kernel

Available packages
Name           : kernel-core
Version        : 7.3.4
Release        : 300.fc45
Architecture   : x86_64
Repository     : updates-testing
Summary        : The Linux kernel
"""

DNF4_INFO_INSTALLED = """\
Installed Packages
Name         : bash
Version      : 5.2.26
Release      : 1.fc39
Architecture : x86_64
Size         : 7.9 M
Source       : bash-5.2.26-1.fc39.src.rpm
Repository   : @System
From repo    : anaconda
Summary      : The GNU Bourne Again shell
License      : GPLv3+
Description  : The GNU Bourne Again shell (Bash) is a shell or command language
             : interpreter that is compatible with the Bourne shell (sh).
"""

DNF4_INFO_AVAILABLE = """\
Available Packages
Name         : hello
Version      : 2.12.1
Release      : 2.fc39
Architecture : x86_64
Size         : 85 k
Source       : hello-2.12.1-2.fc39.src.rpm
Repository   : fedora
Summary      : Prints a familiar, friendly greeting
Description  : The GNU Hello program produces a familiar, friendly greeting.
             : Yes, this is another implementation.
"""


class TestPackageListHeaders(unittest.TestCase):
    def setUp(self):
        self.backend = DNFBackend()

    def test_dnf5_installed_header_skipped(self):
        pkgs = self.backend._parse_package_list(
            DNF5_LIST_INSTALLED, PackageStatus.INSTALLED)
        self.assertEqual([p.name for p in pkgs], ["7zip", "Box2D", "ImageMagick"])
        self.assertEqual(pkgs[2].version, "1:7.1.2.35")
        self.assertEqual(pkgs[2].repo, "updates")

    def test_dnf5_check_upgrade_header_skipped(self):
        out = "Upgrades\nnvidia-settings.x86_64 3:620.70.06-2.fc45 rpmfusion-nonfree-updates\n"
        pkgs = self.backend._parse_package_list(out, PackageStatus.UPDATE_AVAILABLE)
        self.assertEqual([p.name for p in pkgs], ["nvidia-settings"])

    def test_dnf4_header_skipped_and_wrapped_row_joined(self):
        pkgs = self.backend._parse_package_list(
            DNF4_LIST_INSTALLED, PackageStatus.INSTALLED)
        self.assertEqual(
            [p.name for p in pkgs],
            ["bash", "python3-some-really-long-package-name-here", "zstd"])
        self.assertEqual(pkgs[1].arch, "noarch")
        self.assertEqual(pkgs[1].full_version, "1.2.3-4.fc39")
        self.assertEqual(pkgs[1].repo, "@updates")


class TestPackageInfoParsing(unittest.TestCase):
    def setUp(self):
        self.backend = DNFBackend()

    def test_dnf5_installed(self):
        pkg = self.backend._parse_package_info(DNF5_INFO_INSTALLED)
        self.assertEqual(pkg.name, "bash")
        self.assertEqual(pkg.status, PackageStatus.INSTALLED)
        self.assertEqual(pkg.repo, "fedora")
        self.assertEqual(pkg.url, "https://www.gnu.org/software/bash")
        self.assertTrue(pkg.description.startswith("The GNU Bourne Again shell (Bash)"))
        self.assertTrue(pkg.description.endswith(
            "Most sh scripts can be run by bash without modification."))
        self.assertIn("command language interpreter that", pkg.description)

    def test_dnf5_available(self):
        pkg = self.backend._parse_package_info(DNF5_INFO_AVAILABLE)
        self.assertEqual(pkg.status, PackageStatus.AVAILABLE)
        self.assertEqual(pkg.repo, "fedora")
        self.assertEqual(pkg.size, "94.6 KiB")
        self.assertTrue(pkg.description.endswith("prints a greeting."))
        self.assertNotIn("  ", pkg.description)

    def test_dnf5_installed_with_update_shows_newest_installed(self):
        pkg = self.backend._parse_package_info(DNF5_INFO_INSTALLED_WITH_UPDATE)
        self.assertEqual(pkg.status, PackageStatus.INSTALLED)
        self.assertEqual(pkg.full_version, "7.3.3-300.fc45")
        self.assertEqual(pkg.repo, "updates")

    def test_dnf4_installed(self):
        pkg = self.backend._parse_package_info(DNF4_INFO_INSTALLED)
        self.assertEqual(pkg.status, PackageStatus.INSTALLED)
        self.assertEqual(pkg.repo, "@System")
        self.assertTrue(pkg.description.endswith("Bourne shell (sh)."))

    def test_dnf4_available(self):
        pkg = self.backend._parse_package_info(DNF4_INFO_AVAILABLE)
        self.assertEqual(pkg.status, PackageStatus.AVAILABLE)
        self.assertEqual(pkg.repo, "fedora")
        self.assertIn("Yes, this is another implementation.", pkg.description)

    def test_no_header_falls_back_to_at_repo(self):
        out = DNF4_INFO_INSTALLED.split("\n", 1)[1]
        pkg = self.backend._parse_package_info(out)
        self.assertEqual(pkg.status, PackageStatus.INSTALLED)

    def test_empty_output(self):
        self.assertIsNone(self.backend._parse_package_info(""))


class TestRebootRequiredDnf5(unittest.TestCase):
    def setUp(self):
        self.backend = DNFBackend()
        self.backend._dnf_path = "/usr/bin/dnf5"

    def _run(self, dnf_rc=None, legacy_rc=None, dnf_exc=None):
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            self.assertIsInstance(cmd, list)
            self.assertNotIn("shell", kwargs)
            self.assertIn("timeout", kwargs)
            if cmd[0] == "/usr/bin/dnf5":
                if dnf_exc:
                    raise dnf_exc
                return MagicMock(returncode=dnf_rc)
            if cmd[0] == "needs-restarting":
                if legacy_rc is None:
                    raise FileNotFoundError()
                return MagicMock(returncode=legacy_rc)
            if cmd[0] == "rpm":  # kernel check: running kernel is newest
                return MagicMock(returncode=0, stdout="1 6.18.5-200.fc45.x86_64\n")
            raise AssertionError(f"unexpected {cmd}")

        with patch("dnf_gui.core.dnf_backend.subprocess.run", side_effect=fake_run), \
                patch("dnf_gui.core.dnf_backend.os.path.exists", return_value=False), \
                patch("dnf_gui.core.dnf_backend.platform.release",
                      return_value="6.18.5-200.fc45.x86_64"):
            return self.backend.check_reboot() is True, calls

    def test_dnf5_builtin_tried_first(self):
        result, calls = self._run(dnf_rc=1)
        self.assertTrue(result)
        self.assertEqual(calls[0],
                         ["/usr/bin/dnf5", "-C", "-q", "needs-restarting", "-r"])
        self.assertEqual(len(calls), 1)

    def test_dnf5_builtin_says_no_reboot(self):
        result, calls = self._run(dnf_rc=0)
        self.assertFalse(result)
        self.assertEqual(len(calls), 1)

    def test_inconclusive_falls_through_to_legacy_binary(self):
        result, calls = self._run(dnf_rc=2, legacy_rc=1)
        self.assertTrue(result)
        self.assertEqual(calls[1], ["needs-restarting", "-r"])

    def test_timeout_falls_through_to_kernel_check(self):
        result, calls = self._run(
            dnf_exc=subprocess.TimeoutExpired("dnf5", 60))
        self.assertFalse(result)
        self.assertEqual(calls[-1][0], "rpm")


class TestHistoryOrder(unittest.TestCase):
    def setUp(self):
        self.backend = DNFBackend()

    def _history(self, output, **kwargs):
        with patch.object(self.backend, "_run", return_value=output) as run:
            txns = self.backend.history(**kwargs)
        self.assertNotIn("--reverse", run.call_args.args[0])
        return txns

    # `dnf5 -C history list` on Fedora 45 (newest first).
    DNF5_HISTORY = "\n".join([
        " ID Command line                       Date and time       Action(s)     Altered",
        "314 /usr/bin/dnf5 upgrade -y --refresh 2026-11-17 00:18:00 U                 686",
        "313 /usr/bin/dnf5 upgrade -y --refresh 2026-11-14 06:57:00 U                 256",
        "312 dnf install -y xfce4-session xfwm4 2026-11-12 20:51:12 I                  25",
        "  9 dnf install https://mirrors.rpmfus 2026-02-18 06:43:44 I                   2",
    ])

    def test_newest_first(self):
        txns = self._history(self.DNF5_HISTORY)
        self.assertEqual([t["id"] for t in txns], ["314", "313", "312", "9"])

    def test_limit_keeps_newest(self):
        txns = self._history(self.DNF5_HISTORY, limit=2)
        self.assertEqual([t["id"] for t in txns], ["314", "313"])

    def test_ascending_input_still_newest_first(self):
        lines = self.DNF5_HISTORY.split("\n")
        ascending = "\n".join([lines[0], *reversed(lines[1:])])
        txns = self._history(ascending, limit=3)
        self.assertEqual([t["id"] for t in txns], ["314", "313", "312"])

    def test_dnf4_pipe_format_newest_first(self):
        out = "\n".join([
            "ID     | Command line             | Date and time    | Action(s)      | Altered",
            "-------------------------------------------------------------------------------",
            "    12 | upgrade -y               | 2024-01-10 10:00 | Upgrade        |   40",
            "    11 | install vim              | 2024-01-09 09:00 | Install        |    1",
        ])
        txns = self._history(out)
        self.assertEqual([t["id"] for t in txns], ["12", "11"])


class TestRepoToggleCommands(unittest.TestCase):
    def setUp(self):
        self.backend = DNFBackend()

    def _with_dnf(self, path, real):
        self.backend._dnf_path = path
        return patch("dnf_gui.core.dnf_backend.os.path.realpath", return_value=real)

    def test_dnf5_uses_setopt(self):
        with self._with_dnf("/usr/bin/dnf5", "/usr/bin/dnf5"):
            self.assertEqual(
                self.backend.build_enable_repo_command("rpmfusion-free"),
                ["pkexec", "/usr/bin/dnf5", "config-manager", "setopt",
                 "rpmfusion-free.enabled=1"])
            self.assertEqual(
                self.backend.build_disable_repo_command("rpmfusion-free"),
                ["pkexec", "/usr/bin/dnf5", "config-manager", "setopt",
                 "rpmfusion-free.enabled=0"])

    def test_dnf_symlinked_to_dnf5_uses_setopt(self):
        with self._with_dnf("/usr/bin/dnf", "/usr/bin/dnf5"):
            self.assertTrue(self.backend.is_dnf5)
            self.assertIn("setopt", self.backend.build_enable_repo_command("x"))

    def test_dnf4_uses_set_enabled_flags(self):
        with self._with_dnf("/usr/bin/dnf", "/usr/bin/dnf-3"):
            self.assertFalse(self.backend.is_dnf5)
            self.assertEqual(
                self.backend.build_enable_repo_command("rpmfusion-free"),
                ["pkexec", "/usr/bin/dnf", "config-manager", "--set-enabled",
                 "rpmfusion-free"])
            self.assertEqual(
                self.backend.build_disable_repo_command("rpmfusion-free"),
                ["pkexec", "/usr/bin/dnf", "config-manager", "--set-disabled",
                 "rpmfusion-free"])


if __name__ == "__main__":
    unittest.main()
