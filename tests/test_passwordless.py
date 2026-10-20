"""Tests for the scoped passwordless-updates privilege module."""

import shutil
import unittest

from dnf_gui.core import passwordless as pw


class TestCoverageMatching(unittest.TestCase):
    def test_updates_scope_covers_upgrade(self):
        self.assertTrue(pw.is_covered(
            ["pkexec", "/usr/bin/dnf5", "upgrade", "-y", "--refresh"], "updates"))
        self.assertTrue(pw.is_covered(
            ["pkexec", "/usr/bin/dnf", "upgrade", "-y", "--security"], "updates"))
        self.assertTrue(pw.is_covered(
            ["pkexec", "/usr/bin/dnf5", "upgrade", "-y", "--refresh",
             "--exclude=kernel*,mesa-*"], "updates"))

    def test_updates_scope_rejects_extra_upgrade_args(self):
        for extra in (["./evil.rpm"], ["--nogpgcheck"],
                      ["--refresh", "--setopt=pluginpath=/tmp"]):
            self.assertFalse(pw.is_covered(
                ["pkexec", "/usr/bin/dnf5", "upgrade", "-y"] + extra, "updates"))
        self.assertFalse(pw.is_covered(
            ["pkexec", "/usr/bin/dnf5", "upgrade", "-y", "--refresh",
             "--exclude=x", "./evil.rpm"], "updates"))

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
    def test_updates_rule_lists_exact_commands(self):
        content = pw.build_rule_content("alice", "updates")
        self.assertIn("alice ALL=(root) NOPASSWD:", content)
        self.assertIn("/usr/bin/dnf5 upgrade -y --refresh,", content)
        self.assertIn("/usr/bin/dnf5 upgrade -y --security", content)
        self.assertIn("scope=updates", content)
        # Must not grant bare dnf, install, or any unescaped wildcard
        self.assertNotIn("install", content)
        rule = content.splitlines()[-1]
        self.assertNotIn(" *", rule)

    def test_updates_rule_escapes_held_back_globs(self):
        content = pw.build_rule_content("alice", "updates", ["kernel*", "mesa-*"])
        self.assertIn(
            r"/usr/bin/dnf5 upgrade -y --refresh --exclude\=kernel\*\,mesa-\*",
            content)

    def test_escaped_rule_matches_only_literal_argument(self):
        # sudo matches args with libc fnmatch after its parser strips the
        # escapes for , : = — emulate that and check wildcards stay literal.
        import ctypes
        import ctypes.util
        libc = ctypes.CDLL(ctypes.util.find_library("c"))
        arg = "--exclude=kernel*,mesa-*"
        pattern = pw._sudoers_escape(arg)
        for ch in ",:=":
            pattern = pattern.replace("\\" + ch, ch)
        self.assertEqual(libc.fnmatch(pattern.encode(), arg.encode(), 0), 0)
        self.assertNotEqual(libc.fnmatch(
            pattern.encode(),
            b"--exclude=kernel --nogpgcheck ./evil.rpm,mesa-*", 0), 0)

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
        ok, msg = pw.validate_content(pw.build_rule_content(
            "alice", "updates", ["kernel*", "*nvidia*", "[ab]c?"]))
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

    def test_detects_legacy_wildcard_rule(self):
        legacy = "    (root) NOPASSWD: /usr/bin/dnf5 upgrade *, /usr/bin/dnf5 update *\n"
        self.assertTrue(pw.has_legacy_wildcard_rule(legacy))
        exact = ("    (root) NOPASSWD: /usr/bin/dnf5 upgrade -y --refresh, "
                 "/usr/bin/dnf5 upgrade -y --refresh --exclude\\=kernel\\*\n")
        self.assertFalse(pw.has_legacy_wildcard_rule(exact))
        self.assertEqual(pw.parse_sudo_list(exact), "updates")

    def test_parses_off(self):
        self.assertEqual(pw.parse_sudo_list(""), "off")
        self.assertEqual(
            pw.parse_sudo_list("User alice may run nothing\n"), "off")


if __name__ == "__main__":
    unittest.main()
