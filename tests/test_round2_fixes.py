"""Fixes from the second council review and the real-system end-to-end run."""

import time
from unittest.mock import patch

from PyQt6.QtCore import QThread
from PyQt6.QtWidgets import QApplication

from tests.conftest import answer
from dnf_gui.core.package import Package, PackageStatus, UpdateInfo


def _controller():
    import gc
    gc.collect()
    from dnf_gui.ui.controllers.app_controller import AppController
    return AppController()


def _wait(predicate, seconds=5.0):
    deadline = time.monotonic() + seconds
    while not predicate() and time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.02)
    return predicate()


# ── core: dnf5 preview and skipped updates ───────────────────────────

# stdout only: dnf5 prints its "Updating and loading repositories" to stderr.
DNF5_REPOQUERY = (
    "assimp 6.0.6-1.fc45 x86_64 2652538\n"
    "criu 4.3.1-1.fc45 x86_64 685489\n"
    "kernel-core 7.3.4-300.fc45 x86_64 22152541\n")

FFMPEG_SKIPPED = """\
Updating and loading repositories:
Repositories loaded.
Problem: package ffmpeg-9.0.2-4.fc45.x86_64 from rpmfusion-free-updates requires ffmpeg-libs(x86-64) = 9.0.2-4.fc45, but none of the providers can be installed
  - nothing provides liboapv.so.11()(64bit) needed by ffmpeg-libs-9.0.2-4.fc45.x86_64 from rpmfusion-free-updates

Package      Arch   Version      Repository                  Size
Skipping packages with broken dependencies:
 ffmpeg      x86_64 9.0.2-4.fc45 rpmfusion-free-updates   2.6 MiB
 ffmpeg-libs x86_64 9.0.2-4.fc45 rpmfusion-free-updates  23.9 MiB

Nothing to do.
"""


def test_preview_queryformat_ends_each_package_with_a_newline():
    from dnf_gui.core.dnf_backend import DNFBackend
    backend = DNFBackend.__new__(DNFBackend)
    backend._dnf_path = "/usr/bin/dnf5"
    seen = {}

    def fake_run(cmd, allow_nonzero=False):
        seen["cmd"] = cmd
        return DNF5_REPOQUERY
    backend._run = fake_run
    preview = backend.get_upgrade_preview()
    fmt = seen["cmd"][seen["cmd"].index("--queryformat") + 1]
    assert fmt.endswith("\n")  # dnf5 doesn't add one per package
    assert preview.count == 3
    assert preview.total_bytes == 2652538 + 685489 + 22152541


def test_broken_dependency_skips_are_reported():
    from dnf_gui.core.security import parse_blocked_updates, parse_unavailable_updates
    assert parse_blocked_updates(FFMPEG_SKIPPED) is None
    assert parse_unavailable_updates(FFMPEG_SKIPPED) == ["ffmpeg", "ffmpeg-libs"]

    c = _controller()
    c.runner._output = FFMPEG_SKIPPED.splitlines()
    c._on_operation_finished(0, "Update without Major", False)
    assert c.runner.statusText == "Completed · 2 Updates Skipped"
    assert "ffmpeg, ffmpeg-libs" in c.runner.text()


# ── lifecycle ────────────────────────────────────────────────────────

class _SlowThread(QThread):
    def run(self):
        time.sleep(1.0)


def test_detached_threads_survive_a_second_shutdown_call():
    c = _controller()
    thread = _SlowThread(c)
    thread.start()
    first = c.shutdown_threads(timeout_ms=10)
    second = c.shutdown_threads(timeout_ms=10)  # app.py calls it again
    assert thread in first and thread in second
    assert thread in c.detached_threads
    thread.wait(3000)


def test_close_prompt_answered_after_operation_finished_quits():
    c = _controller()
    shown = answer(c)  # leave the close prompt open
    c.prompts.auto_answer = None
    c.runner._worker = type("W", (), {"isRunning": lambda self: True})()
    assert c.requestClose() is False
    assert c.requestClose() is False      # no duplicate prompt
    assert sum(p.title == "Operation Still Running" for p in shown) == 1
    c.runner._worker = None               # the operation ends meanwhile
    with patch.object(c, "_quit_now") as quit_now:
        c.prompts.reply(c.prompts.current["token"], "yes")
    quit_now.assert_called_once()
    assert not c._quit_when_done


