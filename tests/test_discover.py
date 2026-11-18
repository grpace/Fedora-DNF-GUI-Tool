"""Taking over from KDE Discover: the commands that turn its updates off
(for this user or system-wide) and back on, Discover's own restart update,
and how Settings describes the current state."""

import subprocess
import unittest
from unittest.mock import patch

import pytest

from dnf_gui.core import discover_manager as dm
from dnf_gui.core.discover_manager import DiscoverManager, DiscoverStatus
from tests.conftest import answer


class TestDiscoverManager(unittest.TestCase):
    def setUp(self):
        self.mgr = DiscoverManager()

    def test_system_commands_use_pkexec(self):
        for cmd in self.mgr.build_system_disable_commands():
            self.assertIn("pkexec", cmd[0])
        for cmd in self.mgr.build_system_enable_commands():
            self.assertIn("pkexec", cmd[0])

    def test_kill_command_no_root(self):
        cmd = self.mgr.build_kill_notifier_command()
        self.assertNotIn("pkexec", cmd)
        self.assertIn("pkill", cmd)

    def test_remove_notifier_targets_split_package(self):
        cmd = self.mgr.build_remove_notifier_package_command()
        self.assertIn("plasma-discover-notifier", cmd)
        # Must NOT remove plasma-discover itself
        self.assertNotIn("plasma-discover ", " ".join(cmd).replace(
            "plasma-discover-notifier", ""))


class TestSystemWideDiscoverTakeover(unittest.TestCase):
    def setUp(self):
        self.mgr = DiscoverManager()

    def _script(self, cmds):
        self.assertEqual(len(cmds), 1)
        self.assertEqual(cmds[0][:3], ["pkexec", "bash", "-c"])
        check = subprocess.run(["bash", "-n", "-c", cmds[0][3]])
        self.assertEqual(check.returncode, 0, "generated script has a syntax error")
        return cmds[0][3]

    def test_disable_masks_unit_instead_of_deleting_package_file(self):
        script = self._script(self.mgr.build_system_disable_commands())
        self.assertIn(f"systemctl --global mask {dm.NOTIFIER_UNIT}", script)
        self.assertIn("systemctl mask packagekit-offline-update.service", script)
        self.assertNotIn("rm -f /etc/xdg/autostart", script)
        # Never clobbers an admin's own system-wide Discover config.
        self.assertIn(f"grep -qF '{dm.MANAGED_MARKER}'", script)

    def test_enable_undoes_everything(self):
        script = self._script(self.mgr.build_system_enable_commands())
        self.assertIn(f"systemctl --global unmask {dm.NOTIFIER_UNIT}", script)
        self.assertIn("systemctl unmask packagekit-offline-update.service", script)
        self.assertIn("reinstall -y plasma-discover-notifier", script)

    def test_status_detects_global_mask(self):
        status = DiscoverStatus(discover_installed=True, system_autostart_present=True)
        with patch.object(dm.os.path, "islink", return_value=True), \
             patch.object(dm.os, "readlink", return_value="/dev/null"):
            self.assertTrue(DiscoverManager._is_system_disabled(status))
        with patch.object(dm.os.path, "islink", return_value=False):
            self.assertFalse(DiscoverManager._is_system_disabled(status))
            legacy = DiscoverStatus(discover_installed=True, system_autostart_present=False)
            self.assertTrue(DiscoverManager._is_system_disabled(legacy))


class TestRestartUpdateCancel(unittest.TestCase):
    def test_detects_only_packagekit_trigger(self):
        with patch.object(dm.os.path, "islink", return_value=True), \
             patch.object(dm.os, "readlink", return_value="/var/lib/PackageKit/prepared-update"):
            self.assertTrue(DiscoverManager.restart_update_scheduled())
        # dnf's own offline upgrades use the same trigger but point elsewhere.
        with patch.object(dm.os.path, "islink", return_value=True), \
             patch.object(dm.os, "readlink", return_value="/usr/lib/sysimage/libdnf5/offline"):
            self.assertFalse(DiscoverManager.restart_update_scheduled())
        with patch.object(dm.os.path, "islink", return_value=False):
            self.assertFalse(DiscoverManager.restart_update_scheduled())

    def test_cancel_command_and_system_disable_cancels_first(self):
        self.assertEqual(DiscoverManager.build_cancel_restart_update_command(),
                         ["pkcon", "offline-cancel"])
        script = DiscoverManager().build_system_disable_commands()[0][3]
        self.assertLess(script.index("pkcon offline-cancel"),
                        script.index("systemctl mask packagekit-offline-update"))


