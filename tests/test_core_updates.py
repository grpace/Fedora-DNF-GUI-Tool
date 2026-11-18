"""Core updates and "Update Without Core": which packages count as core
(kernel, drivers, firmware, bootloader), marking a package as core, the
upgrade that holds them back, and the word users see for them.

The code still says "major" (held-back patterns, row fields); everything
a user reads says "Core".
"""

import ast
import re
import unittest
from pathlib import Path
from unittest.mock import patch

import pytest

from dnf_gui.core.dnf_backend import (
    DEFAULT_HELD_BACK_PATTERNS, DNFBackend, is_held_back,
    parse_held_back_patterns,
)
from dnf_gui.core.flatpak_backend import FlatpakApp
from dnf_gui.core.package import Package, PackageStatus, UpdateInfo, UpgradePreview
from dnf_gui.core.security import SecuritySummary
from tests.conftest import answer, make_backend

SRC = Path(__file__).resolve().parents[1] / "src" / "dnf_gui"


def _info(*names):
    return UpdateInfo(packages=[
        Package(name=n, version="1", status=PackageStatus.UPDATE_AVAILABLE)
        for n in names])


class TestHeldBackMatching(unittest.TestCase):
    def test_defaults_hold_back_core_packages(self):
        for name in ("kernel", "kernel-core", "kernel-modules-extra",
                     "linux-firmware", "amd-gpu-firmware", "akmod-nvidia",
                     "xorg-x11-drv-nvidia-libs", "nvidia-settings",
                     "mesa-dri-drivers", "grub2-efi-x64", "shim-x64"):
            self.assertTrue(is_held_back(name, DEFAULT_HELD_BACK_PATTERNS), name)

    def test_defaults_let_regular_packages_through(self):
        for name in ("firefox", "kmod", "kmod-libs", "glibc", "systemd",
                     "xorg-x11-drv-libinput", "plasma-desktop"):
            self.assertFalse(is_held_back(name, DEFAULT_HELD_BACK_PATTERNS), name)

    def test_parse_patterns(self):
        valid, invalid = parse_held_back_patterns(
            "kernel*, mesa-*\n*nvidia*  kernel*, bad;rm, --all")
        self.assertEqual(valid, ["kernel*", "mesa-*", "*nvidia*"])
        self.assertEqual(invalid, ["bad;rm", "--all"])


class TestCommand(unittest.TestCase):
    def test_builds_plain_dnf_upgrade_with_excludes(self):
        cmd = make_backend().build_upgrade_without_major_command(["kernel*", "mesa-*"])
        self.assertEqual(cmd, ["pkexec", "/usr/bin/dnf5", "upgrade", "-y", "--refresh",
                               "--exclude=kernel*,mesa-*"])

    def test_drops_unsafe_patterns(self):
        cmd = make_backend().build_upgrade_without_major_command(
            ["kernel*", "--setopt=x", "a b"])
        self.assertEqual(cmd[-1], "--exclude=kernel*")


class TestPreviewFiltering(unittest.TestCase):
    def test_excluding_recomputes_count_and_size(self):
        output = ("firefox 125.0-1.fc44 x86_64 1000\n"
                  "kernel-core 6.18.5-200.fc44 x86_64 5000\n"
                  "mesa-libGL 25.1-1.fc44 x86_64 300\n")
        with patch.object(DNFBackend, "_run", return_value=output):
            preview = make_backend().get_upgrade_preview()
        self.assertEqual(preview.count, 3)
        minor = preview.excluding(DEFAULT_HELD_BACK_PATTERNS)
        self.assertEqual((minor.count, minor.total_bytes, minor.sizes_known), (1, 1000, True))

    def test_excluding_everything_has_no_preview(self):
        preview = UpgradePreview(count=1, total_bytes=5, sizes_known=True,
                                 entries=[("kernel", 5)])
        self.assertFalse(preview.excluding(["kernel*"]).has_preview)


# ── the Updates page ─────────────────────────────────────────────────

@pytest.fixture
def core(app):
    """The app with the default core patterns; ``core.scan(*names)``."""
    app.settings.held_back_patterns = list(DEFAULT_HELD_BACK_PATTERNS)
    app.updates.set_held_back_patterns(list(DEFAULT_HELD_BACK_PATTERNS))
    app.scan = lambda *names: app.updates._on_checked(
        {"dnf": _info(*names), "flatpak": [], "security": None})
    return app


def _minor_enabled(app):
    return next(m for m in app.updates.modes if m["key"] == "minor")["enabled"]


class TestUpdateWithoutCore:
    def test_enabled_only_when_non_core_updates_pending(self, core):
        core.scan("kernel", "kernel-core", "mesa-libGL")
        assert not _minor_enabled(core)
        assert core.updates.held_back_package_names() == ["kernel", "kernel-core", "mesa-libGL"]
        core.scan("kernel", "firefox")
        assert _minor_enabled(core)
        assert core.updates.minor_package_names() == ["firefox"]

    def test_custom_patterns_update_the_button(self, core):
        core.scan("firefox")
        assert _minor_enabled(core)
        core.updates.set_held_back_patterns(["firefox"])
        assert not _minor_enabled(core)

    def test_nothing_pending_disables(self, core):
        core.scan()
        assert not _minor_enabled(core)

    def test_confirm_lists_skipped_packages_and_runs_exact_command(self, core):
        core.scan("kernel-core", "firefox")
        shown = answer(core, "yes")
        with patch.object(core.runner, "run") as run:
            core.updates.upgrade_without_major()
        assert "Core updates skipped (1): kernel-core." in shown[0].text
        run.assert_called_once_with(
            core.backend.build_upgrade_without_major_command(list(DEFAULT_HELD_BACK_PATTERNS)),
            "Update Without Core")

    def test_rows_are_tagged_with_why_they_are_core(self, core):
        core.scan("kernel-core", "firefox")
        model = core.updates.model
        assert {r["name"]: r["major"] for r in model.rows()} == {"kernel-core": True,
                                                                "firefox": False}
        assert core.updates.majorCount == 1
        mode = next(m for m in core.updates.modes if m["key"] == "minor")
        assert "skips 1 core" in mode["detail"]
        reason = model.find("name", "kernel-core")["majorReason"]
        assert "kernel*" in reason and "Update Without Core skips it" in reason