def test_shutdown_drops_open_prompts_without_running_them():
    c = _controller()
    ran = []
    c.prompts.confirm("Keep?", "?", lambda: ran.append("yes"),
                      on_no=lambda: ran.append("no"))
    c._shutdown()
    assert ran == [] and not c.prompts.active


def test_app_download_counts_as_busy_and_cannot_be_cancelled():
    c = _controller()
    shown = answer(c)
    fake = type("W", (), {"isRunning": lambda self: True})()
    c.runner.start_external("Downloading app update", fake)
    assert c.runner.running() and c.runner.busy and not c.runner.cancellable
    assert not c.runner.run(["true"], "Other")
    assert shown[-1].title == "Operation in Progress"
    assert c.requestClose() is False  # asks instead of quitting mid-download


def test_relaunch_refuses_while_a_worker_runs():
    c = _controller()
    shown = answer(c)
    thread = _SlowThread(c)
    thread.start()
    with patch("os.execv") as execv, patch.object(QThread, "wait", lambda self, ms=0: False):
        c.relaunch()
    execv.assert_not_called()
    assert shown[-1].title == "Restart the App Yourself"
    assert c._reminder_timer.isActive()  # still fully working
    QThread.wait(thread, 3000)


def test_no_rescan_after_installing_the_app_update():
    c = _controller()
    answer(c, "no")  # decline "Restart App"
    with patch.object(c, "refreshCurrent") as refresh:
        c._on_operation_finished(0, "Installing app update", False)
    refresh.assert_not_called()


def test_no_rescan_when_quitting_after_a_background_update():
    c = _controller()
    c._quit_when_done = True
    with patch.object(c, "refreshCurrent") as refresh, patch.object(c, "_quit_now"):
        c._on_operation_finished(0, "System Upgrade", False)
    refresh.assert_not_called()


def test_app_update_install_asks_first():
    c = _controller()
    shown = answer(c, "no")
    c._pending_update_info = type("U", (), {"latest_version": "2.0.1",
                                            "download_url": "https://x/y.rpm"})()
    with patch("dnf_gui.ui.controllers.app_controller.AppUpdateDownloadWorker") as worker:
        c.installAppUpdate()
    assert shown[-1].title == "Install Version 2.0.1?"
    worker.assert_not_called()


# ── controllers ──────────────────────────────────────────────────────

def _scan(c, reboot=True):
    pkg = Package("htop", "3.4.2", "1.fc45", "x86_64", "updates",
                  status=PackageStatus.UPDATE_AVAILABLE, installed_version="3.4.1-1.fc45")
    return {"dnf": UpdateInfo(1, [pkg]), "flatpak": [], "security": None,
            "reboot": reboot}


def test_reboot_later_lasts_until_the_next_real_scan():
    c = _controller()
    c.updates._on_checked(_scan(c))
    assert c.updates.rebootRequired
    c.updates.dismissReboot()
    c.updates.show()                      # cached revisit
    assert not c.updates.rebootRequired
    c.updates._on_checked(_scan(c))       # a fresh scan
    assert c.updates.rebootRequired


def test_password_note_matches_the_rule():
    c = _controller()
    cmd = c.backend.build_upgrade_command()
    c.settings.passwordless_scope = "off"
    assert "asked for your password" in c.password_note(cmd)
    c.settings.passwordless_scope = "updates"
    assert "No password needed" in c.password_note(cmd)
    assert "asked for your password" in c.password_note(c.backend.build_install_command("x"))


def test_passwordless_scope_untouched_when_the_runner_is_busy():
    c = _controller()
    answer(c, "yes")
    c.settings_controller.pending_passwordless_scope = "updates"
    with patch("dnf_gui.core.passwordless.current_user", return_value="me"), \
            patch("dnf_gui.core.passwordless.validate_content", return_value=(True, "")), \
            patch.object(c.runner, "run", return_value=False):
        c.settings_controller.enablePasswordless("full")
    assert c.settings_controller.pending_passwordless_scope == "updates"


