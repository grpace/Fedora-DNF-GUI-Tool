"""Security advisories: reading dnf's advisory lists, and the security
updates dnf skips because a dependency isn't ready yet ("waiting").

The blocked-update fixtures are trimmed dnf5 output from a Fedora 44 system
where RPM Fusion's libheif-freeworld still required the old libheif.
"""

import unittest
from unittest.mock import patch

import pytest

from dnf_gui.core import security
from dnf_gui.core.package import Package, PackageStatus, UpdateInfo
from dnf_gui.core.security import (
    BlockedUpdates, SecuritySummary, build_forced_security_update_command,
    find_blocked_security, get_security_summary, parse_blocked_updates,
    parse_unavailable_updates,
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


class TestSecuritySummary(unittest.TestCase):
    def test_urgent_flags(self):
        self.assertTrue(SecuritySummary(total=2, critical=1).urgent)
        self.assertFalse(SecuritySummary(total=1, moderate=1).urgent)
        self.assertFalse(SecuritySummary().urgent)

    @patch("dnf_gui.core.security._run")
    def test_parses_dnf4_style_list(self, mock_run):
        mock_run.side_effect = [
            "FEDORA-2026-aaa Critical/Sec. kernel-6.12-1.fc43.x86_64\n"
            "FEDORA-2026-bbb Moderate/Sec. firefox-125-1.fc43.x86_64\n",
            "",
        ]
        sec = get_security_summary()
        self.assertEqual((sec.total, sec.critical, sec.moderate), (2, 1, 1))
        self.assertIn("FEDORA-2026-aaa", sec.advisories)

    @patch("dnf_gui.core.security._run")
    def test_parses_dnf5_list_counting_unique_advisories(self, mock_run):
        mock_run.side_effect = [
            "Updating and loading repositories:\n"
            "Repositories loaded.\n"
            "Name                   Type     Severity   Package                       Issued\n"
            "FEDORA-2026-0ba06812ef security Important  libheif-1.23.6-1.fc44.x86_64 2026-10-18 01:17:00\n"
            "FEDORA-2026-0ba06812ef security Important  libheif-1.23.6-1.fc44.i686   2026-10-18 01:17:00\n"
            "FEDORA-2026-1111111111 security Critical   kernel-6.18-1.fc44.x86_64    2026-10-18 01:17:00\n",
            "",
        ]
        sec = get_security_summary()
        self.assertEqual((sec.total, sec.important, sec.critical), (2, 1, 1))
        self.assertEqual(len(sec.packages), 3)
        self.assertEqual(mock_run.call_args_list[0].args[0][1:],
                         ["updateinfo", "list", "--updates", "--security"])

    @patch("dnf_gui.core.security._run")
    def test_highest_severity_per_package(self, mock_run):
        mock_run.side_effect = [
            "FEDORA-2026-1 security Moderate  libfoo-1.0-1.fc44.x86_64 2026-10-01\n"
            "FEDORA-2026-2 security Critical  libfoo-1.1-1.fc44.x86_64 2026-10-02\n"
            "FEDORA-2026-3 security Low       my-pkg-name-2.0-3.fc44.noarch 2026-10-02\n",
            "",
        ]
        sec = get_security_summary()
        self.assertEqual(sec.package_severity,
                         {"libfoo": "critical", "my-pkg-name": "low"})

    @patch("dnf_gui.core.security._run")
    def test_dnf5_summary_fallback_ignores_other_sections(self, mock_run):
        mock_run.side_effect = [
            "",
            "Available advisory information summary:\n"
            "Security    : 36\n"
            "  Critical  : 3\n"
            "  Important : 18\n"
            "  Moderate  : 11\n"
            "  Low       : 2\n"
            "  Other     : 2\n"
            "Bugfix      : 36\n"
            "Enhancement : 30\n",
        ]
        sec = get_security_summary()
        self.assertEqual(sec.total, 34)
        self.assertEqual((sec.critical, sec.important, sec.moderate, sec.low),
                         (3, 18, 11, 2))

    @patch("dnf_gui.core.security._run")
    def test_dnf4_summary_fallback_counts(self, mock_run):
        mock_run.side_effect = [
            "",  # empty list output
            "Updates Information Summary: available\n"
            "    2 Critical Security notice(s)\n"
            "    3 Important Security notice(s)\n",
        ]
        sec = get_security_summary()
        self.assertEqual((sec.total, sec.critical, sec.important), (5, 2, 3))


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

    def test_broken_dependency_skips_are_unavailable_not_blocked(self):
        self.assertIsNone(parse_blocked_updates(FFMPEG_SKIPPED))
        self.assertEqual(parse_unavailable_updates(FFMPEG_SKIPPED), ["ffmpeg", "ffmpeg-libs"])


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


def _scan(app, info, summary):
    app.updates._on_checked({"dnf": info, "flatpak": [], "security": summary})


def _mode(app, key):
    return next(m for m in app.updates.modes if m["key"] == key)


@pytest.fixture
def scanned(app):
    """``scanned(summary)``: the app after a scan with three updates."""
    def scan(summary):
        info = UpdateInfo(packages=[
            Package(name=n, version="1", status=PackageStatus.UPDATE_AVAILABLE)
            for n in ("libheif", "libheif-ffmpeg", "firefox")])
        _scan(app, info, summary)
        return app
    return scan


class TestWaitingOnTheUpdatesPage:
    def test_notice_count_and_mode_when_nothing_installable(self, scanned):
        updates = scanned(_blocked_summary()).updates
        notice = updates.blocked
        assert notice["visible"]
        assert notice["title"] == "1 security advisory waiting on RPM Fusion"
        # Leads with what to do now; Force is behind Details, not on the notice.
        assert "Nothing to do now" in notice["text"]
        assert "forceTooltip" not in notice
        assert (updates.securityTotal, updates.securityWaiting,
                updates.security_installable) == (1, 1, 0)
        mode = _mode(updates.app, "security")
        assert mode["enabled"]  # clicking explains + offers force
        assert "nothing to install yet" in mode["detail"].lower()

    def test_partial_block_says_what_still_installs(self, scanned):
        updates = scanned(
            _blocked_summary(("FEDORA-2026-ff", "moderate", {"firefox"}))).updates
        assert updates.security_installable == 1
        assert "still installs the other 1 advisory" in updates.blocked_summary()

    def test_waiting_rows_are_tagged(self, scanned):
        model = scanned(
            _blocked_summary(("FEDORA-2026-ff", "moderate", {"firefox"}))).updates.model
        libheif = model.find("name", "libheif")
        assert libheif["waiting"] and libheif["severity"] == "Important"
        assert "can't install it yet" in libheif["tooltip"]
        firefox = model.find("name", "firefox")
        assert firefox["security"] and not firefox["waiting"]

    def test_notice_hidden_without_blocks(self, scanned):
        updates = scanned(_summary((ADVISORY, "important", {"libheif"}))).updates
        assert updates.blocked == {}
        assert updates.securityWaiting == 0


class TestSecurityOnlyWhenWaiting:
    @pytest.fixture
    def blocked(self, app):
        _scan(app, UpdateInfo(), _blocked_summary())
        return app

    def test_explains_instead_of_running(self, blocked):
        shown = answer(blocked)
        with patch.object(blocked.runner, "run") as run:
            blocked.updates.security_upgrade()
        prompt = shown[0]
        assert prompt.title == "Nothing to Install Yet"
        assert [b for b, _ in prompt.buttons] == ["force", "ok"]
        assert prompt.default == "ok"
        assert "won't install it until then" in prompt.text
        run.assert_not_called()

    def test_force_confirms_then_runs_forced_command(self, blocked):
        shown = answer(blocked, "yes")
        with patch.object(blocked.runner, "run") as run:
            blocked.updates.forceSecurity()
        prompt = shown[-1]
        assert "libheif-freeworld" in prompt.text
        assert "sudo dnf install libheif-freeworld" in prompt.text
        assert prompt.destructive and prompt.default == "no"
        run.assert_called_once_with(build_forced_security_update_command(),
                                    "Forced Security Upgrade")
        assert blocked.forced_removals == ["libheif-freeworld"]

    def test_explanation_force_button_leads_to_forced_run(self, blocked):
        answer(blocked, "force", "yes")
        with patch.object(blocked.runner, "run") as run:
            blocked.updates.security_upgrade()
        run.assert_called_once_with(build_forced_security_update_command(),
                                    "Forced Security Upgrade")

    def test_force_declined_runs_nothing(self, blocked):
        answer(blocked, "no")
        with patch.object(blocked.runner, "run") as run:
            blocked.updates.forceSecurity()
        run.assert_not_called()
        assert blocked.forced_removals == []


class TestSkippedPackagesAfterARun:
    def _finish(self, app, output, operation="Security Upgrade"):
        _scan(app, UpdateInfo(), SecuritySummary())
        app.runner._output = output.splitlines()
        with patch.object(app.updates, "recheck_reboot"):
            app.runner._finish(0, operation, False)

    def test_blocked_run_reports_skipped_packages(self, app):
        self._finish(app, SECURITY_BLOCKED)
        output = app.runner.text()
        assert "1 update couldn't be installed: libheif" in output
        assert "Running Security Only again won't install it" in output
        assert app.runner.statusText == "Completed · 1 Update Skipped"

    def test_broken_dependencies_are_reported(self, app):
        self._finish(app, FFMPEG_SKIPPED, "Update Without Core")
        assert app.runner.statusText == "Completed · 2 Updates Skipped"
        assert "ffmpeg, ffmpeg-libs" in app.runner.text()

    def test_clean_run_keeps_plain_success(self, app):
        self._finish(app, FORCED)
        assert app.runner.statusText == "Completed"
        assert "couldn't be installed" not in app.runner.text()
