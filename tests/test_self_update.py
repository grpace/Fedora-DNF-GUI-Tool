"""The self-updater: finding a newer release on GitHub, downloading its RPM
from a GitHub host only, checking it against GitHub's SHA-256 digest, and
installing exactly that file as root. Every HTTP call here is mocked."""

import hashlib
import io
import json
import os
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from dnf_gui.core import updater
from dnf_gui.core.updater import (
    VERIFIED_INSTALL_SCRIPT, _asset_sha256, _is_safe_download_url, _version_compare,
    build_verified_install_command, check_for_update,
)
from dnf_gui.core.worker import AppUpdateDownloadWorker
from tests.conftest import answer

RPM = b"the real rpm"
DIGEST = hashlib.sha256(RPM).hexdigest()
ASSET_URL = ("https://github.com/grpace/Fedora-DNF-GUI-Tool/releases/download/"
             "v2.0.1/DNF-Package-Manager-v2.0.1.rpm")


def _release(tag="v2.0.1", assets=None, **extra):
    if assets is None:
        assets = [{"name": "DNF-Package-Manager-v2.0.1.rpm",
                   "browser_download_url": ASSET_URL, "digest": f"sha256:{DIGEST}"}]
    return dict(tag_name=tag, assets=assets,
                html_url="https://github.com/grpace/Fedora-DNF-GUI-Tool/releases/tag/" + tag,
                body="Fixes", **extra)


def _check(release, current="2.0.0"):
    seen = {}

    def urlopen(request, timeout=None):
        seen["url"] = request.full_url
        return io.BytesIO(json.dumps(release).encode())
    with patch("urllib.request.urlopen", side_effect=urlopen):
        info = check_for_update(current)
    assert seen["url"] == updater.GITHUB_API_URL
    return info


# ── finding the update ───────────────────────────────────────────────

@pytest.mark.parametrize("current, latest, expected", [
    ("2.0.0", "2.0.10", -1),   # numeric, not string, order
    ("2.0.10", "2.0.9", 1),
    ("2.0.0", "v2.0.0", 0),
    ("2.0", "2.0.0", 0),
    ("1.5.1", "2.0.0", -1),
])
def test_version_compare(current, latest, expected):
    assert _version_compare(current, latest) == expected


def test_newer_release_with_its_rpm_and_digest():
    info = _check(_release())
    assert (info.latest_version, info.download_url, info.sha256) == ("2.0.1", ASSET_URL, DIGEST)
    assert info.release_url.endswith("/v2.0.1")


def test_same_or_older_release_is_no_update():
    assert _check(_release("v2.0.0")) is None
    assert _check(_release("v1.5.1")) is None
    assert _check(_release(""), current="2.0.0") is None


def test_noarch_rpm_is_preferred_and_other_files_ignored():
    noarch = ASSET_URL.replace(".rpm", ".noarch.rpm")
    info = _check(_release(assets=[
        {"name": "notes.txt", "browser_download_url": ASSET_URL.replace(".rpm", ".txt")},
        {"name": "x.rpm", "browser_download_url": ASSET_URL, "digest": "sha256:" + "0" * 64},
        {"name": "x.noarch.rpm", "browser_download_url": noarch, "digest": f"sha256:{DIGEST}"},
    ]))
    assert (info.download_url, info.sha256) == (noarch, DIGEST)


@pytest.mark.parametrize("name", ["x.rpm", "x.noarch.rpm"])
def test_asset_on_another_host_is_not_offered(name):
    info = _check(_release(assets=[{"name": name, "digest": f"sha256:{DIGEST}",
                                    "browser_download_url": f"https://evil.example/{name}"}]))
    assert info.latest_version == "2.0.1"
    assert (info.download_url, info.sha256) == ("", "")


def test_network_or_json_errors_are_no_update():
    with patch("urllib.request.urlopen", side_effect=OSError("offline")):
        assert check_for_update("2.0.0") is None
    with patch("urllib.request.urlopen", return_value=io.BytesIO(b"<html>")):
        assert check_for_update("2.0.0") is None


def test_asset_digest_parsing():
    assert _asset_sha256({"digest": "sha256:" + "AB" * 32}) == "ab" * 32
    assert _asset_sha256({"digest": "md5:abc"}) == ""
    assert _asset_sha256({"digest": "sha256:xyz"}) == ""
    assert _asset_sha256({}) == ""


@pytest.mark.parametrize("url, safe", [
    ("https://github.com/x/y.rpm", True),
    ("https://release-assets.githubusercontent.com/x/y.rpm", True),
    ("https://objects.githubusercontent.com/x/y.rpm", True),
    ("http://github.com/x.rpm", False),             # not https
    ("https://evil.example/x.rpm", False),
    ("https://github.com.evil.example/x.rpm", False),
    ("https://evilgithub.com/x.rpm", False),
    ("", False),
])
def test_download_hosts(url, safe):
    assert _is_safe_download_url(url) is safe


# ── downloading and checking it ──────────────────────────────────────

class _Response:
    def __init__(self, body, url):
        self._body, self._url = body, url

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def geturl(self):
        return self._url

    def read(self, limit=-1):
        return self._body if limit < 0 else self._body[:limit]


