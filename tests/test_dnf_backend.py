"""The DNF backend: parsing dnf5 and dnf4 output, and the argv it builds.

Reboot detection is in test_reboot.py; the upgrade commands the
passwordless rule lists are in test_sudoers_sync.py.
"""

import subprocess
import unittest
from unittest.mock import MagicMock, patch

from dnf_gui.core.dnf_backend import DNFBackend
from dnf_gui.core.package import Package, PackageStatus
from tests.conftest import make_backend


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


class TestListInstalled(unittest.TestCase):
    def setUp(self):
        self.backend = make_backend()

    @patch("dnf_gui.core.dnf_backend.subprocess.run")
    def test_parses_output(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="firefox.x86_64  125.0-1.fc43  @updates\nbash.x86_64  5.2.26-1.fc43  @anaconda\n"
        )
        packages = self.backend.list_installed()
        self.assertEqual([p.name for p in packages], ["firefox", "bash"])

    @patch("dnf_gui.core.dnf_backend.subprocess.run")
    def test_failure_is_an_empty_list(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        self.assertEqual(self.backend.list_installed(), [])


class TestCommands(unittest.TestCase):
    def test_package_commands_are_exact_argv(self):
        backend = make_backend()
        self.assertEqual(backend.build_install_command("htop"),
                         ["pkexec", "/usr/bin/dnf5", "install", "-y", "htop"])
        self.assertEqual(backend.build_remove_command("htop"),
                         ["pkexec", "/usr/bin/dnf5", "remove", "-y", "htop"])
        # Upgrading one package uses `upgrade`: `install` may not upgrade.
        self.assertEqual(backend.build_upgrade_package_command("firefox"),
                         ["pkexec", "/usr/bin/dnf5", "upgrade", "-y", "firefox"])
        self.assertEqual(backend.build_autoremove_command(),
                         ["pkexec", "/usr/bin/dnf5", "autoremove", "-y"])

    def test_firmware_check_treats_no_updates_as_success(self):
        """fwupdmgr exits 2 for "no updates"; real errors still fail."""
        script = make_backend().build_firmware_update_check_command()[2]
        for fw_rc, expected in ((0, 0), (1, 1), (2, 0), (3, 3)):
            probe = script.replace("fwupdmgr get-updates", f"(exit {fw_rc})")
            self.assertEqual(subprocess.run(["bash", "-c", probe]).returncode,
                             expected, fw_rc)


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
        self.backend = make_backend()

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
        self.backend = make_backend()

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


class TestHistoryOrder(unittest.TestCase):
    def setUp(self):
        self.backend = make_backend()

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
        self.backend = make_backend()

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



class TestRepoList(unittest.TestCase):
    def test_parses_ids_names_and_status(self):
        sample_output = "\n".join([
            "repo id                                            repo name                                                  status",
            "brave-browser                                      Brave Browser                                              enabled",
            "copr:copr.fedorainfracloud.org:avengemedia:dms     Copr repo for dms owned by avengemedia                     disabled",
            "fedora                                             Fedora 43 - x86_64                                         enabled",
        ])
        backend = make_backend()
        with patch.object(backend, "_run", return_value=sample_output):
            repos = backend.list_repos(show_all=True)
        self.assertEqual(len(repos), 3)
        self.assertEqual((repos[0]["id"], repos[0]["name"], repos[0]["enabled"]),
                         ("brave-browser", "Brave Browser", True))
        self.assertEqual(repos[1]["id"], "copr:copr.fedorainfracloud.org:avengemedia:dms")
        self.assertEqual(repos[1]["name"], "Copr repo for dms owned by avengemedia")
        self.assertFalse(repos[1]["enabled"])


class TestHistoryParsing(unittest.TestCase):
    def test_packagekit_transactions_have_a_name(self):
        sample_output = "\n".join([
            "    ID Command line                         Date and time       Action(s) Altered",
            "   242 /usr/bin/dnf5 upgrade -y --refresh   2026-09-09 13:03:56               126",
            "   238                                      2026-09-05 05:51:10                 2",
        ])
        backend = make_backend()
        with patch.object(backend, "_run", return_value=sample_output):
            txns = backend.history()
        self.assertEqual([(t["id"], t["altered"]) for t in txns], [("242", "126"), ("238", "2")])
        self.assertEqual(txns[1]["command"], "System / PackageKit")


DNF5_SEARCH = (
    "Matched fields: name (exact)\n"
    " htop.x86_64\tInteractive process viewer\n"
    "Matched fields: name, summary\n"
    " neohtop-debuginfo.x86_64\tDebug information for package neohtop\n"
    " neohtop.aarch64\tSystem monitoring on steroids\n"
    " neohtop.x86_64\tSystem monitoring on steroids\n"
    " neohtop.i686\tSystem monitoring on steroids\n"
)
DNF4_SEARCH = (
    "=== Name Exactly Matched: htop ===\n"
    "htop.x86_64 : Interactive process viewer\n"
    "=== Name & Summary Matched: htop ===\n"
    "pcp-htop.x86_64 : Performance Co-Pilot htop\n"
)


class TestRepoSearch(unittest.TestCase):
    def _search(self, output, installed=None):
        backend = make_backend()

        def fake_run(cmd, allow_nonzero=False):
            if "repoquery" in cmd:
                return "neohtop 1.2.0-1.fc44 updates\npcp-htop 6.3-1.fc44 fedora\n"
            return output

        with patch.object(DNFBackend, "_run", side_effect=fake_run), \
             patch.object(DNFBackend, "_installed_versions",
                          return_value=installed or {}), \
             patch("dnf_gui.core.dnf_backend.platform.machine", return_value="x86_64"):
            return backend.search("htop")

    def test_dnf5_keeps_order_native_arch_and_skips_debug(self):
        results = self._search(DNF5_SEARCH, {"htop": "3.4.1-3.fc44"})
        self.assertEqual([(p.name, p.arch) for p in results],
                         [("htop", "x86_64"), ("neohtop", "x86_64")])
        self.assertEqual(results[0].status, PackageStatus.INSTALLED)
        self.assertEqual(results[0].version, "3.4.1-3.fc44")
        self.assertEqual(results[1].status, PackageStatus.AVAILABLE)
        self.assertEqual(results[1].summary, "System monitoring on steroids")
        self.assertEqual((results[1].version, results[1].repo), ("1.2.0-1.fc44", "updates"))

    def test_dnf4_format(self):
        results = self._search(DNF4_SEARCH)
        self.assertEqual([p.name for p in results], ["htop", "pcp-htop"])

    def test_rejects_short_and_option_like_queries(self):
        backend = make_backend()
        with patch.object(DNFBackend, "_run") as run:
            self.assertEqual(backend.search("h"), [])
            self.assertEqual(backend.search("--help"), [])
        run.assert_not_called()


class TestCheckUpdates(unittest.TestCase):
    def test_installed_versions_newest_wins_and_missing_ignored(self):
        out = ("kernel-core 7.2.5-200.fc44\nkernel-core 7.2.6-200.fc44\n"
               "package nope is not installed\n")
        with patch("dnf_gui.core.dnf_backend.subprocess.run",
                   return_value=MagicMock(stdout=out)):
            versions = make_backend()._installed_versions(["kernel-core", "nope"])
        self.assertEqual(versions, {"kernel-core": "7.2.6-200.fc44"})

    def test_fills_installed_version(self):
        proc = MagicMock(returncode=100, stdout="firefox.x86_64 146.0-1.fc44 updates\n")
        with patch("dnf_gui.core.dnf_backend.subprocess.run", return_value=proc), \
             patch.object(DNFBackend, "_installed_versions",
                          return_value={"firefox": "145.0-1.fc44"}):
            info = make_backend().check_updates()
        self.assertFalse(info.check_failed)
        self.assertEqual(info.packages[0].installed_version, "145.0-1.fc44")

    def test_dnf_error_exit_marks_check_failed(self):
        with patch("dnf_gui.core.dnf_backend.subprocess.run",
                   return_value=MagicMock(returncode=1, stdout="")):
            self.assertTrue(make_backend().check_updates().check_failed)

    def test_unneeded_packages_sorted_and_unique(self):
        with patch.object(DNFBackend, "_run", return_value="b-1-1\na-2-1\nb-1-1\n"):
            self.assertEqual(make_backend().unneeded_packages(), ["a-2-1", "b-1-1"])


# stdout only: dnf5 prints its "Updating and loading repositories" to stderr.
DNF5_REPOQUERY = (
    "assimp 6.0.6-1.fc45 x86_64 2652538\n"
    "criu 4.3.1-1.fc45 x86_64 685489\n"
    "kernel-core 7.3.4-300.fc45 x86_64 22152541\n")


class TestUpgradePreview(unittest.TestCase):
    def _preview(self, output, **kwargs):
        backend = make_backend()
        seen = {}

        def fake_run(cmd, allow_nonzero=False):
            seen["cmd"] = cmd
            return output
        with patch.object(DNFBackend, "_run", side_effect=fake_run):
            return backend.get_upgrade_preview(**kwargs), seen.get("cmd")

    def test_parses_rows_and_sums_sizes(self):
        preview, cmd = self._preview(DNF5_REPOQUERY)
        # dnf5 doesn't end each package with a newline unless asked.
        self.assertTrue(cmd[cmd.index("--queryformat") + 1].endswith("\n"))
        self.assertEqual(preview.count, 3)
        self.assertEqual(preview.total_bytes, 2652538 + 685489 + 22152541)
        self.assertTrue(preview.sizes_known)
        self.assertTrue(preview.has_preview)

    def test_security_flag_passes_through(self):
        _, cmd = self._preview("", security_only=True)
        self.assertIn("--security", cmd)
        self.assertIn("--upgrades", cmd)

    def test_tolerates_garbage_and_unknown_sizes(self):
        preview, _ = self._preview("Last metadata expiration check...\n"
                                   "firefox 125.0-1.fc44 x86_64 %{downloadsize}\n"
                                   "broken-line\n"
                                   "bash 5.2-1.fc44 x86_64 1024\n")
        self.assertEqual(preview.count, 2)  # firefox + bash counted
        self.assertEqual(preview.total_bytes, 1024)
        self.assertTrue(preview.sizes_known)

    def test_empty_on_backend_failure(self):
        preview, _ = self._preview(None)
        self.assertFalse(preview.has_preview)
        self.assertEqual((preview.count, preview.total_bytes), (0, 0))
