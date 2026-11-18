"""Desktop notifications: when an operation's result is sent, where a
click leads, the notify-send fallback, and launching the app from a
reminder."""

import os
from unittest.mock import MagicMock, patch

import pytest

from dnf_gui.core import notifications


# ── operation results ────────────────────────────────────────────────

def test_sent_only_when_the_window_is_not_focused(app):
    with patch.object(app.notifier, "send") as notify, \
            patch.object(app, "_window_active", return_value=True):
        app._notify_if_unfocused(0, "System Upgrade")
    notify.assert_not_called()
    with patch.object(app.notifier, "send") as notify, \
            patch.object(app, "_window_active", return_value=False):
        app._notify_if_unfocused(1, "System Upgrade")
    sent = notify.call_args.args[0]
    assert sent.title == "System Upgrade"
    assert "Failed" in sent.body
    assert sent.page == "terminal"  # a click shows the output
    assert ("terminal", "Show Output") in sent.actions


def test_success_just_raises_the_window(app):
    with patch.object(app.notifier, "send") as notify, \
            patch.object(app, "_window_active", return_value=False):
        app._notify_if_unfocused(0, "System Upgrade")
    sent = notify.call_args.args[0]
    assert sent.page == ""
    assert sent.urgency == "normal"


# ── clicks ───────────────────────────────────────────────────────────

class TestNotifier:
    """Clicks are routed to the page the notification names."""

    @pytest.fixture(autouse=True)
    def notifier(self):
        self.notifier = notifications.Notifier()
        self.notifier._pages[7] = "updates"
        self.events = []
        self.notifier.activated.connect(lambda p, t: self.events.append((p, t)))
        self.notifier.closed.connect(lambda nid: self.events.append(nid))

    def _signal(self, member, *args):
        msg = MagicMock()
        msg.member.return_value = member
        msg.arguments.return_value = list(args)
        self.notifier._on_signal(msg)

    def test_body_click_opens_the_notifications_page(self):
        self._signal("ActivationToken", 7, "token-1")
        self._signal("ActionInvoked", 7, "default")
        assert self.events == [("updates", "token-1")]

    def test_button_names_its_page(self):
        self._signal("ActionInvoked", 7, "terminal")
        assert self.events == [("terminal", "")]

    def test_ignores_other_apps_notifications(self):
        self._signal("ActionInvoked", 99, "default")
        self._signal("NotificationClosed", 99, 2)
        assert self.events == []

    def test_closed(self):
        self._signal("NotificationClosed", 7, 2)
        assert self.events == [7]
        assert 7 not in self.notifier._pages

    def test_default_action_comes_first(self):
        n = notifications.Notification("T", actions=[("updates", "View Updates")])
        assert n.action_list() == ["default", "Open", "updates", "View Updates"]

    def test_falls_back_to_notify_send(self):
        n = notifications.Notification("Title", "-Body")
        with patch.object(notifications, "_notify_send", return_value=True):
            assert self.notifier.send(n) == notifications.UNTRACKED
        with patch.object(notifications, "_notify_send", return_value=False):
            assert self.notifier.send(n) == 0
        cmd = notifications.notify_send_command(n)
        assert cmd[0] == "notify-send"
        assert "--icon=dnf-gui" in cmd
        assert cmd[-3:] == ["--", "Title", "-Body"]  # never read as options


# ── launching the app from a reminder ────────────────────────────────

def test_service_starts_the_app_in_its_own_unit():
    with patch.dict(os.environ, {"INVOCATION_ID": "abc"}), \
            patch("dnf_gui.core.paths.find_system_binary", return_value="/usr/bin/dnf-gui"), \
            patch("subprocess.run", return_value=MagicMock(returncode=0)) as run, \
            patch("subprocess.Popen") as popen:
        assert notifications.launch_app("updates", "tok")
    cmd = run.call_args.args[0]
    assert cmd[:2] == ["systemd-run", "--user"]
    assert "--setenv=XDG_ACTIVATION_TOKEN=tok" in cmd
    assert cmd[-3:] == ["/usr/bin/dnf-gui", "--page", "updates"]
    popen.assert_not_called()


def test_outside_systemd_the_app_is_spawned_directly(monkeypatch):
    monkeypatch.delenv("INVOCATION_ID", raising=False)
    with patch("dnf_gui.core.paths.find_system_binary", return_value="/usr/bin/dnf-gui"), \
            patch("subprocess.Popen") as popen:
        assert notifications.launch_app("updates")
    assert popen.call_args.args[0] == ["/usr/bin/dnf-gui", "--page", "updates"]
    assert popen.call_args.kwargs["start_new_session"]
