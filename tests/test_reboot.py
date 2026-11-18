"""Whether a restart is needed after updates: the backend's checks, the
scan that reports them, and the Updates page's restart notice.

``check_reboot()`` answers True, False, or None when every check was
inconclusive; None shows "A restart may be needed" instead of claiming
either way.
"""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from dnf_gui.core.dnf_backend import DNFBackend
from dnf_gui.core.package import Package, PackageStatus, UpdateInfo
from tests.conftest import REAL_COMBINED_CHECK_RUN, make_backend

DNF5 = ["/usr/bin/dnf5", "-C", "-q", "needs-restarting", "-r"]
LEGACY = ["needs-restarting", "-r"]
RUNNING = "6.18.5-200.fc45.x86_64"
NEWER_KERNEL = "1760000000 6.18.6-200.fc45.x86_64\n1750000000 6.18.5-200.fc45.x86_64\n"
SAME_KERNEL = "1750000000 6.18.5-200.fc45.x86_64\n"
MISSING = FileNotFoundError()


def _check(dnf=MISSING, legacy=MISSING, sentinel=False, kernels=SAME_KERNEL, dnf5=True):
    """Run check_reboot with each probe scripted: an exit code, or an
    exception to raise. ``kernels`` is the rpm query's output (None: rpm
    fails). Returns (result, the argv of every command run)."""
    backend = make_backend("/usr/bin/dnf5" if dnf5 else "/usr/bin/dnf")
    calls = []

    def outcome(value, **fields):
        if isinstance(value, BaseException):
            raise value
        return MagicMock(returncode=value, **fields)

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        assert isinstance(cmd, list) and "shell" not in kwargs and "timeout" in kwargs
        if cmd == DNF5:
            return outcome(dnf)
        if cmd == LEGACY:
            return outcome(legacy)
        if cmd[0] == "rpm":
            if kernels is None:
                return MagicMock(returncode=1, stdout="")
            return MagicMock(returncode=0, stdout=kernels)
        raise AssertionError(f"unexpected {cmd}")

    with patch("dnf_gui.core.dnf_backend.subprocess.run", side_effect=fake_run), \
            patch("dnf_gui.core.dnf_backend.os.path.exists",
                  side_effect=lambda p: sentinel and p == "/run/reboot-required"), \
            patch("dnf_gui.core.dnf_backend.os.path.realpath", side_effect=lambda p: p), \
            patch("dnf_gui.core.dnf_backend.platform.release", return_value=RUNNING):
        return backend.check_reboot(), calls


@pytest.mark.parametrize("probes, expected, ran", [
    # dnf5's built-in needs-restarting answers first.
    (dict(dnf=1), True, [DNF5]),
    (dict(dnf=0), False, [DNF5]),
    # Inconclusive (a plugin error, a timeout): the legacy binary next.
    (dict(dnf=2, legacy=1), True, [DNF5, LEGACY]),
    (dict(dnf=subprocess.TimeoutExpired("dnf5", 60), legacy=0), False, [DNF5, LEGACY]),
    # Neither: the sentinel file, then kernel drift.
    (dict(sentinel=True), True, [DNF5, LEGACY]),
    (dict(kernels=NEWER_KERNEL), True, [DNF5, LEGACY, "rpm"]),
    (dict(kernels=SAME_KERNEL), False, [DNF5, LEGACY, "rpm"]),
    (dict(dnf=subprocess.TimeoutExpired("dnf5", 60)), False, [DNF5, LEGACY, "rpm"]),
    # Nothing could tell: None, never an exception.
    (dict(kernels=None), None, [DNF5, LEGACY, "rpm", "rpm"]),
    (dict(dnf=OSError(), legacy=subprocess.TimeoutExpired("x", 1), kernels=None),
     None, [DNF5, LEGACY, "rpm", "rpm"]),
    # dnf4 has no needs-restarting command (exit 1 would read as "reboot").
    (dict(dnf5=False, legacy=0), False, [LEGACY]),
])
def test_check_reboot(probes, expected, ran):
    result, calls = _check(**probes)
    assert result is expected
    assert [c if c[0] != "rpm" else "rpm" for c in calls] == ran


