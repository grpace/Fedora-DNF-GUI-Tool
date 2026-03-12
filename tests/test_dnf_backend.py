"""Tests for the DNF backend module."""

import unittest
from unittest.mock import patch, MagicMock

from src.dnf_gui.core.package import Package, PackageStatus, UpdateInfo
from src.dnf_gui.core.dnf_backend import DNFBackend


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

    def test_display_name(self):
        """Test the display_name property."""
        pkg = Package(name="my-cool-package", version="1.0")
        self.assertEqual(pkg.display_name, "My Cool Package")


class TestDNFBackend(unittest.TestCase):
    """Tests for the DNF backend."""

    def setUp(self):
        self.backend = DNFBackend()

    @patch("src.dnf_gui.core.dnf_backend.subprocess.run")
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

    @patch("src.dnf_gui.core.dnf_backend.subprocess.run")
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


if __name__ == "__main__":
    unittest.main()