def _download(body=RPM, digest=DIGEST, url=ASSET_URL, final_url=None):
    worker = AppUpdateDownloadWorker(url, digest)
    done, errors = [], []
    worker.finished.connect(done.append)
    worker.error.connect(errors.append)
    folders = []
    real_mkdtemp = __import__("tempfile").mkdtemp

    def mkdtemp(**kwargs):
        folders.append(real_mkdtemp(**kwargs))
        return folders[-1]
    with patch("urllib.request.urlopen",
               return_value=_Response(body, final_url or url)) as urlopen, \
            patch("dnf_gui.core.worker.tempfile.mkdtemp", side_effect=mkdtemp):
        worker.run()  # synchronously: no thread needed
    return done, errors, urlopen, folders


def test_verified_download_is_saved_privately():
    done, errors, _, folders = _download()
    assert errors == []
    assert done == [os.path.join(folders[0], "DNF-Package-Manager-v2.0.1.rpm")]
    with open(done[0], "rb") as f:
        assert f.read() == RPM


def test_checksum_mismatch_saves_nothing():
    done, errors, _, folders = _download(body=b"something else")
    assert done == [] and folders == []
    assert errors[0].startswith("Checksum mismatch")


def test_redirect_to_another_host_is_refused():
    done, errors, _, folders = _download(final_url="https://evil.example/x.rpm")
    assert done == [] and folders == []
    assert errors == ["Download redirected to an untrusted host"]


@pytest.mark.parametrize("url, digest, error", [
    ("https://evil.example/x.rpm", DIGEST, "untrusted download URL"),
    (ASSET_URL, "", "checksum"),
])
def test_refuses_before_downloading(url, digest, error):
    done, errors, urlopen, _ = _download(url=url, digest=digest)
    urlopen.assert_not_called()
    assert done == [] and error in errors[0]


def test_oversized_download_is_refused():
    with patch.object(AppUpdateDownloadWorker, "MAX_BYTES", 4):
        done, errors, _, folders = _download()
    assert done == [] and folders == []
    assert "unexpectedly large" in errors[0]


# ── installing it ────────────────────────────────────────────────────

def _offer(app, sha256=DIGEST, url=ASSET_URL):
    info = SimpleNamespace(latest_version="2.0.1", download_url=url, sha256=sha256,
                           release_url="", release_notes="")
    app._on_app_update_checked(info)
    return info


def test_install_needs_a_digest(app):
    _offer(app, sha256="")
    assert app.appUpdate["available"] and not app.appUpdate["canInstall"]
    _offer(app)
    assert app.appUpdate["canInstall"]


def test_install_asks_first(app):
    shown = answer(app, "no")
    _offer(app)
    with patch("dnf_gui.ui.controllers.app_controller.AppUpdateDownloadWorker") as worker:
        app.installAppUpdate()
    assert shown[-1].title == "Install Version 2.0.1?"
    worker.assert_not_called()


def test_downloaded_file_is_installed_with_the_published_digest(app):
    _offer(app)
    app.runner.start_external("Downloading app update", None)
    with patch.object(app.runner, "run") as run:
        app._on_update_downloaded("/tmp/dnf-gui-update-x/update.rpm")
    run.assert_called_once_with(
        build_verified_install_command("/tmp/dnf-gui-update-x/update.rpm", DIGEST,
                                       app.backend.dnf_path),
        "Installing app update")


def test_no_rescan_after_installing_the_app_update(app):
    answer(app, "no")  # decline "Restart App"
    with patch.object(app, "refreshCurrent") as refresh:
        app._on_operation_finished(0, "Installing app update", False)
    refresh.assert_not_called()


# ── the root-side check (run here as this user, without pkexec) ──────

def _run_verified_script(path, digest=DIGEST, dnf="/usr/bin/dnf5"):
    """The refusal paths all exit before dnf would run."""
    return subprocess.run([sys.executable, "-I", "-c", VERIFIED_INSTALL_SCRIPT,
                           str(path), digest, dnf], capture_output=True, text=True, timeout=20)


def test_install_command_passes_data_never_shell_text():
    argv = build_verified_install_command("/tmp/x.rpm", DIGEST, "/usr/bin/dnf5")
    assert argv[:4] == ["pkexec", "/usr/bin/python3", "-I", "-c"]
    assert argv[-3:] == ["/tmp/x.rpm", DIGEST, "/usr/bin/dnf5"]


def test_root_check_refuses_a_swapped_file_or_bad_arguments(tmp_path):
    rpm = tmp_path / "update.rpm"
    rpm.write_bytes(b"something else")
    swapped = _run_verified_script(rpm)
    assert swapped.returncode == 3 and "changed after it was checked" in swapped.stdout
    assert _run_verified_script(rpm, digest="").returncode == 2
    assert _run_verified_script(rpm, dnf="/home/me/.local/bin/dnf").returncode == 2


def test_root_copy_refuses_symlinks_devices_fifos_and_huge_files(tmp_path):
    real = tmp_path / "real.rpm"
    real.write_bytes(RPM)
    link = tmp_path / "link.rpm"
    link.symlink_to(real)                       # even to a matching file
    dev = tmp_path / "zero.rpm"
    dev.symlink_to("/dev/zero")
    fifo = tmp_path / "fifo.rpm"
    os.mkfifo(fifo)
    huge = tmp_path / "huge.rpm"
    with open(huge, "wb") as f:
        f.truncate(101 * 1024 * 1024)           # sparse: costs no disk
    for path in (link, dev, fifo, huge, tmp_path / "missing.rpm"):
        result = _run_verified_script(path)
        assert result.returncode == 3, (path, result.stdout, result.stderr)
        assert "Refusing" in result.stdout
