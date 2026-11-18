"""The version lives in five places and they must agree (AGENTS.md): miss
``src/dnf_gui/__init__.py`` and installed copies keep offering the same
update forever, because the self-updater compares against it."""

import re
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

import dnf_gui

ROOT = Path(__file__).resolve().parents[1]


def _spec() -> str:
    return (ROOT / "packaging" / "dnf-gui.spec").read_text()


def versions() -> dict[str, str]:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    spec = _spec()
    changelog = spec.split("%changelog", 1)[1]
    releases = ET.parse(ROOT / "packaging" / "dnf-gui.metainfo.xml").getroot().find("releases")
    headings = re.findall(r"^## \[(\d[^\]]*)\]", (ROOT / "CHANGELOG.md").read_text(), re.M)
    return {
        "pyproject.toml": pyproject["project"]["version"],
        "src/dnf_gui/__init__.py": dnf_gui.__version__,
        "dnf-gui.spec Version": re.search(r"^Version:\s*(\S+)", spec, re.M).group(1),
        "dnf-gui.spec %changelog": re.search(r"^\*.* - (\S+?)-\d+\s*$", changelog, re.M).group(1),
        "metainfo newest <release>": releases.find("release").get("version"),
        "CHANGELOG.md newest heading": headings[0],
    }


def test_every_place_has_the_same_version():
    found = versions()
    assert len(set(found.values())) == 1, found


def test_newest_entries_come_first():
    """"Newest" above means first: each list is newest-first."""
    from dnf_gui.core.updater import _version_compare
    releases = ET.parse(ROOT / "packaging" / "dnf-gui.metainfo.xml").getroot().find("releases")
    meta = [r.get("version") for r in releases.findall("release")]
    headings = re.findall(r"^## \[(\d[^\]]*)\]", (ROOT / "CHANGELOG.md").read_text(), re.M)
    spec = re.findall(r"^\*.* - (\S+?)-\d+\s*$", _spec().split("%changelog", 1)[1], re.M)
    for name, listed in (("metainfo", meta), ("CHANGELOG.md", headings), ("spec", spec)):
        assert len(listed) >= 2, name
        for newer, older in zip(listed, listed[1:]):
            assert _version_compare(newer, older) > 0, (name, newer, older)