class TestMarkingCore:
    def test_row_button_toggles_core(self, core):
        core.scan("firefox", "kernel-core")
        model = core.updates.model
        firefox = model.find("name", "firefox")
        assert firefox["majorActionLabel"] == "Treat as Core"
        assert firefox["canToggleMajor"]
        assert not model.find("name", "kernel-core")["canToggleMajor"]  # kernel* covers it

        core.updates.toggleMajor("firefox")
        assert "firefox" in core.settings.held_back_patterns
        firefox = model.find("name", "firefox")
        assert firefox["major"]
        assert firefox["majorActionLabel"] == "Don't Treat as Core"
        assert "You marked this as core" in firefox["majorReason"]

        core.updates.toggleMajor("firefox")
        assert "firefox" not in core.settings.held_back_patterns
        assert not model.find("name", "firefox")["major"]

    def test_toggle_hold_saves_and_updates_the_page(self, core):
        core.settings_controller.toggle_hold("firefox", True)
        assert "firefox" in core.settings.held_back_patterns
        assert "firefox" in core.updates.held_back_patterns
        core.settings_controller.toggle_hold("firefox", False)
        assert "firefox" not in core.settings.held_back_patterns
        assert "firefox" not in core.updates.held_back_patterns

    def test_saving_patterns_updates_rows_and_settings(self, core):
        from dnf_gui.core import passwordless as pw
        core.scan("firefox")
        with patch.object(pw, "live_status", return_value=("off", False, True)):
            core.settings_controller.saveHeldBack("kernel*, firefox")
        assert core.settings.held_back_patterns == ["kernel*", "firefox"]
        assert not _minor_enabled(core)
        assert core.updates.model.find("name", "firefox")["major"]

    def test_invalid_patterns_are_not_saved(self, core):
        shown = answer(core)
        core.settings_controller.saveHeldBack("kernel*, bad;rm")
        assert shown[-1].title == "Invalid Patterns"
        assert "bad;rm" in shown[-1].text
        assert core.settings.held_back_patterns == list(DEFAULT_HELD_BACK_PATTERNS)


# ── the word users read is "Core", never "Major" ─────────────────────

MAJOR = re.compile(r"\bmajor\b", re.IGNORECASE)
KEY = re.compile(r"[a-z_][A-Za-z0-9_]*")
QML_TOKENS = re.compile(r'"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\'|//[^\n]*|/\*.*?\*/', re.S)


def _qml_strings(path: Path) -> list[str]:
    return [t[1:-1] for t in QML_TOKENS.findall(path.read_text()) if t[0] in "\"'"]


def _python_strings(path: Path) -> list[str]:
    tree = ast.parse(path.read_text())
    docstrings = {id(node.value) for node in ast.walk(tree)
                  if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)}
    return [node.value for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
            and id(node) not in docstrings]


def _says_major(text: str) -> bool:
    # A lowercase key ("major": a role or filter key) is code, not text.
    return bool(MAJOR.search(text)) and not KEY.fullmatch(text)


def test_no_user_facing_string_literal_says_major():
    found = []
    for path in sorted((SRC / "ui" / "qml").glob("*.qml")):
        found += [(path.name, s) for s in _qml_strings(path) if _says_major(s)]
    for path in sorted(SRC.rglob("*.py")):
        found += [(path.name, s) for s in _python_strings(path) if _says_major(s)]
    assert found == []


def test_the_scan_finds_a_string_that_says_major(tmp_path):
    """The scan above would catch one (not a scan that sees nothing)."""
    qml = tmp_path / "X.qml"
    qml.write_text('// Major in a comment is fine\nLabel { text: "Major Updates"; '
                   'property string k: "major"; property var c: ({ label: "Major" }) }\n')
    assert [s for s in _qml_strings(qml) if _says_major(s)] == ["Major Updates", "Major"]
    py = tmp_path / "x.py"
    py.write_text('"""Major docstring."""\nTITLE = f"{3} major updates"\nKEY = "major"\n')
    assert [s for s in _python_strings(py) if _says_major(s)] == [" major updates"]


def test_no_text_on_the_updates_page_says_major(core):
    core.updates._on_checked({
        "dnf": _info("kernel-core", "firefox", "libheif"),
        "flatpak": [FlatpakApp(name="Kdenlive", application_id="org.kde.kdenlive")],
        "security": SecuritySummary(total=1, package_severity={"libheif": "important"})})
    updates = core.updates
    shown = answer(core, "no", "no", "no", "no")
    for action in ("upgrade_without_major", "upgrade_all", "update_everything",
                   "security_upgrade"):
        getattr(updates, action)()
    texts = [updates.headline, updates.summary]
    for mode in updates.modes:
        texts += [str(v) for v in mode.values() if isinstance(v, str)]
    for row in updates.model.rows():
        texts += [row[k] for k in ("majorReason", "majorActionLabel", "majorTooltip",
                                   "tooltip", "section") if isinstance(row.get(k), str)]
    for prompt in shown:
        texts += [prompt.title, prompt.text, *[label for _, label in prompt.buttons]]
    assert len(shown) == 4
    assert [t for t in texts if MAJOR.search(t)] == []
