"""Tests for the scoped passwordless-updates privilege module."""

import shutil
import unittest

from dnf_gui.core import passwordless as pw


class TestCoverageMatching(unittest.TestCase):
    def test_updates_scope_covers_upgrade(self):
        self.assertTrue(pw.is_covered(
            ["pkexec", "/usr/bin/dnf5", "upgrade", "-y", "--refresh"], "updates"))
        self.assertTrue(pw.is_covered(
            ["pkexec", "/usr/bin/dnf", "update", "-y"], "updates"))
        self.assertTrue(pw.is_covered(
            ["pkexec", "/usr/bin/dnf", "upgrade", "--security"], "updates"))

    def test_updates_scope_rejects_risky_verbs(self):
        for verb in ("install", "remove", "autoremove", "distro-sync",
                     "group", "config-manager", "copr", "history", "clean"):
            self.assertFalse(
                pw.is_covered(["pkexec", "/usr/bin/dnf5", verb, "-y", "x"], "updates"),
                f"verb {verb} must stay behind a password",
            )

    def test_bash_wrappers_never_covered(self):
        # Allowing passwordless bash-as-root would equal passwordless root.
        self.assertFalse(pw.is_covered(
            ["pkexec", "bash", "-c", "dnf upgrade -y"], "updates"))
        self.assertFalse(pw.is_covered(
            ["pkexec", "bash", "-c", "dnf upgrade -y"], "full"))

    def test_non_dnf_programs_rejected(self):
        self.assertFalse(pw.is_covered(
            ["pkexec", "fwupdmgr", "update", "-y"], "updates"))
        self.assertFalse(pw.is_covered(
            ["pkexec", "fwupdmgr", "update", "-y"], "full"))

    def test_off_scope_covers_nothing(self):
        self.assertFalse(pw.is_covered(
            ["pkexec", "/usr/bin/dnf5", "upgrade", "-y"], "off"))
        self.assertFalse(pw.is_covered(
            ["pkexec", "/usr/bin/dnf5", "upgrade", "-y"], "bogus"))

    def test_full_scope_covers_dnf_but_not_bash(self):
        self.assertTrue(pw.is_covered(
            ["pkexec", "/usr/bin/dnf5", "install", "-y", "foo"], "full"))
        self.assertTrue(pw.is_covered(
            ["pkexec", "/usr/bin/dnf", "remove", "-y", "foo"], "full"))


class TestRewrite(unittest.TestCase):
    def test_maybe_passwordless_rewrites_covered(self):
        cmd = ["pkexec", "/usr/bin/dnf5", "upgrade", "-y", "--refresh"]
        self.assertEqual(pw.maybe_passwordless(cmd, "updates"),
                         ["sudo", "-n", "/usr/bin/dnf5", "upgrade", "-y", "--refresh"])

    def test_maybe_passwordless_leaves_uncovered(self):
        cmd = ["pkexec", "/usr/bin/dnf5", "install", "-y", "foo"]
        self.assertEqual(pw.maybe_passwordless(cmd, "updates"), cmd)
        self.assertEqual(pw.maybe_passwordless(cmd, "off"), cmd)


class TestRuleContent(unittest.TestCase):
    def test_updates_rule_lists_upgrade_verbs(self):
        content = pw.build_rule_content("alice", "updates")
        self.assertIn("alice ALL=(root) NOPASSWD:", content)
        self.assertIn("/usr/bin/dnf5 upgrade *", content)
        self.assertIn("scope=updates", content)
        # Must not grant bare dnf or install
        self.assertNotIn("install", content)

    def test_full_rule_is_broad_but_dnf_only(self):
        content = pw.build_rule_content("alice", "full")
        self.assertIn("/usr/bin/dnf5 *", content)
        self.assertNotIn("bash", content)
        self.assertNotIn("fwupdmgr", content)

    def test_visudo_validation(self):
        if not shutil.which("visudo"):
            self.skipTest("visudo not available here")
        ok, msg = pw.validate_content(pw.build_rule_content("alice", "updates"))
        self.assertTrue(ok, msg)
        bad_ok, _ = pw.validate_content("this is not valid sudoers {{{")
        self.assertFalse(bad_ok)


class TestSudoListParsing(unittest.TestCase):
    def test_parses_updates_scope(self):
        out = ("User alice may run the following commands on host:\n"
               "    (root) NOPASSWD: /usr/bin/dnf upgrade *, /usr/bin/dnf update *, "
               "/usr/bin/dnf5 upgrade *, /usr/bin/dnf5 update *\n")
        self.assertEqual(pw.parse_sudo_list(out), "updates")

    def test_parses_full_scope(self):
        out = ("User alice may run the following commands on host:\n"
               "    (root) NOPASSWD: /usr/bin/dnf *, /usr/bin/dnf5 *\n")
        self.assertEqual(pw.parse_sudo_list(out), "full")

    def test_parses_off(self):
        self.assertEqual(pw.parse_sudo_list(""), "off")
        self.assertEqual(
            pw.parse_sudo_list("User alice may run nothing\n"), "off")


if __name__ == "__main__":
    unittest.main()
