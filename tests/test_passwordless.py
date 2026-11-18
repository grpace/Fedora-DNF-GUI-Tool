"""Passwordless updates: which argv the sudoers rule covers, the rule's
text and how it's installed, the runner's sudo -n → pkexec fallback, the
password note in confirmations, and Settings' status line.

test_sudoers_sync.py checks that the rule lists the exact argv the real
command builders produce.
"""

import shutil
import unittest
from unittest.mock import patch

import pytest
from PyQt6.QtCore import QObject, pyqtSignal

from dnf_gui.core import passwordless as pw
from tests.conftest import answer


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
                         ["/usr/bin/sudo", "-n", "/usr/bin/dnf5", "upgrade", "-y", "--refresh"])

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
        libc = ctypes.CDLL(None)  # this process's libc
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

    def test_covers_held_back_needs_the_exact_list(self):
        out = ("    (root) NOPASSWD: /usr/bin/dnf5 upgrade -y --refresh, "
               "/usr/bin/dnf5 upgrade -y --refresh --exclude\\=kernel\\*\\,mesa-\\*, "
               "/usr/bin/dnf5 upgrade -y --security\n")
        self.assertTrue(pw.covers_held_back(out, ["kernel*", "mesa-*"]))
        self.assertFalse(pw.covers_held_back(out, ["kernel*"]))
        self.assertFalse(pw.covers_held_back(out, ["kernel*", "mesa-*", "firefox"]))
        self.assertTrue(pw.covers_held_back(out.replace("\\", ""), ["kernel*", "mesa-*"]))


# ── the rule's user and installation ─────────────────────────────────

def test_rule_user_comes_from_the_real_uid_and_must_be_safe(monkeypatch):
    import os
    import pwd
    monkeypatch.setenv("LOGNAME", "attacker\nALL ALL=(ALL) NOPASSWD: ALL")
    monkeypatch.setenv("USER", "attacker")
    monkeypatch.setenv("SUDO_USER", "attacker")
    assert pw.current_user() == pwd.getpwuid(os.getuid()).pw_name
    with pytest.raises(ValueError):
        pw.build_rule_content("me\nALL ALL=(ALL) NOPASSWD: ALL", "updates")
    with pytest.raises(ValueError):
        pw.build_rule_content("root", "updates")


def test_rule_is_checked_before_it_is_moved_into_place():
    script = pw.build_install_commands(pw.build_rule_content("me", "updates"))[3]
    tmp = pw.SUDOERS_FILE + ".tmp"
    assert script.index(f"cat > {tmp}") < script.index(f"visudo -c -f {tmp}") \
        < script.index(f"mv -f {tmp} {pw.SUDOERS_FILE}")
    assert f"cat > {pw.SUDOERS_FILE} " not in script  # never written in place
    assert f"mv -f {tmp} {pw.SUDOERS_FILE} || {{" in script  # a failed move fails


def test_uses_the_system_sudo_or_stays_on_pkexec():
    cmd = ["pkexec", "/usr/bin/dnf5", "upgrade", "-y", "--refresh"]
    with patch.object(pw, "find_system_binary", return_value="/usr/sbin/sudo"):
        assert pw.maybe_passwordless(cmd, "updates")[:2] == ["/usr/sbin/sudo", "-n"]
    with patch.object(pw, "find_system_binary", return_value=None):
        assert pw.maybe_passwordless(cmd, "updates") == cmd


# ── chains: only the covered step skips the password ──────────────────

def test_update_everything_runs_its_dnf_step_without_a_password(app):
    answer(app, "yes")
    with patch.object(app.runner, "run_chain") as chain:
        app.updates.update_everything()
    dnf_step, flatpak_step = chain.call_args.args[0]
    assert pw.is_covered(dnf_step, pw.SCOPE_UPDATES)
    assert pw.maybe_passwordless(dnf_step, pw.SCOPE_UPDATES)[:2] == ["/usr/bin/sudo", "-n"]
    assert pw.maybe_passwordless(flatpak_step, pw.SCOPE_UPDATES) == flatpak_step


def test_release_upgrade_updates_first_without_a_password(app):
    from dnf_gui.core import release_upgrade as ru
    answer(app, "yes")
    with patch.object(ru, "current_release", return_value=44), \
            patch.object(app.runner, "run_chain") as chain:
        app.updates.start_release_upgrade(45)
    update_step, download_step = chain.call_args.args[0]
    assert pw.is_covered(update_step, pw.SCOPE_UPDATES)
    # Downloading a new release always asks.
    assert not pw.is_covered(download_step, pw.SCOPE_UPDATES)