def test_clean_up_runs_one_preview_at_a_time():
    c = _controller()
    running = type("W", (), {"isRunning": lambda self: True})()
    c.updates._autoremove_worker = running
    with patch("dnf_gui.ui.controllers.updates.CallWorker") as worker:
        c.updates.autoremove()
    worker.assert_not_called()


def test_flathub_search_error_is_shown():
    c = _controller()
    shown = answer(c)
    c.flatpak._search_generation = 3
    c.flatpak._on_search_error(3, "flatpak: network unreachable")
    assert shown[-1].title == "Flathub Search Failed"
    assert c.flatpak.searchDone and not c.flatpak.searching


def test_open_details_reload_after_an_operation():
    c = _controller()
    c.packages._details_name = "htop"
    with patch.object(c.packages, "loadDetails") as load:
        c._on_operation_finished(0, "Installing htop", False)
    load.assert_called_once_with("htop")


# ── hostile-critics security fixes ───────────────────────────────────

def test_privileged_binaries_never_come_from_path(monkeypatch, tmp_path):
    """A dnf planted earlier in $PATH (e.g. ~/.local/bin) is never used."""
    fake = tmp_path / "dnf5"
    fake.write_text("#!/bin/sh\n")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}:/usr/bin")
    from dnf_gui.core.dnf_backend import DNFBackend
    from dnf_gui.core.flatpak_backend import FlatpakBackend
    from dnf_gui.core.security import build_security_update_command
    assert DNFBackend().dnf_path.startswith(("/usr/", "/bin/"))
    assert build_security_update_command()[1].startswith(("/usr/", "/bin/"))
    assert FlatpakBackend()._flatpak.startswith(("/usr/", "/bin/"))


def test_sudoers_user_comes_from_the_real_uid_and_must_be_safe(monkeypatch):
    import pwd
    import pytest
    from dnf_gui.core import passwordless as pw
    monkeypatch.setenv("LOGNAME", "attacker\nALL ALL=(ALL) NOPASSWD: ALL")
    monkeypatch.setenv("USER", "attacker")
    monkeypatch.setenv("SUDO_USER", "attacker")
    assert pw.current_user() == pwd.getpwuid(__import__("os").getuid()).pw_name
    with pytest.raises(ValueError):
        pw.build_rule_content("me\nALL ALL=(ALL) NOPASSWD: ALL", "updates")
    with pytest.raises(ValueError):
        pw.build_rule_content("root", "updates")


def test_sudoers_rule_is_checked_before_it_is_moved_into_place():
    from dnf_gui.core import passwordless as pw
    script = pw.build_install_commands(pw.build_rule_content("me", "updates"))[3]
    tmp = pw.SUDOERS_FILE + ".tmp"
    assert script.index(f"cat > {tmp}") < script.index(f"visudo -c -f {tmp}") \
        < script.index(f"mv -f {tmp} {pw.SUDOERS_FILE}")
    assert f"cat > {pw.SUDOERS_FILE} " not in script  # never written in place


# ── hostile-critics UX fixes ─────────────────────────────────────────

def test_main_button_falls_back_when_the_favorite_has_nothing_to_do():
    from dnf_gui.core.flatpak_backend import FlatpakApp
    c = _controller()
    c.updates.setFavorite("all")
    c.updates._on_checked({"dnf": UpdateInfo(), "flatpak": [FlatpakApp("Kdenlive", "org.kde.kdenlive")],
                           "security": None})
    assert c.updates.mainMode == "everything"   # only Flatpak updates are waiting
    with patch.object(c.updates, "runMode") as run:
        c.updates.runFavorite()
    run.assert_called_once_with("everything")