def _status(**fields):
    return DiscoverStatus(**{"discover_installed": True, "system_autostart_present": True,
                             **fields})


def test_settings_status_is_plain_language(app):
    settings = app.settings_controller

    def show(**fields):
        settings._on_discover_status(_status(**fields))
        for text in (settings.discoverTitle, settings.discoverText):
            assert "—" not in text
            for jargon in ("PlasmaDiscoverUpdates", "packagekit-offline-update",
                           "DiscoverNotifier", "autostart"):
                assert jargon not in text

    # Active takeover: positive, only Restore offered.
    show(per_user_disabled=True)
    assert settings.discoverLevel == "positive"
    assert "this app handles updates" in settings.discoverTitle.lower()
    assert settings.discoverActive
    # Discover checking on its own: warning, only Take Over offered.
    show(notifier_running=True, restart_update_scheduled=True)
    assert settings.discoverLevel == "warning"
    assert not settings.discoverActive
    assert "running right now" in settings.discoverText
    assert "restart" in settings.discoverText
    # Nothing installed: no jargon, no actions.
    show(discover_installed=False, system_autostart_present=False)
    assert settings.discoverLevel == "info"
    assert not settings.discoverInstalled


def test_settings_warns_about_a_scheduled_restart_even_after_takeover(app):
    settings = app.settings_controller
    settings._on_discover_status(_status(per_user_disabled=True))
    assert settings.discoverLevel == "positive"
    assert not settings.discoverScheduled  # no Cancel button
    settings._on_discover_status(_status(per_user_disabled=True, restart_update_scheduled=True))
    assert settings.discoverLevel == "warning"
    assert "scheduled" in settings.discoverTitle.lower()
    assert settings.discoverScheduled


class TestTakeOver:
    @pytest.fixture
    def take_over(self, app):
        def run(*choices, scheduled=True, reminders=True):
            app.settings.reminders_enabled = reminders
            shown = answer(app, *choices)
            manager = app.discover_manager
            with patch.object(manager, "restart_update_scheduled", return_value=scheduled), \
                    patch.object(manager, "set_per_user_enabled") as set_enabled, \
                    patch.object(app.settings_controller, "load_discover_status"), \
                    patch("subprocess.run"), \
                    patch.object(app.runner, "run") as run:
                app.settings_controller.takeOver()
            confirms = [p for p in shown if any(b == "no" for b, _ in p.buttons)]
            return confirms, set_enabled, run
        return run

    def test_offers_to_cancel_a_scheduled_update(self, take_over):
        confirms, set_enabled, run = take_over("yes", "yes")
        assert len(confirms) == 2  # take over, then cancel?
        set_enabled.assert_called_once_with(False)
        run.assert_called_once_with(["pkcon", "offline-cancel"],
                                    "Cancelling Discover's restart update")

    def test_keeping_the_scheduled_update_runs_nothing(self, take_over):
        confirms, set_enabled, run = take_over("yes", "no")
        assert len(confirms) == 2
        set_enabled.assert_called_once_with(False)
        run.assert_not_called()

    def test_offers_reminders_when_they_are_off(self, take_over):
        confirms, set_enabled, _ = take_over("yes", "no", "no", reminders=False)
        assert confirms[-1].title == "Turn On Update Reminders?"
        set_enabled.assert_called_once_with(False)

    def test_declined_changes_nothing(self, take_over):
        confirms, set_enabled, run = take_over("no")
        assert len(confirms) == 1
        set_enabled.assert_not_called()
        run.assert_not_called()

    def test_system_wide_disable_runs_the_pkexec_script_after_yes(self, app):
        shown = answer(app, "yes")
        with patch.object(app.runner, "run") as run:
            app.settings_controller.disableDiscoverSystem()
        assert shown[0].destructive
        run.assert_called_once_with(app.discover_manager.build_system_disable_commands()[0],
                                    "Disabling Discover system-wide")
        answer(app, "no")
        with patch.object(app.runner, "run") as run:
            app.settings_controller.disableDiscoverSystem()
        run.assert_not_called()