def test_check_reboot_never_raises():
    backend = make_backend()
    with patch("dnf_gui.core.dnf_backend.subprocess.run",
               side_effect=subprocess.TimeoutExpired("x", 1)), \
            patch("dnf_gui.core.dnf_backend.os.path.exists", return_value=False):
        assert backend.check_reboot() is None


# ── the update scan ──────────────────────────────────────────────────

@pytest.mark.parametrize("reboot", [None, True, False])
def test_scan_reports_the_reboot_check_as_is(reboot):
    """The real CombinedUpdateCheckWorker.run passes check_reboot's answer
    through unchanged: None ("can't tell") must not turn into False."""
    from dnf_gui.core.worker import CombinedUpdateCheckWorker
    dnf = MagicMock(spec=DNFBackend)
    dnf.check_updates.return_value = UpdateInfo()
    dnf.get_upgrade_preview.return_value = None
    dnf.check_reboot.return_value = reboot
    flatpak = MagicMock(available=False)
    worker = CombinedUpdateCheckWorker(dnf, flatpak)
    results, errors = [], []
    worker.finished.connect(results.append)
    worker.error.connect(errors.append)
    with patch("dnf_gui.core.security.get_security_summary", return_value=None), \
            patch("dnf_gui.core.security.find_blocked_security"), \
            patch("dnf_gui.core.release_upgrade.check_release_upgrade", return_value=None):
        REAL_COMBINED_CHECK_RUN(worker)  # synchronously, on this thread
    assert errors == []
    assert results[0]["reboot"] is reboot
    dnf.check_reboot.assert_called_once_with()


def test_scan_reports_a_crashing_reboot_check_as_none():
    from dnf_gui.core.worker import CombinedUpdateCheckWorker
    dnf = MagicMock(spec=DNFBackend)
    dnf.check_updates.return_value = UpdateInfo()
    dnf.check_reboot.side_effect = RuntimeError("boom")
    worker = CombinedUpdateCheckWorker(dnf, MagicMock(available=False))
    results = []
    worker.finished.connect(results.append)
    with patch("dnf_gui.core.security.get_security_summary", return_value=None), \
            patch("dnf_gui.core.release_upgrade.check_release_upgrade", return_value=None):
        REAL_COMBINED_CHECK_RUN(worker)
    assert results[0]["reboot"] is None


# ── the restart notice ───────────────────────────────────────────────

def _scan(reboot):
    pkg = Package("htop", "3.4.2", "1.fc45", "x86_64", "updates",
                  status=PackageStatus.UPDATE_AVAILABLE, installed_version="3.4.1-1.fc45")
    return {"dnf": UpdateInfo(1, [pkg]), "flatpak": [], "security": None, "reboot": reboot}


def test_later_lasts_until_the_next_real_scan(app):
    updates = app.updates
    updates._on_checked(_scan(True))
    assert updates.rebootRequired is True
    updates.dismissReboot()
    assert updates.rebootRequired is False
    updates.set_reboot_required(True)   # e.g. the post-upgrade recheck
    updates.show()                      # a cached revisit
    assert updates.rebootRequired is False
    updates._on_checked(_scan(True))    # a fresh scan asks again
    assert updates.rebootRequired is True


def test_an_inconclusive_check_says_a_restart_may_be_needed(app):
    updates = app.updates
    updates._on_reboot_checked(None)
    assert updates.rebootRequired is True and updates.rebootCertain is False
    updates._on_reboot_checked(False)
    assert updates.rebootRequired is False
    updates._on_reboot_check_failed("dnf crashed")
    assert updates.rebootRequired is True and updates.rebootCertain is False


def test_a_rescan_that_cannot_tell_keeps_the_may_need_restart_notice(app):
    """After an update the reboot check says "maybe"; the rescan the same
    update starts must not clear it when it can't tell either."""
    updates = app.updates
    updates._on_reboot_checked(None)
    updates._on_checked(_scan(None))
    assert updates.rebootRequired is True and updates.rebootCertain is False
    updates._on_checked(_scan(False))   # a conclusive answer wins
    assert updates.rebootRequired is False
    updates._on_checked(_scan(True))
    assert updates.rebootRequired is True and updates.rebootCertain is True