def test_cancel_goes_away_once_dnf_starts_the_transaction():
    c = _controller()
    finished = []
    c.runner.finished.connect(lambda *a: finished.append(a))
    assert c.runner.run(["sh", "-c", "echo Running transaction; sleep 1"], "Demo")
    assert _wait(lambda: c.runner.cancellable is False and c.runner.busy)
    assert _wait(lambda: finished, 5)


def test_password_note_follows_the_rule_actually_installed():
    c = _controller()
    cmd = c.backend.build_upgrade_command()
    c.settings.passwordless_scope = "updates"       # saved setting says yes...
    with patch.object(type(c), "_live_passwordless", lambda self: ("off", True)):
        assert "asked for your password" in c.password_note(cmd)   # ...the rule says no
    minor = c.backend.build_upgrade_without_major_command(["kernel*"])
    with patch.object(type(c), "_live_passwordless", lambda self: ("updates", False)):
        assert "asked for your password" in c.password_note(minor)  # stale major list
        assert "No password needed" in c.password_note(cmd)


def test_app_update_install_needs_a_digest():
    c = _controller()
    info = type("U", (), {"latest_version": "2.0.1", "download_url": "https://x/y.rpm",
                          "release_url": "", "release_notes": "", "sha256": ""})()
    c._on_app_update_checked(info)
    assert c.appUpdate["available"] and not c.appUpdate["canInstall"]
    info.sha256 = "ab" * 32
    c._on_app_update_checked(info)
    assert c.appUpdate["canInstall"]


def test_failed_reboot_check_says_a_restart_may_be_needed():
    c = _controller()
    c.updates.set_reboot_required(True, certain=False)
    assert c.updates.rebootRequired and not c.updates.rebootCertain


def test_firmware_update_is_confirmed_as_destructive():
    c = _controller()
    shown = answer(c, "no")
    c.system.runTool("firmware_update")
    assert shown[-1].destructive and "BIOS/UEFI" in shown[-1].text


# ── hostile-critics follow-up ────────────────────────────────────────

def _run_verified_script(tmp_path, content: bytes, digest: str, dnf: str = "/usr/bin/dnf5"):
    """Run the root-side install script as this user, without pkexec; the
    refusal paths exit before dnf would run."""
    import subprocess
    import sys
    from dnf_gui.core.updater import VERIFIED_INSTALL_SCRIPT
    rpm = tmp_path / "update.rpm"
    rpm.write_bytes(content)
    return subprocess.run([sys.executable, "-I", "-c", VERIFIED_INSTALL_SCRIPT,
                           str(rpm), digest, dnf], capture_output=True, text=True)


def test_self_update_is_rechecked_as_root_and_refuses_a_swapped_file(tmp_path):
    import hashlib
    from dnf_gui.core.updater import build_verified_install_command
    good = hashlib.sha256(b"the real rpm").hexdigest()
    argv = build_verified_install_command("/tmp/x.rpm", good, "/usr/bin/dnf5")
    assert argv[:4] == ["pkexec", "/usr/bin/python3", "-I", "-c"]
    assert argv[-3:] == ["/tmp/x.rpm", good, "/usr/bin/dnf5"]   # data, never shell text
    swapped = _run_verified_script(tmp_path, b"something else", good)
    assert swapped.returncode == 3 and "changed after it was checked" in swapped.stdout
    assert _run_verified_script(tmp_path, b"x", "", "/usr/bin/dnf5").returncode == 2
    assert _run_verified_script(tmp_path, b"x", good, "/home/me/.local/bin/dnf").returncode == 2


def test_inconclusive_reboot_check_says_a_restart_may_be_needed():
    from dnf_gui.core.dnf_backend import DNFBackend
    backend = DNFBackend.__new__(DNFBackend)
    backend._dnf_path = "/usr/bin/dnf5"
    with patch("subprocess.run", side_effect=FileNotFoundError), \
            patch("os.path.exists", return_value=False):
        assert backend.check_reboot() is None
        assert backend.reboot_required() is False   # old callers unchanged
    c = _controller()
    c.updates._on_reboot_checked(None)
    assert c.updates.rebootRequired and not c.updates.rebootCertain


def test_update_everything_defaults_to_cancel():
    c = _controller()
    shown = answer(c, "no")
    c.updates.update_everything()
    assert shown[-1].default == "no"


