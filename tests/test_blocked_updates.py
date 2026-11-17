"""Security updates dnf skips because a dependency isn't ready yet.

Fixtures are trimmed dnf5 output from a Fedora 44 system where RPM Fusion's
libheif-freeworld still required the old libheif.
"""

import gc
import unittest
from unittest.mock import patch

from dnf_gui.core import security
from dnf_gui.core.app_settings import AppSettings, perform_background_check
from dnf_gui.core.package import Package, PackageStatus, UpdateInfo
from dnf_gui.core.security import (
    BlockedUpdates, SecuritySummary, build_forced_security_update_command,
    find_blocked_security, parse_blocked_updates,
)
from tests.conftest import answer

SECURITY_BLOCKED = """\
Updating and loading repositories:
Repositories loaded.
Problem: problem with installed package
  - installed package libheif-freeworld-1.23.6-1.fc44.x86_64 requires libheif(x86-64) = 1.23.6, but none of the providers can be installed
  - package libheif-freeworld-1.23.6-1.fc44.x86_64 from rpmfusion-free-updates requires libheif(x86-64) = 1.23.6, but none of the providers can be installed
  - package libheif-freeworld-1.21.2-3.fc44.x86_64 from rpmfusion-free requires libheif(x86-64) = 1.21.2, but none of the providers can be installed
  - cannot install both libheif-1.23.7-1.fc44.x86_64 from updates and libheif-1.23.6-1.fc44.x86_64 from @System
  - cannot install the best update candidate for package libheif-1.23.6-1.fc44.x86_64

Package            Arch   Version       Repository          Size
Skipping packages with conflicts:
 libheif           x86_64 1.21.2-1.fc44 fedora           1.8 MiB
 libheif           x86_64 1.23.7-1.fc44 updates          2.4 MiB
Skipping packages with broken dependencies:
 libheif-freeworld x86_64 1.21.2-3.fc44 rpmfusion-free 185.7 KiB

Nothing to do.
"""

FULL_UPGRADE = """\
Updating and loading repositories:
Repositories loaded.
Problem 1: installed package libheif-freeworld-1.23.6-1.fc44.x86_64 requires libheif(x86-64) = 1.23.6, but none of the providers can be installed
  - cannot install both libheif-1.23.7-1.fc44.x86_64 from updates and libheif-1.23.6-1.fc44.x86_64 from @System
Problem 2: problem with installed package
  - package libheif-freeworld-1.23.6-1.fc44.x86_64 from rpmfusion-free-updates requires libheif(x86-64) = 1.23.6, but none of the providers can be installed

Package                                    Arch   Version            Repository                     Size
Upgrading:
 akmod-nvidia                              x86_64 3:615.78.08-1.fc44 rpmfusion-nonfree-updates 100.2 KiB
   replacing akmod-nvidia                  x86_64 3:615.71.09-3.fc44 rpmfusion-nonfree-updates 100.2 KiB
 grub2-common                              noarch 1:2.12-66.fc44     updates                     6.2 MiB
   replacing grub2-common                  noarch 1:2.12-64.fc44     updates                     6.2 MiB
Skipping packages with conflicts:
 libheif                                   x86_64 1.21.2-1.fc44      fedora                      1.8 MiB
 libheif                                   x86_64 1.23.7-1.fc44      updates                     2.4 MiB
 libheif-ffmpeg                            x86_64 1.23.7-1.fc44      updates                    32.0 KiB
Skipping packages with broken dependencies:
 libheif-freeworld                         x86_64 1.21.2-3.fc44      rpmfusion-free            185.7 KiB

Transaction Summary:
 Upgrading:         2 packages
 Replacing:         2 packages
 Skipping:           4 packages

Operation aborted by the user.
"""

FORCED = """\
Repositories loaded.
Package                     Arch   Version         Repository                  Size
Removing dependent packages:
 libheif-freeworld          x86_64 0:1.23.6-1.fc44 rpmfusion-free-updates 226.8 KiB
Upgrading:
 libheif                    x86_64 0:1.23.7-1.fc44 updates                  2.4 MiB
   replacing libheif        x86_64 0:1.23.6-1.fc44 updates                  2.3 MiB
 libheif-ffmpeg             x86_64 0:1.23.7-1.fc44 updates                 32.0 KiB
   replacing libheif-ffmpeg x86_64 0:1.23.6-1.fc44 updates                 32.0 KiB

Transaction Summary:
 Upgrading:          2 packages
 Removing:           1 package

Operation aborted by the user.
"""

