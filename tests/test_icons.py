"""Icons: the bundled set and every name the UI asks for, the colored
copies QML loads, the AppStream app icons, and AppIcon.qml (an app's own
icon, or a tinted letter tile)."""

import gzip
import importlib.util
import re
from pathlib import Path

import pytest

from dnf_gui.core import appicons
from dnf_gui.ui.iconset import ICON_DIR, IconSet
from tests.conftest import by_name, evaluate, find_items, spin, wait_until

ROOT = Path(__file__).resolve().parents[1]
QML_DIR = ROOT / "src" / "dnf_gui" / "ui" / "qml"
CONTROLLERS = ROOT / "src" / "dnf_gui" / "ui" / "controllers"

NAME = r'"([a-z][a-z0-9-]*)"'
# A name in a result position: the whole value, a ternary branch, or what
# a function block returns (not an argument such as indexOf("install")).
RESULT = re.compile(r'(?:^|[?:]|\breturn)\s*' + NAME)
ICON_PROPERTY = re.compile(r'\b(?:iconName|icon|actionIcon)\s*:(?!\s*root\.ico)')


def _expression(text: str, start: int) -> str:
    """The QML/JS value that starts at ``start``: up to a newline (unless
    the next line continues it with an operator), a comma or a closing
    bracket at depth 0, with brackets balanced."""
    depth, i = 0, start
    while i < len(text):
        ch = text[i]
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            if depth == 0:
                break
            depth -= 1
        elif ch == '"':
            i = text.index('"', i + 1)
        elif depth == 0 and ch == ",":
            break
        elif depth == 0 and ch == "\n":
            rest = text[i + 1:].lstrip(" ")
            if rest[:1] not in ("?", ":", "+", "|", "&"):
                break
        i += 1
    return text[start:i]


def icon_names_in_qml(text: str) -> set[str]:
    used = set()
    for call in re.findall(r"root\.ico\(([^;\n]*)", text):
        used.update(re.findall(NAME, call))
    for match in ICON_PROPERTY.finditer(text):
        used.update(RESULT.findall(_expression(text, match.end()).strip()))
    return used


def icon_names_in_python(text: str) -> set[str]:
    return set(re.findall(r'"(?:icon|iconName|actionIcon)":\s*' + NAME, text))


def test_every_icon_the_ui_names_is_bundled():
    shipped = {p.stem for p in ICON_DIR.glob("*.svg")}
    used = set()
    for qml in QML_DIR.glob("*.qml"):
        used |= icon_names_in_qml(qml.read_text())
    for py in CONTROLLERS.glob("*.py"):
        used |= icon_names_in_python(py.read_text())
    # Names only reachable through a ternary, a block or Python are seen.
    assert {"window-restore", "window-maximize", "view-refresh", "user-identity",
            "flatpak-discover", "security-high", "edit-clear-all", "go-down",
            "list-add", "arrow-up", "package-x-generic"} <= used
    missing = sorted(used - shipped)
    assert not missing, missing
    assert (ICON_DIR / "LICENSE").read_text().startswith("MIT License")


def test_the_scan_reads_ternaries_and_blocks_but_not_arguments():
    qml = '''
        iconName: row.id === "add_flathub" ? "flatpak-discover"
                : row.id.indexOf("firmware") === 0 ? "cpu"
                : "view-refresh"
        readonly property string actionIcon: {
            if (a.indexOf("install") >= 0) return "list-add";
            return "system-software-update";
        }
        { key: "x", icon: "computer", fallback: "folder-flatpak" }
        icon.source: root.ico(open ? "arrow-up" : "arrow-down", enabled)
    '''
    assert icon_names_in_qml(qml) == {"flatpak-discover", "cpu", "view-refresh", "list-add",
                                      "system-software-update", "computer", "arrow-up",
                                      "arrow-down"}


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


def test_app_icon_lookup_returns_a_copy(app):
    app._on_app_icons({"firefox": {"theme": "org.mozilla.firefox", "file": ""}})
    info = app.appIcon("firefox")
    info["theme"] = "changed"
    assert app.appIcon("firefox") == {"theme": "org.mozilla.firefox", "file": ""}
    assert app.appIcon("libheif") == {}


# ── AppIcon.qml ──────────────────────────────────────────────────────

def _tile_colors() -> list[str]:
    source = (QML_DIR / "AppIcon.qml").read_text()
    listed = re.search(r"tileColors:\s*\[([^\]]*)\]", source).group(1)
    return re.findall(r'"(#[0-9a-fA-F]{6})"', listed)


TILE_COLORS = _tile_colors()


