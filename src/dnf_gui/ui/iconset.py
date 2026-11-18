"""The app's own bold icons (Phosphor, in ``ui/icons``), in the theme's colors.

Plasma only recolors icons that come from the icon theme; buttons draw any
other SVG exactly as written. So each icon is written out once per text color
the interface asks for, into a private temporary directory, and QML points
at that copy (``Main.qml``'s ``ico()``). A color scheme change asks for a new
color, which gets its own directory.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from pathlib import Path

from PyQt6.QtCore import QUrl

ICON_DIR = Path(__file__).with_name("icons")
_FILL = 'fill="currentColor"'
_HEX = re.compile(r"^#[0-9a-f]{6}$")


class IconSet:
    def __init__(self, source: Path = ICON_DIR):
        self._source = source
        self._sources = {p.stem: p.read_text(encoding="utf-8")
                         for p in sorted(source.glob("*.svg"))}
        self._root: str | None = None
        self._bases: dict[str, str] = {}

    def names(self) -> list[str]:
        return list(self._sources)

    def base_url(self, color: str) -> str:
        """``file://…/`` directory holding every icon filled with ``color``
        (``#rrggbb``; anything else falls back to black)."""
        color = color.lower() if _HEX.match(color.lower()) else "#000000"
        if color not in self._bases:
            directory = os.path.join(self._ensure_root(), color[1:])
            os.makedirs(directory, exist_ok=True)
            for name, svg in self._sources.items():
                Path(directory, name + ".svg").write_text(
                    svg.replace(_FILL, f'fill="{color}"'), encoding="utf-8")
            self._bases[color] = QUrl.fromLocalFile(directory).toString() + "/"
        return self._bases[color]

    def _ensure_root(self) -> str:
        if self._root is None or not os.path.isdir(self._root):
            parent = os.environ.get("XDG_RUNTIME_DIR")
            if not parent or not os.path.isdir(parent):
                parent = None
            self._root = tempfile.mkdtemp(prefix="dnf-gui-icons-", dir=parent)
            self._bases.clear()
        return self._root

    def cleanup(self) -> None:
        if self._root:
            shutil.rmtree(self._root, ignore_errors=True)
            self._root = None
            self._bases.clear()