def test_passwordless_uses_the_system_sudo_or_stays_on_pkexec():
    from dnf_gui.core import passwordless as pw
    cmd = ["pkexec", "/usr/bin/dnf5", "upgrade", "-y", "--refresh"]
    with patch("dnf_gui.core.passwordless.find_system_binary", return_value="/usr/bin/sudo"):
        assert pw.maybe_passwordless(cmd, "updates")[0] == "/usr/bin/sudo"
    with patch("dnf_gui.core.passwordless.find_system_binary", return_value=None):
        assert pw.maybe_passwordless(cmd, "updates") == cmd


def test_failed_move_fails_the_sudoers_install():
    from dnf_gui.core import passwordless as pw
    script = pw.build_install_commands(pw.build_rule_content("me", "updates"))[3]
    assert f"mv -f {pw.SUDOERS_FILE}.tmp {pw.SUDOERS_FILE} || {{" in script


def test_live_rule_is_checked_again_after_it_changes():
    c = _controller()
    c._pw_cache = (1e18, ("full", True))
    c.settings_controller.toggle_hold("htop", True)
    assert c._pw_cache is None


def test_flatpak_update_pill_matches_app_id_and_branch():
    from dnf_gui.core.flatpak_backend import FlatpakApp
    c = _controller()
    c.updates._on_checked({"dnf": UpdateInfo(), "security": None, "flatpak": [
        FlatpakApp("KDE Application Platform", "org.kde.Platform", "", "6.9")]})
    assert c.updates.flatpakHasUpdate("org.kde.Platform", "6.9")
    assert not c.updates.flatpakHasUpdate("org.kde.Platform", "6.8")
    assert not c.updates.flatpakHasUpdate("org.kde.Sdk", "6.9")


# ── security critic, second follow-up ────────────────────────────────

def test_rescan_that_cannot_tell_keeps_the_may_need_restart_banner():
    """After an update the reboot check says "maybe"; the rescan the same
    update starts must not clear it when it can't tell either."""
    c = _controller()
    c.updates._on_reboot_checked(None)
    c.updates._on_checked(_scan(c, reboot=None))
    assert c.updates.rebootRequired and not c.updates.rebootCertain
    c.updates._on_checked(_scan(c, reboot=False))   # a conclusive answer wins
    assert not c.updates.rebootRequired
    c.updates._on_checked(_scan(c, reboot=True))
    assert c.updates.rebootRequired and c.updates.rebootCertain


def test_combined_scan_reports_an_inconclusive_reboot_check_as_none():
    import inspect
    from dnf_gui.core import worker
    source = inspect.getsource(worker.CombinedUpdateCheckWorker)
    assert "check_reboot()" in source and "reboot_required()" not in source


def test_root_copy_refuses_symlinks_devices_fifos_and_huge_files(tmp_path):
    import hashlib
    import os
    import subprocess
    import sys
    from dnf_gui.core.updater import VERIFIED_INSTALL_SCRIPT
    digest = hashlib.sha256(b"x").hexdigest()

    def run(path):
        return subprocess.run([sys.executable, "-I", "-c", VERIFIED_INSTALL_SCRIPT,
                               str(path), digest, "/usr/bin/dnf5"],
                              capture_output=True, text=True, timeout=20)

    real = tmp_path / "real.rpm"
    real.write_bytes(b"x")
    link = tmp_path / "link.rpm"
    link.symlink_to(real)                       # even to a matching file
    dev = tmp_path / "zero.rpm"
    dev.symlink_to("/dev/zero")
    fifo = tmp_path / "fifo.rpm"
    os.mkfifo(fifo)
    huge = tmp_path / "huge.rpm"
    with open(huge, "wb") as f:
        f.truncate(101 * 1024 * 1024)           # sparse: costs no disk
    for path in (link, dev, fifo, huge, tmp_path / "missing.rpm"):
        result = run(path)
        assert result.returncode == 3, (path, result.stdout, result.stderr)
        assert "Refusing" in result.stdout
