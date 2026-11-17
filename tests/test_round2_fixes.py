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
