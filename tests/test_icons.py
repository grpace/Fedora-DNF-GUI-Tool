"""The bundled icon set, the colored copies QML loads, and the AppStream app icons."""

import gzip
import re
from pathlib import Path

from dnf_gui.core import appicons
from dnf_gui.ui.iconset import ICON_DIR, IconSet

QML_DIR = Path(__file__).resolve().parents[1] / "src" / "dnf_gui" / "ui" / "qml"


def test_every_icon_the_qml_names_is_bundled():
    shipped = {p.stem for p in ICON_DIR.glob("*.svg")}
    used = set()
    for qml in QML_DIR.glob("*.qml"):
        text = qml.read_text()
        for call in re.findall(r"root\.ico\(([^;\n]*)", text):
            used.update(re.findall(r'"([a-z][a-z0-9-]*)"', call))
        # Sidebar entries and info cards pass names through iconName.
        used.update(re.findall(r'iconName: "([a-z][a-z0-9-]*)"', text))
        used.update(re.findall(r'icon: "([a-z][a-z0-9-]*)"', text))
    missing = sorted(used - shipped)
    assert not missing, missing
    assert (ICON_DIR / "LICENSE").read_text().startswith("MIT License")


def test_icons_are_written_in_the_requested_color(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    icons = IconSet()
    base = icons.base_url("#FFAA00")
    folder = Path(base.removeprefix("file://"))
    svg = (folder / "download.svg").read_text()
    assert 'fill="#ffaa00"' in svg and "currentColor" not in svg
    assert icons.base_url("#ffaa00") == base            # made once per color
    assert icons.base_url("not a color").endswith("/000000/")
    icons.cleanup()
    assert not folder.exists()


def test_appstream_catalog_maps_packages_to_icons(tmp_path):
    root = tmp_path / "swcatalog"
    (root / "xml").mkdir(parents=True)
    (root / "icons" / "fedora" / "64x64").mkdir(parents=True)
    (root / "icons" / "fedora" / "64x64" / "org.mozilla.firefox.png").write_bytes(b"png")
    xml = b"""<?xml version="1.0"?>
<components origin="fedora">
  <component type="desktop-application"><id>org.mozilla.firefox</id>
    <pkgname>firefox</pkgname><icon type="cached" width="64">org.mozilla.firefox.png</icon></component>
  <component type="addon"><id>x</id><pkgname>libheif</pkgname></component>
  <component type="desktop-application"><id>org.gimp.GIMP.desktop</id><pkgname>gimp</pkgname>
    <icon type="cached" width="64">../../../etc/passwd</icon></component>
</components>"""
    (root / "xml" / "fedora.xml.gz").write_bytes(gzip.compress(xml))
    icons = appicons.load_app_icons((str(root),))
    assert icons["firefox"]["file"].endswith("64x64/org.mozilla.firefox.png")
    assert icons["firefox"]["theme"] == "org.mozilla.firefox"
    assert "libheif" not in icons                       # not an app
    assert icons["gimp"] == {"theme": "org.gimp.GIMP", "file": ""}  # no path tricks