# ── Settings: turning it on and off ──────────────────────────────────

@pytest.fixture
def settings_app(app):
    # Never run the real `sudo -n -l` status probe.
    with patch.object(pw, "current_user", return_value="alice"), \
            patch.object(pw, "live_status", return_value=("off", False, True)):
        yield app


def _enable(app, scope, *choices, valid=True):
    shown = answer(app, *choices)
    with patch.object(pw, "validate_content",
                      return_value=(valid, "" if valid else "syntax error")) as check, \
            patch.object(app.runner, "run") as run:
        app.settings_controller.enablePasswordless(scope)
    return shown, check, run


class TestTurningItOn:
    def test_declined_runs_nothing(self, settings_app):
        shown, check, run = _enable(settings_app, "updates", "no")
        run.assert_not_called()
        check.assert_not_called()
        assert shown[0].title == "Turn On Passwordless Updates?"
        assert settings_app.settings.passwordless_scope == "off"

    def test_validation_failure_runs_nothing(self, settings_app):
        shown, check, run = _enable(settings_app, "updates", "yes", valid=False)
        check.assert_called_once()
        run.assert_not_called()
        assert shown[-1].title == "Validation Failed"
        assert settings_app.settings.passwordless_scope == "off"

    def test_installs_validated_rule_and_saves_scope_only_on_success(self, settings_app):
        app = settings_app
        _, check, run = _enable(app, "updates", "yes")
        content = pw.build_rule_content("alice", "updates", app.settings.held_back_patterns)
        check.assert_called_once_with(content)
        run.assert_called_once_with(pw.build_install_commands(content),
                                    "Enabling passwordless updates")
        # Nothing is remembered until the privileged step finishes.
        assert app.settings.passwordless_scope == "off"
        app._on_operation_finished(0, "Enabling passwordless updates", False)
        assert app.settings.passwordless_scope == "updates"

    def test_failed_install_keeps_scope_off(self, settings_app):
        _enable(settings_app, "full", "yes")
        settings_app._on_operation_finished(1, "Enabling passwordless updates", False)
        assert settings_app.settings.passwordless_scope == "off"

    def test_full_scope_warns_and_defaults_to_no(self, settings_app):
        shown, _, run = _enable(settings_app, "full", "no")
        assert shown[0].destructive and shown[0].default == "no"
        assert "removes every password prompt" in shown[0].text
        run.assert_not_called()

    def test_scope_untouched_when_the_runner_is_busy(self, settings_app):
        answer(settings_app, "yes")
        settings_app.settings_controller.pending_passwordless_scope = "updates"
        with patch.object(pw, "validate_content", return_value=(True, "")), \
                patch.object(settings_app.runner, "run", return_value=False):
            settings_app.settings_controller.enablePasswordless("full")
        assert settings_app.settings_controller.pending_passwordless_scope == "updates"

    def test_disable_removes_rule_and_turns_scope_off(self, settings_app):
        settings_app.settings.passwordless_scope = "updates"
        answer(settings_app, "yes")
        with patch.object(settings_app.runner, "run") as run:
            settings_app.settings_controller.disablePasswordless()
        run.assert_called_once_with(pw.build_remove_commands(),
                                    "Disabling passwordless updates")
        settings_app._on_operation_finished(0, "Disabling passwordless updates", False)
        assert settings_app.settings.passwordless_scope == "off"


@pytest.mark.parametrize("remembered, live, legacy, covered, level, title", [
    ("off", "off", False, True, "info", "Off"),
    ("updates", "updates", False, True, "positive", "On: Updates Only"),
    ("updates", "off", False, True, "warning", "Not Working"),
    # An old wildcard rule is a security warning even when it works.
    ("updates", "updates", True, True, "warning", None),
    ("updates", "updates", False, False, "warning", None),
    ("off", "full", False, True, None, None),
])
def test_status_line(app, remembered, live, legacy, covered, level, title):
    controller = app.settings_controller
    app.settings.passwordless_scope = remembered
    with patch.object(pw, "live_status", return_value=(live, legacy, covered)):
        controller.load_passwordless_status()
    if level:
        assert controller.passwordlessLevel == level
    if title:
        assert controller.passwordlessTitle == title
    if legacy:
        assert any("overly broad" in n for n in controller.passwordlessNotes)
    for text in [controller.passwordlessTitle, controller.passwordlessText,
                 *controller.passwordlessNotes]:
        assert "—" not in text


# ── the password note in confirmations ──────────────────────────────

