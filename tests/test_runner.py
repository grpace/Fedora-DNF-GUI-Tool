"""The operation runner: running a command and streaming its output,
progress, cancelling, one operation at a time, and the output log.

The passwordless sudo -n → pkexec fallback is in test_passwordless.py.
"""

from unittest.mock import patch

from tests.conftest import answer, wait_until
from dnf_gui.ui.controllers.runner import MAX_LOG_LINES, LogModel, parse_step


def test_runs_a_command_and_reports_its_exit_code(app):
    done = []
    app.runner._start(["echo", "hello_world"], done.append)
    assert wait_until(lambda: done)
    assert done == [0]
    assert "hello_world" in app.runner.text()


def test_missing_binary_finishes_through_the_done_path(app):
    done = []
    app.runner._start(["/nonexistent/binary-xyz"], done.append)
    assert wait_until(lambda: done)
    assert done == [-1]
    assert app.runner.worker is None


def test_streams_progress_and_finishes(app):
    runner = app.runner
    finished = []
    runner.finished.connect(lambda code, op, chain: finished.append((code, op, chain)))
    assert runner.run(["printf", "[1/2] a-1.0  100%% | x\\n[2/2] b-1.0  100%% | y\\n"], "Demo")
    assert runner.busy
    assert wait_until(lambda: finished)
    assert finished == [(0, "Demo", False)]
    assert runner.status == "succeeded" and not runner.busy
    assert runner.progress == 1.0
    assert "[2/2] b-1.0  100% | y" in runner.output


def test_cancel_stops_the_command(app):
    runner = app.runner
    runner.run(["sleep", "10"], "Test sleep cancellation")
    assert runner.busy and runner.cancellable  # the Cancel button is offered
    assert wait_until(lambda: runner.worker is not None and runner.worker._process is not None)
    runner.cancel()
    assert wait_until(lambda: runner.worker is None)
    assert "cancelled" in runner.text().lower()
    assert runner.status == "cancelled"
    assert not runner.busy


def test_cancel_goes_away_once_dnf_starts_the_transaction(app):
    finished = []
    app.runner.finished.connect(lambda *a: finished.append(a))
    assert app.runner.run(["sh", "-c", "echo Running transaction; sleep 1"], "Demo")
    assert wait_until(lambda: app.runner.cancellable is False and app.runner.busy)
    assert wait_until(lambda: finished)


def test_second_operation_is_refused_while_one_runs(app):
    shown = answer(app)
    assert app.runner.run(["sleep", "5"], "Long")
    first = app.runner.worker
    assert not app.runner.run(["true"], "Other")
    assert [p.title for p in shown] == ["Operation in Progress"]
    assert app.runner.worker is first
    app.runner.cancel()
    assert wait_until(lambda: not app.runner.busy)
    assert app.runner.status == "cancelled"


def test_app_download_counts_as_busy_and_cannot_be_cancelled(app):
    shown = answer(app)
    fake = type("W", (), {"isRunning": lambda self: True})()
    app.runner.start_external("Downloading app update", fake)
    assert app.runner.running() and app.runner.busy and not app.runner.cancellable
    assert not app.runner.run(["true"], "Other")
    assert shown[-1].title == "Operation in Progress"
    assert app.requestClose() is False  # asks instead of quitting mid-download


def test_failed_operation_opens_the_output(app):
    finished = []
    app.runner.finished.connect(lambda *a: finished.append(a))
    with patch.object(app, "refreshCurrent"):
        app.runner.run(["sh", "-c", "echo broken; exit 3"], "Demo")
        assert wait_until(lambda: finished)
    assert app.runner.status == "failed"
    assert app.activityExpanded and app.activityVisible


# ── helpers ──────────────────────────────────────────────────────────

def test_parse_dnf5_and_dnf4_progress_lines():
    assert parse_step("[ 3/12] firefox-0:146.0.1-1.fc45.x86_64   100% |  52.3 MiB/s |  68.2 MiB |  00m01s") \
        == ("firefox 146.0.1-1.fc45", 3, 12)
    assert parse_step("  Upgrading        : kernel-core-7.2.8-300.fc45.x86_64    4/20") \
        == ("Upgrading kernel-core 7.2.8-300.fc45", 4, 20)
    assert parse_step("Updating and loading repositories:") is None
    assert parse_step("[0/0]") is None


def test_log_model_is_capped():
    log = LogModel()
    log.append("\n".join(f"line {i}" for i in range(MAX_LOG_LINES + 50)))
    assert log.count == MAX_LOG_LINES
    assert log.text().split("\n")[0] == "line 50"
    log.clear()
    assert log.count == 0
