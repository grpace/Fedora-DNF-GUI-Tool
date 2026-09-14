"""WCAG contrast check for the DNF GUI theme (both modes).

Run: QT_QPA_PLATFORM=offscreen PYTHONPATH=src python3 scripts/check_contrast.py
Exits non-zero if any pair fails its threshold.
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, "src")

from dnf_gui.ui.styles.theme import get_palette


def lum(hexcolor: str) -> float:
    h = hexcolor.lstrip("#")
    if len(h) == 8:  # strip alpha
        h = h[:6]
    r, g, b = (int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))

    def lin(x: float) -> float:
        return x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4

    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def ratio(fg: str, bg: str) -> float:
    a, b = lum(fg), lum(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


# (name, fg_key, bg_key, min_ratio)
PAIRS = [
    # nav
    ("nav idle", "text_dim", "bg_sidebar", 4.5),
    ("nav idle on card", "text_dim", "bg_card", 4.5),
    ("nav active", "accent", "bg_sidebar", 4.5),
    ("nav active on card", "accent", "bg_card", 4.5),
    ("count badge", "on_bright", "accent", 4.5),
    ("section/version", "text_dim", "bg_sidebar", 4.5),
    # content
    ("card title", "text", "bg_card", 4.5),
    ("card detail", "text_dim", "bg_card", 4.5),
    ("card detail on app", "text_dim", "bg_app", 4.5),
    ("stat number", "accent", "bg_card", 3.0),
    ("stat label", "text_dim", "bg_card", 4.5),
    ("header", "text", "bg_app", 3.0),
    ("subheader", "text_dim", "bg_app", 4.5),
    # buttons
    ("primary", "on_bright", "accent", 4.5),
    ("success", "on_bright", "green", 4.5),
    ("warning", "on_bright", "amber", 4.5),
    ("accent btn", "accent", "bg_card", 4.5),
    ("ghost", "text_dim", "bg_card", 4.5),
    ("danger", "danger", "bg_card", 4.5),
    # badges
    ("update pill", "badge_update_text", "badge_update_bg", 4.5),
    ("ok pill", "badge_ok_text", "bg_card", 4.5),
    ("muted pill", "text_dim", "bg_card", 4.5),
    ("txn badge", "accent", "bg_card", 4.5),
    # banners / status
    ("reboot banner", "amber", "amber_bg", 4.5),
    ("status title", "text", "bg_banner", 4.5),
    ("status detail", "text_dim", "bg_banner", 4.5),
    # terminal (always light text on a dark console surface)
    ("terminal", "terminal_text", "terminal_bg", 4.5),
]


def main() -> int:
    failures = 0
    for mode in ("dark", "light"):
        pal = dict(get_palette(mode), terminal_text="#fcfcfc")
        print(f"--- {mode} ---")
        for name, fgk, bgk, minimum in PAIRS:
            r = ratio(pal[fgk], pal[bgk])
            ok = r >= minimum
            failures += not ok
            print(f"  {'PASS' if ok else 'FAIL'} {name:20s} {r:.2f}:1 "
                  f"(min {minimum})  {pal[fgk]} on {pal[bgk]}")
    print("OK" if failures == 0 else f"{failures} FAILURES")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