def test_password_note_follows_the_rule_actually_installed(app):
    upgrade = app.backend.build_upgrade_command()
    without_core = app.backend.build_upgrade_without_major_command(["kernel*"])
    app.settings.passwordless_scope = "off"
    assert "asked for your password" in app.password_note(upgrade)
    app.settings.passwordless_scope = "updates"
    assert "No password needed" in app.password_note(upgrade)
    assert "asked for your password" in app.password_note(
        app.backend.build_install_command("x"))
    # The saved setting says yes, but the rule installed says no.
    with patch.object(type(app), "_live_passwordless", lambda self: ("off", True)):
        assert "asked for your password" in app.password_note(upgrade)
    # The installed rule lists other core patterns than the app's.
    with patch.object(type(app), "_live_passwordless", lambda self: ("updates", False)):
        assert "asked for your password" in app.password_note(without_core)
        assert "No password needed" in app.password_note(upgrade)


def test_live_rule_is_checked_again_after_the_core_list_changes(app):
    app._pw_cache = (1e18, ("full", True))
    app.settings_controller.toggle_hold("htop", True)
    assert app._pw_cache is None


# ── the runner: sudo -n, then pkexec once ────────────────────────────

class _FakeWorker(QObject):
    """Stands in for CommandWorker: records argv, finishes synchronously."""

    output_line = pyqtSignal(str)
    finished = pyqtSignal(int)
    error = pyqtSignal(str)
    started_argvs: list = []
    script = None  # argv -> (lines, exit code)

    def __init__(self, command, parent=None):
        super().__init__(parent)
        self._command = list(command)

    def isRunning(self):  # noqa: N802 - Qt API
        return False

    def start(self):
        _FakeWorker.started_argvs.append(self._command)
        lines, code = _FakeWorker.script(self._command)
        for line in lines:
            self.output_line.emit(line)
        self.finished.emit(code)


class TestRunnerFallback:
    """pkexec is swapped for sudo -n only for covered argv, and a sudo that
    still wants a password falls back to pkexec exactly once."""

    @pytest.fixture(autouse=True)
    def fake_worker(self, app):
        _FakeWorker.started_argvs = []
        self.app = app
        self.cmd = app.backend.build_upgrade_command()
        assert self.cmd[0] == "pkexec"
        # A successful "System Upgrade" rechecks the reboot notice.
        with patch("dnf_gui.ui.controllers.runner.CommandWorker", _FakeWorker), \
                patch.object(app.updates, "recheck_reboot"):
            yield

    def _run(self, scope, script, cmd=None):
        self.app.settings.passwordless_scope = scope
        _FakeWorker.script = staticmethod(script)
        finished = []
        self.app.runner.finished.connect(lambda *a: finished.append(a))
        self.app.runner.run(cmd or self.cmd, "System Upgrade")
        return finished

    def test_off_scope_uses_pkexec(self):
        self._run("off", lambda argv: ([], 0))
        assert _FakeWorker.started_argvs == [self.cmd]

    def test_covered_command_uses_sudo_n(self):
        finished = self._run("updates", lambda argv: ([], 0))
        assert _FakeWorker.started_argvs == [["/usr/bin/sudo", "-n"] + self.cmd[1:]]
        assert finished == [(0, "System Upgrade", False)]

    def test_sudo_password_prompt_retries_once_with_pkexec(self):
        def script(argv):
            if argv[0].endswith("/sudo"):
                return (["sudo: a password is required"], 1)
            return ([], 0)
        finished = self._run("updates", script)
        assert _FakeWorker.started_argvs == [["/usr/bin/sudo", "-n"] + self.cmd[1:], self.cmd]
        assert finished == [(0, "System Upgrade", False)]
        assert "falling back to password prompt" in self.app.runner.text()

    def test_pkexec_failure_after_fallback_is_not_retried_again(self):
        finished = self._run("updates", lambda argv: (["sudo: a password is required"], 1))
        assert len(_FakeWorker.started_argvs) == 2
        assert finished == [(1, "System Upgrade", False)]

    def test_other_sudo_failures_are_not_retried(self):
        finished = self._run("updates", lambda argv: (["Error: no space left"], 1))
        assert _FakeWorker.started_argvs == [["/usr/bin/sudo", "-n"] + self.cmd[1:]]
        assert finished == [(1, "System Upgrade", False)]

    def test_uncovered_command_keeps_pkexec(self):
        cmd = self.app.backend.build_install_command("htop")
        self._run("updates", lambda argv: ([], 0), cmd)
        assert _FakeWorker.started_argvs == [cmd]
