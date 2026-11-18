"""The passwordless "updates" rule must cover the commands the app really runs.

``UPDATE_ARGVS`` in ``core/passwordless.py`` is a hand-written copy of the
upgrade commands' flags. These tests build the commands with the real
builders, so changing a flag in one place without the other fails here
instead of silently bringing back the password prompt.
"""

import unittest
from unittest.mock import patch

from dnf_gui.core import passwordless as pw
from dnf_gui.core.dnf_backend import DEFAULT_HELD_BACK_PATTERNS, DNFBackend
from dnf_gui.core.security import (
    build_forced_security_update_command, build_security_update_command,
)

DNF_BINARIES = ("/usr/bin/dnf5", "/usr/bin/dnf")


def _backend(dnf_path: str) -> DNFBackend:
    backend = DNFBackend.__new__(DNFBackend)
    backend._dnf_path = dnf_path
    return backend


def _rule_lines(scope: str, held_back=()) -> list[str]:
    return pw._rule_commands(scope, list(held_back))


def _as_rule_line(cmd: list[str]) -> str:
    """How sudoers would list ``cmd`` (pkexec dropped, args escaped)."""
    return " ".join([cmd[1]] + [pw._sudoers_escape(a) for a in cmd[2:]])


class TestRealBuildersAreCovered(unittest.TestCase):
    def test_upgrade_all_is_covered_and_listed(self):
        for path in DNF_BINARIES:
            cmd = _backend(path).build_upgrade_command()
            self.assertTrue(pw.is_covered(cmd, pw.SCOPE_UPDATES), cmd)
            self.assertIn(_as_rule_line(cmd), _rule_lines(pw.SCOPE_UPDATES))
            self.assertEqual(pw.maybe_passwordless(cmd, pw.SCOPE_UPDATES),
                             ["/usr/bin/sudo", "-n"] + cmd[1:])

    def test_security_only_is_covered_and_listed(self):
        for path in DNF_BINARIES:
            with patch("dnf_gui.core.security.system_binary", return_value=path):
                cmd = build_security_update_command()
            self.assertEqual(cmd[1], path)
            self.assertTrue(pw.is_covered(cmd, pw.SCOPE_UPDATES), cmd)
            self.assertIn(_as_rule_line(cmd), _rule_lines(pw.SCOPE_UPDATES))

    def test_update_without_major_is_covered_and_listed(self):
        patterns = list(DEFAULT_HELD_BACK_PATTERNS)
        for path in DNF_BINARIES:
            cmd = _backend(path).build_upgrade_without_major_command(patterns)
            self.assertTrue(pw.is_covered(cmd, pw.SCOPE_UPDATES), cmd)
            self.assertIn(_as_rule_line(cmd),
                          _rule_lines(pw.SCOPE_UPDATES, patterns))

    def test_package_changing_commands_are_not_covered(self):
        backend = _backend("/usr/bin/dnf5")
        for cmd in (build_forced_security_update_command(),
                    backend.build_install_command("htop"),
                    backend.build_remove_command("htop"),
                    backend.build_upgrade_package_command("htop"),
                    backend.build_autoremove_command()):
            self.assertFalse(pw.is_covered(cmd, pw.SCOPE_UPDATES), cmd)
            self.assertEqual(pw.maybe_passwordless(cmd, pw.SCOPE_UPDATES), cmd)