ADVISORY = "FEDORA-2026-09382b8de6"


def _summary(*advisories) -> SecuritySummary:
    """advisories: (id, severity, {package names})"""
    s = SecuritySummary(total=len(advisories))
    for adv, sev, names in advisories:
        s.advisories.append(adv)
        s.advisory_severity[adv] = sev
        s.advisory_packages[adv] = set(names)
        for name in names:
            s.package_severity[name] = sev
        setattr(s, sev, getattr(s, sev) + 1)
    return s


def _blocked_summary(other=None) -> SecuritySummary:
    advisories = [(ADVISORY, "important", {"libheif", "libheif-ffmpeg"})]
    if other:
        advisories.append(other)
    s = _summary(*advisories)
    s.blocked = BlockedUpdates(packages=["libheif", "libheif-ffmpeg"],
                               blockers={"libheif-freeworld": "rpmfusion-free-updates"},
                               removals=["libheif-freeworld"])
    return s


class TestParseBlockedUpdates(unittest.TestCase):
    def test_security_run(self):
        blocked = parse_blocked_updates(SECURITY_BLOCKED)
        self.assertEqual(blocked.packages, ["libheif"])
        self.assertEqual(blocked.blockers, {"libheif-freeworld": "rpmfusion-free-updates"})
        self.assertEqual(blocked.source, "RPM Fusion")
        text = blocked.explanation()
        self.assertIn("libheif can't update yet", text)
        self.assertIn("libheif-freeworld from RPM Fusion", text)

    def test_full_upgrade_lists_skips_not_upgrades(self):
        blocked = parse_blocked_updates(FULL_UPGRADE)
        self.assertEqual(blocked.packages, ["libheif", "libheif-ffmpeg"])
        self.assertNotIn("akmod-nvidia", blocked.packages)
        self.assertEqual(list(blocked.blockers), ["libheif-freeworld"])

    def test_clean_runs_report_nothing(self):
        self.assertIsNone(parse_blocked_updates(FORCED))
        self.assertIsNone(parse_blocked_updates("Nothing to do.\n"))
        self.assertIsNone(parse_blocked_updates(""))

    def test_forced_removals(self):
        sections = security._table_sections(FORCED)
        self.assertEqual(sections["remove"], ["libheif-freeworld"])
        self.assertEqual(sections["install"], ["libheif", "libheif-ffmpeg"])

    def test_dnf4_header_note_is_ignored(self):
        out = ("Skipping packages with conflicts:\n"
               "(add '--best --allowerasing' to command line to force their upgrade):\n"
               " libheif   x86_64  1.23.7-1.fc44  updates  2.4 M\n\n")
        self.assertEqual(parse_blocked_updates(out).packages, ["libheif"])

    def test_unknown_blocker_still_explains(self):
        text = BlockedUpdates(packages=["foo"]).explanation()
        self.assertIn("foo", text)


