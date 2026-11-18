"""Closing, quitting and restarting the app: an operation that is still
running keeps the app alive in the background (dnf writes to our pipe), and
shutting down never destroys a thread that is still running."""

import time
from unittest.mock import patch

import pytest
from PyQt6.QtCore import QThread
from PyQt6.QtWidgets import QApplication

from tests.conftest import answer


class _SlowThread(QThread):
    def run(self):
        time.sleep(1.0)


@pytest.fixture
def windowed(app):
    from PyQt6.QtGui import QWindow
    window = QWindow()
    app.set_window(window)
    window.show()
    app.window = window
    yield app
    window.hide()
    QApplication.instance().setQuitOnLastWindowClosed(True)


def _close_while_running(app, *choices):
    shown = answer(app, *choices)
    with patch.object(app.runner, "running", return_value=True):
        accepted = app.requestClose()
    return accepted, shown


class TestCloseDuringAnOperation:
    def test_close_hides_and_keeps_running(self, windowed):
        accepted, shown = _close_while_running(windowed, "yes")
        assert accepted is False
        assert shown[0].title == "Operation Still Running"
        assert not windowed.window.isVisible()
        assert not QApplication.instance().quitOnLastWindowClosed()
        # A failure brings the window back with the output.
        windowed._operation_finished(failed=True)
        assert windowed.window.isVisible()
        assert QApplication.instance().quitOnLastWindowClosed()
        assert windowed.activityExpanded

    def test_keep_open_keeps_the_window(self, windowed):
        accepted, _ = _close_while_running(windowed, "no")
        assert accepted is False
        assert windowed.window.isVisible()
        assert not windowed._quit_when_done

    def test_close_when_idle_is_allowed(self, windowed):
        shown = answer(windowed)
        with patch.object(windowed, "shutdown_threads") as shutdown:
            assert windowed.requestClose() is True
        shutdown.assert_called_once()
        assert shown == []

    def test_success_quits_once_done(self, windowed):
        _close_while_running(windowed, "yes")
        with patch.object(QApplication, "quit") as quit_app, \
                patch("dnf_gui.ui.controllers.app_controller.QTimer.singleShot",
                      side_effect=lambda ms, fn: fn()):
            windowed._operation_finished(failed=False)
        quit_app.assert_called_once()

    def test_background_success_notification_is_not_clickable(self, windowed):
        _close_while_running(windowed, "yes")
        with patch.object(windowed.notifier, "send") as notify:
            windowed._notify_if_unfocused(0, "System Upgrade")
        assert notify.call_args.args[0].clickable is False

    def test_no_rescan_when_quitting_after_a_background_update(self, app):
        app._quit_when_done = True
        with patch.object(app, "refreshCurrent") as refresh, patch.object(app, "_quit_now"):
            app._on_operation_finished(0, "System Upgrade", False)
        refresh.assert_not_called()

    def test_close_prompt_answered_after_the_operation_finished_quits(self, app):
        shown = answer(app)
        app.prompts.auto_answer = None        # leave the close prompt open
        app.runner._worker = type("W", (), {"isRunning": lambda self: True})()
        assert app.requestClose() is False
        assert app.requestClose() is False    # no duplicate prompt
        assert sum(p.title == "Operation Still Running" for p in shown) == 1
        app.runner._worker = None             # the operation ends meanwhile
        with patch.object(app, "_quit_now") as quit_now:
            app.prompts.reply(app.prompts.current["token"], "yes")
        quit_now.assert_called_once()
        assert not app._quit_when_done


def test_shutdown_drops_open_prompts_without_running_them(app):
    ran = []
    app.prompts.confirm("Keep?", "?", lambda: ran.append("yes"),
                        on_no=lambda: ran.append("no"))
    app._shutdown()
    assert ran == [] and not app.prompts.active


def test_detached_threads_survive_a_second_shutdown_call(app):
    thread = _SlowThread(app)
    thread.start()
    first = app.shutdown_threads(timeout_ms=10)
    second = app.shutdown_threads(timeout_ms=10)  # app.py calls it again
    assert thread in first and thread in second
    assert thread in app.detached_threads
    thread.wait(3000)


def test_relaunch_refuses_while_a_worker_runs(app):
    shown = answer(app)
    thread = _SlowThread(app)
    thread.start()
    with patch("os.execv") as execv, patch.object(QThread, "wait", lambda self, ms=0: False):
        app.relaunch()
    execv.assert_not_called()
    assert shown[-1].title == "Restart the App Yourself"
    assert app._reminder_timer.isActive()  # still fully working
    QThread.wait(thread, 3000)
