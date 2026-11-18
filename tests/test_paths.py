"""Where the app finds the programs it runs: system directories only,
never ``$PATH`` (a planted ``~/.local/bin/dnf`` would run as root once the
user types their password). The directories here are fixtures."""

import pytest

from dnf_gui.core import paths
from tests.conftest import REAL_FIND_SYSTEM_BINARY


@pytest.fixture
def system(tmp_path, monkeypatch):
    """Two fake system directories, searched in order, and the real lookup."""
    first, second = tmp_path / "usr-bin", tmp_path / "usr-sbin"
    first.mkdir()
    second.mkdir()
    monkeypatch.setattr(paths, "SYSTEM_DIRS", (str(first), str(second)))
    monkeypatch.setattr(paths, "find_system_binary", REAL_FIND_SYSTEM_BINARY)
    return first, second


def _program(folder, name, mode=0o755):
    path = folder / name
    path.write_text("#!/bin/sh\n")
    path.chmod(mode)
    return str(path)


def test_finds_an_executable_in_a_system_directory(system):
    first, second = system
    sudo = _program(second, "sudo")
    assert paths.find_system_binary("sudo") == sudo
    assert paths.find_system_binary("missing") is None


def test_skips_files_that_are_not_executable_and_directories(system):
    first, second = system
    _program(first, "dnf5", mode=0o644)
    (first / "flatpak").mkdir()
    assert paths.find_system_binary("dnf5") is None
    assert paths.find_system_binary("flatpak") is None
    dnf5 = _program(second, "dnf5")
    assert paths.find_system_binary("dnf5") == dnf5


def test_names_are_tried_in_order_then_directories(system):
    first, second = system
    dnf = _program(first, "dnf")
    dnf5 = _program(second, "dnf5")
    # dnf5 wins even though dnf sits in an earlier directory.
    assert paths.find_system_binary("dnf5", "dnf") == dnf5
    assert paths.find_system_binary("dnf", "dnf5") == dnf
    earlier = _program(first, "dnf5")
    assert paths.find_system_binary("dnf5") == earlier


def test_never_looks_in_path(system, tmp_path, monkeypatch):
    planted = tmp_path / "home-bin"
    planted.mkdir()
    _program(planted, "dnf5")
    monkeypatch.setenv("PATH", f"{planted}:/usr/bin")
    assert paths.find_system_binary("dnf5") is None


def test_system_binary_falls_back_to_an_absolute_path(system):
    first, _ = system
    assert paths.system_binary("dnf5", "dnf") == "/usr/bin/dnf5"
    dnf = _program(first, "dnf")
    assert paths.system_binary("dnf5", "dnf") == dnf


def test_privileged_programs_never_come_from_path(system, tmp_path, monkeypatch):
    """A dnf planted earlier in $PATH (e.g. ~/.local/bin) is never used."""
    from dnf_gui.core import passwordless
    from dnf_gui.core.dnf_backend import DNFBackend
    from dnf_gui.core.flatpak_backend import FlatpakBackend
    from dnf_gui.core.security import build_security_update_command
    first, _ = system
    monkeypatch.setattr(passwordless, "find_system_binary", REAL_FIND_SYSTEM_BINARY)
    planted = tmp_path / "home-bin"
    planted.mkdir()
    for name in ("dnf5", "flatpak", "sudo"):
        _program(planted, name)
    monkeypatch.setenv("PATH", f"{planted}:/usr/bin")
    real = {name: _program(first, name) for name in ("dnf5", "flatpak", "sudo")}
    assert DNFBackend().dnf_path == real["dnf5"]
    assert build_security_update_command()[1] == real["dnf5"]
    assert FlatpakBackend()._flatpak == real["flatpak"]
    cmd = ["pkexec", "/usr/bin/dnf5", "upgrade", "-y", "--refresh"]
    assert passwordless.maybe_passwordless(cmd, "updates")[0] == real["sudo"]
