"""The async prompt queue and the operation runner's progress/log logic."""

import time

from PyQt6.QtWidgets import QApplication

from dnf_gui.ui.controllers.prompts import NO, YES, Prompts
from dnf_gui.ui.controllers.runner import MAX_LOG_LINES, LogModel, parse_step


# ── prompts ──────────────────────────────────────────────────────────

def test_one_prompt_at_a_time_in_order():
    prompts = Prompts()
    ran = []
    prompts.confirm("First", "1?", lambda: ran.append("first"))
    prompts.confirm("Second", "2?", lambda: ran.append("second"))
    assert prompts.current["title"] == "First"
    prompts.reply(prompts.current["token"], YES)
    assert prompts.current["title"] == "Second"
    prompts.reply(prompts.current["token"], NO)
    assert ran == ["first"] and not prompts.active


def test_stale_or_repeated_reply_runs_nothing():
    prompts = Prompts()
    ran = []
    prompts.confirm("Remove?", "Remove it?", lambda: ran.append(1))
    token = prompts.current["token"]
    prompts.reply(token + 99, YES)   # not the current prompt
    assert ran == [] and prompts.active
    prompts.reply(token, YES)
    prompts.reply(token, YES)        # double click / late repeat
    assert ran == [1]


def test_destructive_defaults_to_no_and_unknown_choice_uses_default():
    prompts = Prompts()
    ran = []
    prompts.confirm("Force?", "Force it?", lambda: ran.append(1), destructive=True)
    current = prompts.current
    assert current["defaultChoice"] == NO and current["destructive"]
    prompts.reply(current["token"], "something-else")
    assert ran == []


def test_cancel_all_answers_safely():
    prompts = Prompts()
    ran, declined = [], []
    prompts.confirm("Upgrade?", "Go?", lambda: ran.append(1),
                    on_no=lambda: declined.append(1), default_yes=True)
    prompts.choose("Pick", "Which?", [("force", "Force"), ("ok", "OK")],
                   lambda c: ran.append(c), default="ok")
    prompts.cancel_all()
    assert ran == ["ok"] and declined == [1] and not prompts.active


def test_prompt_shown_while_another_is_open_waits_its_turn():
    """A worker finishing while a prompt is open queues its prompt; it
    never replaces or answers the open one."""
    prompts = Prompts()
    ran = []
    prompts.confirm("Upgrade All?", "Go?", lambda: ran.append("upgrade"))
    prompts.inform("Nothing to Clean Up", "No unneeded packages.")
    assert prompts.current["title"] == "Upgrade All?"
    prompts.reply(prompts.current["token"], YES)
    assert ran == ["upgrade"]
    assert prompts.current["title"] == "Nothing to Clean Up"


# ── runner helpers ───────────────────────────────────────────────────

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


def test_runner_streams_progress_and_finishes(monkeypatch):
    from dnf_gui.ui.controllers.app_controller import AppController
    controller = AppController()
    runner = controller.runner
    finished = []
    runner.finished.connect(lambda code, op, chain: finished.append((code, op, chain)))
    assert runner.run(["printf", "[1/2] a-1.0  100%% | x\\n[2/2] b-1.0  100%% | y\\n"], "Demo")
    assert runner.busy
    deadline = time.monotonic() + 5
    while not finished and time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.02)
    assert finished == [(0, "Demo", False)]
    assert runner.status == "succeeded" and not runner.busy
    assert runner.progress == 1.0
    assert "[2/2] b-1.0  100% | y" in runner.output


def test_second_operation_is_rejected_while_one_runs():
    from tests.conftest import answer
    from dnf_gui.ui.controllers.app_controller import AppController
    controller = AppController()
    shown = answer(controller)
    assert controller.runner.run(["sleep", "5"], "Long")
    assert not controller.runner.run(["true"], "Other")
    assert shown[-1].title == "Operation in Progress"
    controller.runner.cancel()
    deadline = time.monotonic() + 5
    while controller.runner.busy and time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.02)
    assert controller.runner.status == "cancelled"


def test_dnf5_history_action_letters_become_words():
    from dnf_gui.ui.controllers.pages import describe_actions
    assert describe_actions("E, I, U") == "Removed, Install, Upgrade"
    assert describe_actions("U") == "Upgrade"
    assert describe_actions("Upgrade") == "Upgrade"   # dnf4 words unchanged
    assert describe_actions("") == ""
