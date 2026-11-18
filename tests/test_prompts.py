"""The async prompt queue: one prompt at a time, safe defaults, and the
conftest ``answer()`` helper the other tests use."""

from dnf_gui.ui.controllers.prompts import NO, YES, Prompts
from tests.conftest import answer

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


def test_conftest_answer_scripts_the_replies(app):
    ran = []
    shown = answer(app, "yes")
    app.prompts.confirm("Go?", "Go now?", lambda: ran.append("first"))
    # Out of scripted answers: the prompt's default (No, when destructive).
    app.prompts.confirm("Remove?", "Remove it?", lambda: ran.append("second"), destructive=True)
    assert ran == ["first"]
    assert [p.title for p in shown] == ["Go?", "Remove?"]