class TestFindBlockedSecurity(unittest.TestCase):
    def test_marks_advisory_waiting_and_learns_removals(self):
        s = _summary((ADVISORY, "important", {"libheif", "libheif-ffmpeg"}))
        with patch.object(security, "_dry_run",
                          side_effect=[SECURITY_BLOCKED, FORCED]) as dry:
            blocked = find_blocked_security(s)
        self.assertEqual(dry.call_args_list[1].args[0],
                         ["--security", "--allowerasing", "--best"])
        # libheif-ffmpeg isn't in dnf's skip list but isn't installing either.
        self.assertEqual(sorted(blocked.packages), ["libheif", "libheif-ffmpeg"])
        self.assertEqual(blocked.removals, ["libheif-freeworld"])
        self.assertEqual(s.blocked_advisories, [ADVISORY])
        self.assertEqual(s.installable_total, 0)
        self.assertTrue(s.urgent)
        self.assertFalse(s.installable_urgent)

    def test_installable_advisories_are_not_waiting(self):
        s = _summary((ADVISORY, "important", {"libheif"}),
                     ("FEDORA-2026-other", "moderate", {"akmod-nvidia"}))
        with patch.object(security, "_dry_run",
                          side_effect=[FULL_UPGRADE, FORCED]):
            find_blocked_security(s)
        self.assertEqual(s.blocked_advisories, [ADVISORY])
        self.assertEqual(s.installable_total, 1)

    def test_nothing_blocked(self):
        s = _summary(("FEDORA-2026-other", "moderate", {"akmod-nvidia"}))
        with patch.object(security, "_dry_run", return_value=FULL_UPGRADE):
            self.assertIsNone(find_blocked_security(s))
        self.assertIsNone(s.blocked)

    def test_unknown_output_or_no_advisories_skips(self):
        s = _summary((ADVISORY, "important", {"libheif"}))
        with patch.object(security, "_dry_run", return_value=None):
            self.assertIsNone(find_blocked_security(s))
        with patch.object(security, "_dry_run") as dry:
            self.assertIsNone(find_blocked_security(SecuritySummary()))
        dry.assert_not_called()

    def test_forced_command_needs_password_in_updates_scope(self):
        from dnf_gui.core.passwordless import maybe_passwordless
        cmd = build_forced_security_update_command()
        self.assertEqual(cmd[-3:], ["--security", "--allowerasing", "--best"])
        self.assertEqual(maybe_passwordless(cmd, "updates"), cmd)


class TestReminderSkipsWaiting(unittest.TestCase):
    @patch("dnf_gui.core.dnf_backend.DNFBackend.check_updates",
           return_value=UpdateInfo(total_updates=3))
    @patch("dnf_gui.core.flatpak_backend.FlatpakBackend.available", False)
    @patch("dnf_gui.core.security.get_security_summary")
    def test_security_only_reminder_quiet_when_all_waiting(self, mock_sec, _dnf):
        mock_sec.return_value = _summary((ADVISORY, "important", {"libheif"}))
        settings = AppSettings()
        settings.security_only = True
        settings.notify_flatpak = False
        self.addCleanup(setattr, settings, "security_only", False)
        self.addCleanup(setattr, settings, "notify_flatpak", True)
        with patch.object(security, "_dry_run", side_effect=[SECURITY_BLOCKED, FORCED]):
            res = perform_background_check(settings)
        self.assertEqual(res.security_total, 0)
        self.assertEqual(res.security_waiting, 1)
        self.assertFalse(res.security_urgent)
        self.assertFalse(res.should_notify)


def _controller():
    # Free controllers left by earlier tests now, while none of their
    # threads run: a later processEvents() would otherwise fire their
    # pending start-up timers and GC could destroy a running QThread.
    gc.collect()
    from dnf_gui.ui.controllers.app_controller import AppController
    return AppController()


def _scan(app, info, summary):
    app.updates._on_checked({"dnf": info, "flatpak": [], "security": summary})


class TestUpdatesBlocked(unittest.TestCase):
    def _app(self, summary):
        app = _controller()
        info = UpdateInfo(packages=[
            Package(name=n, version="1", status=PackageStatus.UPDATE_AVAILABLE)
            for n in ("libheif", "libheif-ffmpeg", "firefox")])
        _scan(app, info, summary)
        return app

    def _mode(self, app, key):
        return next(m for m in app.updates.modes if m["key"] == key)

    def test_banner_count_and_mode_when_nothing_installable(self):
        updates = self._app(_blocked_summary()).updates
        banner = updates.blocked
        self.assertTrue(banner["visible"])
        self.assertEqual(banner["title"], "1 security advisory waiting on RPM Fusion")
        self.assertIn("won't install it until then", banner["text"])
        self.assertIn("libheif-freeworld", banner["forceTooltip"])
        self.assertEqual(updates.securityTotal, 1)
        self.assertEqual(updates.securityWaiting, 1)
        self.assertEqual(updates.security_installable, 0)
        mode = self._mode(updates.app, "security")
        self.assertTrue(mode["enabled"])  # clicking explains + offers force
        self.assertIn("nothing to install yet", mode["detail"].lower())

    def test_partial_block_says_what_still_installs(self):
        updates = self._app(
            _blocked_summary(("FEDORA-2026-ff", "moderate", {"firefox"}))).updates
        self.assertEqual(updates.security_installable, 1)
        self.assertIn("still installs the other 1 advisory", updates.blocked_summary())

    def test_waiting_rows_are_tagged(self):
        model = self._app(
            _blocked_summary(("FEDORA-2026-ff", "moderate", {"firefox"}))).updates.model
        libheif = model.find("name", "libheif")
        self.assertTrue(libheif["waiting"])
        self.assertEqual(libheif["severity"], "Important")
        self.assertIn("can't install it yet", libheif["tooltip"])
        firefox = model.find("name", "firefox")
        self.assertTrue(firefox["security"])
        self.assertFalse(firefox["waiting"])

    def test_banner_hidden_without_blocks(self):
        updates = self._app(_summary((ADVISORY, "important", {"libheif"}))).updates
        self.assertEqual(updates.blocked, {})
        self.assertEqual(updates.securityWaiting, 0)


