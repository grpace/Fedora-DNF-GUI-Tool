"""Which packages are apps, and their icons, from the AppStream catalogs.

Fedora's ``appstream-data`` (and RPM Fusion's) list every desktop app with
the packages it comes from and a cached icon. Rows for those packages show
the app's icon instead of a generic package. Reading the catalogs takes
under a second; run it off the UI thread.
"""

from __future__ import annotations

import gzip
import os
import xml.etree.ElementTree as ET

CATALOG_ROOTS = ("/usr/share/swcatalog", "/var/cache/swcatalog")
APP_TYPES = ("desktop-application", "desktop", "console-application")


def _catalog_files(root: str) -> list[str]:
    xml_dir = os.path.join(root, "xml")
    try:
        names = sorted(os.listdir(xml_dir))
    except OSError:
        return []
    return [os.path.join(xml_dir, n) for n in names
            if n.endswith(".xml") or n.endswith(".xml.gz")]


def _icon_file(root: str, origin: str | None, name: str | None) -> str:
    """The largest cached copy of an icon that exists, else ""."""
    if not origin or not name or "/" in name or "/" in origin:
        return ""
    for size in ("128x128", "64x64"):
        path = os.path.join(root, "icons", origin, size, name)
        if os.path.isfile(path):
            return path
    return ""


def parse_catalog(path: str, root: str, icons: dict[str, dict]) -> None:
    """Add ``{package: {"theme": name, "file": path}}`` entries from one
    catalog file to ``icons`` (first entry for a package wins)."""
    opener = gzip.open if path.endswith(".gz") else open
    origin = None
    with opener(path, "rb") as f:
        for event, el in ET.iterparse(f, events=("start", "end")):
            if event == "start":
                if el.tag == "components":
                    origin = el.get("origin")
                continue
            if el.tag != "component":
                continue
            if el.get("type") in APP_TYPES:
                theme, cached = "", ""
                for icon in el.findall("icon"):
                    kind = icon.get("type")
                    if kind == "stock" and not theme:
                        theme = (icon.text or "").strip()
                    elif kind == "cached" and not cached:
                        cached = (icon.text or "").strip()
                component_id = (el.findtext("id") or "").strip()
                if not theme and component_id:
                    theme = component_id.removesuffix(".desktop")
                entry = {"theme": theme, "file": _icon_file(root, origin, cached)}
                if entry["theme"] or entry["file"]:
                    for pkg in el.findall("pkgname"):
                        name = (pkg.text or "").strip()
                        if name and name not in icons:
                            icons[name] = entry
            el.clear()


def load_app_icons(roots: tuple[str, ...] = CATALOG_ROOTS) -> dict[str, dict]:
    icons: dict[str, dict] = {}
    for root in roots:
        for path in _catalog_files(root):
            try:
                parse_catalog(path, root, icons)
            except (OSError, ET.ParseError, EOFError):
                continue
    return icons
