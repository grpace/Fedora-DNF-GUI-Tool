#!/usr/bin/env python3
"""WCAG AA contrast check of the colors the QML UI pairs itself.

The UI takes every color from the Plasma color scheme (Kirigami.Theme), so
the scheme authors own most contrast. This checks the pairings this app
chooses on top of that, against Breeze Light and Breeze Dark:

  * status pills (negative/neutral/link/positive tones, blended toward
    the text color so they stay readable, on their own fill: the tone at
    15% over the view background), and the same tone text with no fill
    (Tools' "Set Up", Settings' status lines),
  * secondary text (text blended 30% toward
    the background) on the view and window backgrounds,
  * notices: title and dimmed body on the tone at 12% over the view,
  * the primary button and the sidebar badge: white on the accent
    darkened 30% toward black (28% on hover, 40% pressed); on the selected
    sidebar entry the badge inverts (that accent on the selection's text
    color).

Exit status is non-zero if any pairing is below its minimum.
Usage: python3 scripts/check_contrast.py [scheme.colors ...]
"""

from __future__ import annotations

import configparser
import sys
from pathlib import Path

SCHEMES = [Path("/usr/share/color-schemes/BreezeLight.colors"),
           Path("/usr/share/color-schemes/BreezeDark.colors")]
SECONDARY_MIX = 0.30  # must match the QML's secondary text blend
PILL_MIX = 0.40       # must match Pill.qml (tone blended toward text)
PILL_FILL = 0.15      # must match Pill.qml fillMix (tone over the background)
NOTICE_MIX = 0.12     # must match Notice.qml tintMix (tone over the background)
PRIMARY_MIX = 0.30    # must match PrimaryButton.qml / NavItem.qml (accent toward black)
PRIMARY_HOVER_MIX = 0.28
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)


def _rgb(value: str) -> tuple[int, int, int]:
    r, g, b = (int(x) for x in value.split(",")[:3])
    return r, g, b


def _luminance(rgb) -> float:
    def channel(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b) -> float:
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def mix(a, b, t: float):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def check(path: Path) -> list[str]:
    scheme = configparser.ConfigParser(interpolation=None)
    scheme.read(path)
    view = {k: _rgb(v) for k, v in scheme["Colors:View"].items()}
    window = {k: _rgb(v) for k, v in scheme["Colors:Window"].items()}
    selection = {k: _rgb(v) for k, v in scheme["Colors:Selection"].items()}
    bg, fg = view["backgroundnormal"], view["foregroundnormal"]
    highlight = selection["backgroundnormal"]
    tones = {"negative": view["foregroundnegative"], "neutral": view["foregroundneutral"],
             "link (Core)": view["foregroundlink"], "positive": view["foregroundpositive"],
             "plain": fg}
    pairs = []
    for name, tone in tones.items():
        text = mix(tone, fg, PILL_MIX)
        pairs.append((f"pill {name}", text, mix(bg, tone, PILL_FILL), 4.5))
        if name != "plain":
            pairs.append((f"{name} text (no fill)", text, bg, 4.5))
    notice_tones = {"warning": view["foregroundneutral"], "information": highlight,
                    "positive": view["foregroundpositive"], "negative": view["foregroundnegative"]}
    for name, tone in notice_tones.items():
        fill = mix(bg, tone, NOTICE_MIX)
        pairs.append((f"notice {name} title", fg, fill, 4.5))
        pairs.append((f"notice {name} body", mix(fg, fill, SECONDARY_MIX), fill, 4.5))
    pairs += [
        ("primary button", WHITE, mix(highlight, BLACK, PRIMARY_MIX), 4.5),
        ("primary button (hover)", WHITE, mix(highlight, BLACK, PRIMARY_HOVER_MIX), 4.5),
        # The sidebar badge inverts on the selected entry.
        ("badge on selected entry", mix(highlight, BLACK, PRIMARY_MIX),
         selection["foregroundnormal"], 4.5),
        ("secondary text (view)", mix(fg, bg, SECONDARY_MIX), bg, 4.5),
        ("secondary text (window)",
         mix(window["foregroundnormal"], window["backgroundnormal"], SECONDARY_MIX),
         window["backgroundnormal"], 4.5),
        ("body text", fg, bg, 4.5),
    ]
    failures = []
    print(path.stem)
    # Selected rows use the scheme's own selection colors (as every KDE
    # app does); reported for information, not something this app picks.
    sel = contrast(selection["foregroundnormal"], selection["backgroundnormal"])
    print(f"  INFO {'scheme selection':30} {sel:5.2f}:1")
    for name, a, b, minimum in pairs:
        ratio = contrast(a, b)
        ok = ratio >= minimum
        print(f"  {'PASS' if ok else 'FAIL'} {name:30} {ratio:5.2f}:1 (min {minimum})")
        if not ok:
            failures.append(f"{path.stem}: {name} {ratio:.2f}:1")
    return failures


def main(argv: list[str]) -> int:
    paths = [Path(a) for a in argv] or [p for p in SCHEMES if p.exists()]
    if not paths:
        print("No color schemes found (install plasma-breeze or pass a .colors file).")
        return 1
    failures = [f for p in paths for f in check(p)]
    print("FAIL" if failures else "OK")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