class TestControllerBlocked(unittest.TestCase):
    def _app(self, summary):
        app = _controller()
        _scan(app, UpdateInfo(), summary)
        return app

    def test_security_only_explains_instead_of_running(self):
        app = self._app(_blocked_summary())
        with patch.object(app.updates, "explain_blocked_security") as explain, \
                patch.object(app.runner, "run") as run:
            app.updates.security_upgrade()
        explain.assert_called_once()
        run.assert_not_called()

    def test_explanation_offers_force_but_defaults_to_ok(self):
        app = self._app(_blocked_summary())
        shown = answer(app)
        with patch.object(app.runner, "run") as run:
            app.updates.security_upgrade()
        prompt = shown[0]
        self.assertEqual(prompt.title, "Nothing to Install Yet")
        self.assertEqual([b for b, _ in prompt.buttons], ["force", "ok"])
        self.assertEqual(prompt.default, "ok")
        self.assertIn("won't install it until then", prompt.text)
        run.assert_not_called()

    def test_force_confirms_then_runs_forced_command(self):
        app = self._app(_blocked_summary())
        shown = answer(app, "yes")
        with patch.object(app.runner, "run") as run:
            app.updates.forceSecurity()
        prompt = shown[-1]
        self.assertIn("libheif-freeworld", prompt.text)
        self.assertIn("sudo dnf install libheif-freeworld", prompt.text)
        self.assertTrue(prompt.destructive)
        self.assertEqual(prompt.default, "no")
        run.assert_called_once_with(build_forced_security_update_command(),
                                    "Forced Security Upgrade")
        self.assertEqual(app.forced_removals, ["libheif-freeworld"])

    def test_explanation_force_button_leads_to_forced_run(self):
        app = self._app(_blocked_summary())
        answer(app, "force", "yes")
        with patch.object(app.runner, "run") as run:
            app.updates.security_upgrade()
        run.assert_called_once_with(build_forced_security_update_command(),
                                    "Forced Security Upgrade")

    def test_force_declined_runs_nothing(self):
        app = self._app(_blocked_summary())
        answer(app, "no")
        with patch.object(app.runner, "run") as run:
            app.updates.forceSecurity()
        run.assert_not_called()
        self.assertEqual(app.forced_removals, [])

    def test_finished_run_reports_skipped_packages(self):
        app = self._app(SecuritySummary())
        app.runner._output = SECURITY_BLOCKED.splitlines()
        with patch.object(app.updates, "recheck_reboot"):
            app.runner._finish(0, "Security Upgrade", False)
        output = app.runner.text()
        self.assertIn("1 update couldn't be installed: libheif", output)
        self.assertIn("Running Security Only again won't install it", output)
        self.assertEqual(app.runner.statusText, "Completed · 1 Update Skipped")

    def test_clean_run_keeps_plain_success(self):
        app = self._app(SecuritySummary())
        app.runner._output = FORCED.splitlines()
        with patch.object(app.updates, "recheck_reboot"):
            app.runner._finish(0, "Security Upgrade", False)
        self.assertEqual(app.runner.statusText, "Completed")
        self.assertNotIn("couldn't be installed", app.runner.text())


if __name__ == "__main__":
    unittest.main()