def _contrast_script():
    spec = importlib.util.spec_from_file_location("check_contrast",
                                                  ROOT / "scripts" / "check_contrast.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _rgb(hex_color: str):
    return tuple(int(hex_color[i:i + 2], 16) for i in (1, 3, 5))


def test_tile_colors_carry_white_letters_at_wcag_aa():
    """AppIcon.qml's letter is white on one of these (check_contrast.py's
    contrast formula)."""
    contrast = _contrast_script().contrast
    assert len(TILE_COLORS) == 8
    for color in TILE_COLORS:
        assert contrast((255, 255, 255), _rgb(color)) >= 4.5, color


def _tint(name: str) -> str:
    """AppIcon.qml's tint, in Python: a stable hash of the name."""
    h = 0
    for ch in name:
        h = (h * 31 + ord(ch)) % 9973
    return TILE_COLORS[h % len(TILE_COLORS)]


@pytest.fixture
def make_icon(ui):
    """``make_icon(**props)``: an AppIcon.qml in the loaded window."""
    from PyQt6.QtCore import QUrl
    from PyQt6.QtQml import QQmlComponent, QQmlEngine
    controller, window, problems = ui
    assert wait_until(lambda: controller.appIconsReady)  # the stubbed catalog: firefox
    # The theme has these icons, whatever this machine's theme has.
    controller._theme_icons.update({"org.mozilla.firefox": True, "org.kde.kdenlive": True,
                                    "org.example.Missing": False})
    context = QQmlEngine.contextForObject(window)
    component = QQmlComponent(context.engine(), QUrl.fromLocalFile(str(QML_DIR / "AppIcon.qml")))
    made = []

    def make(**props):
        icon = component.createWithInitialProperties(props, context)
        assert icon is not None, component.errorString()
        icon.setParentItem(window.contentItem())
        made.append(icon)
        spin(50)
        return icon
    yield make, problems
    for icon in made:
        icon.deleteLater()


def _parts(icon):
    image = [i for i in icon.childItems() if i.objectName() == "appIconImage"][0]
    tile = [i for i in icon.childItems() if i.objectName() == "letterTile"][0]
    return image, tile


def test_an_app_shows_its_own_icon(make_icon):
    make, problems = make_icon
    icon = make(name="firefox")
    image, tile = _parts(icon)
    assert image.property("source") == "org.mozilla.firefox"
    assert image.isVisible() and not tile.isVisible()
    assert problems() == []


@pytest.mark.parametrize("name, letter", [("libheif", "L"), ("7zip", "7"),
                                          ("_x-lib", "X"), ("+++", "?")])
def test_anything_else_gets_a_tinted_letter_tile(make_icon, name, letter):
    make, problems = make_icon
    icon = make(name=name)
    image, tile = _parts(icon)
    assert not image.isVisible() and tile.isVisible()
    assert icon.property("letter") == letter
    assert evaluate(icon, "tint.toString()") == _tint(name)
    assert tile.property("color").name() == _tint(name)
    assert evaluate(icon, "tileColors.join(',')") == ",".join(TILE_COLORS)
    assert problems() == []


def test_the_tint_is_stable_and_spread(make_icon):
    make, problems = make_icon
    names = ["bash", "git", "htop", "libheif", "vim-enhanced", "zsh", "python3", "kernel-core"]
    tints = [evaluate(make(name=n), "tint.toString()") for n in names]
    assert tints == [_tint(n) for n in names]
    assert len(set(tints)) >= 4
    assert problems() == []


def test_flatpak_app_id_wins_over_the_package_name(make_icon):
    make, problems = make_icon
    icon = make(name="firefox", appId="org.kde.kdenlive")
    image, tile = _parts(icon)
    assert icon.property("themeName") == "org.kde.kdenlive"
    assert icon.property("iconFile") == ""
    assert image.property("source") == "org.kde.kdenlive" and image.isVisible()
    # An id the theme lacks gets the tile, never an empty space.
    image, tile = _parts(make(name="Missing App", appId="org.example.Missing"))
    assert not image.isVisible() and tile.isVisible()
    assert problems() == []


def test_a_runtime_shows_the_shared_library_glyph(make_icon):
    make, problems = make_icon
    icon = make(name="KDE Application Platform", appId="org.kde.Platform", runtime=True)
    image, tile = _parts(icon)
    assert image.property("source").endswith("/application-x-sharedlib.svg")
    assert image.isVisible() and not tile.isVisible()
    assert problems() == []


def test_update_rows_use_app_icons(ui):
    """The Updates list draws its rows with AppIcon (not a generic box)."""
    from dnf_gui.core.package import Package, PackageStatus, UpdateInfo
    controller, window, problems = ui
    assert wait_until(lambda: controller.appIconsReady)
    controller._theme_icons["org.mozilla.firefox"] = True
    pkgs = [Package(n, "2", "1.fc45", "x86_64", "updates", status=PackageStatus.UPDATE_AVAILABLE,
                    installed_version="1-1.fc45") for n in ("firefox", "libheif")]
    controller.updates._on_checked({"dnf": UpdateInfo(2, pkgs), "flatpak": [], "security": None})
    assert wait_until(lambda: len(find_items(window, lambda i: i.objectName() == "letterTile"
                                             and i.isVisible())) >= 1)
    images = find_items(window, lambda i: i.objectName() == "appIconImage" and i.isVisible())
    assert [i.property("source") for i in images] == ["org.mozilla.firefox"]
    assert by_name(window, "windowControls")  # the window is the real one
    assert problems() == []


def test_one_app_icon_is_used_everywhere():
    """The app icon lives once, in the package; every installer, the README
    and the interface use that file (no stale copies)."""
    from pathlib import Path

    from PyQt6.QtSvg import QSvgRenderer
    from dnf_gui.ui.window import APP_ICON

    repo = Path(__file__).resolve().parents[1]
    assert APP_ICON == repo / "src" / "dnf_gui" / "ui" / "app_icon.svg"
    assert QSvgRenderer(str(APP_ICON)).isValid()
    assert "cp src/%{app_module}/ui/app_icon.svg" in (repo / "packaging" / "dnf-gui.spec").read_text()
    assert 'cp "src/dnf_gui/ui/app_icon.svg"' in (repo / "install.sh").read_text()
    assert 'src="src/dnf_gui/ui/app_icon.svg"' in (repo / "README.md").read_text()
    assert "app_icon.svg" in (repo / "pyproject.toml").read_text()
    qml = repo / "src" / "dnf_gui" / "ui" / "qml"
    assert 'Qt.resolvedUrl("../app_icon.svg")' in (qml / "Main.qml").read_text()
    for page in ("Sidebar.qml", "SettingsPage.qml"):
        assert "source: root.appIcon" in (qml / page).read_text(), page
    stale = [p for p in repo.rglob("app_icon*.svg")
             if p != APP_ICON and ".git" not in p.parts and "prototypes" not in p.parts]
    assert not stale, stale
