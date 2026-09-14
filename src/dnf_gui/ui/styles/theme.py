"""Breeze-inspired adaptive theme for Fedora KDE.

Lightweight by design:
- flat surfaces, no gradients, no per-widget inline stylesheets
- one QSS source of truth; pages use objectName only
- follows KDE light/dark via ``mode`` ("auto" | "dark" | "light")

Public API is backward compatible:
    get_stylesheet() -> str            # auto-detect, dark fallback
    get_stylesheet(mode) -> str        # explicit "dark" / "light" / "auto"
    detect_color_scheme() -> str       # "dark" or "light"
    resolve_mode(mode) -> str
    get_saved_theme_mode() / save_theme_mode()
"""

from __future__ import annotations

import os

from PyQt6.QtCore import QSettings

_ORG = "Greg.Tech"
_APP = "DNF Package Manager"

# ─── Palettes (Breeze-adjacent, tuned for contrast) ───────────────────
_DARK = {
    "bg_app": "#1b1e26",       # window
    "bg_sidebar": "#16181f",   # nav rail
    "bg_card": "#232733",      # cards
    "bg_card_hover": "#292e3c",
    "bg_input": "#14161d",
    "bg_banner": "#232733",
    "border": "#343a4a",
    "border_soft": "#2a2f3d",
    "border_focus": "#3daee9",  # Breeze blue
    "text": "#fcfcfc",
    "text_dim": "#aeb4c2",
    "text_faint": "#7b8294",
    "accent": "#3daee9",       # Breeze blue
    "accent_hover": "#52bcec",
    "accent_pressed": "#2d9bcb",
    "on_bright": "#10181d",    # text on bright fills (buttons, badges)
    "green": "#27ae60",
    "green_hover": "#32c16f",
    "badge_ok_text": "#3ddc84",
    "badge_update_bg": "#f67400",
    "badge_update_text": "#231303",
    "danger": "#f87171",
    "red": "#da4453",
    "amber": "#f67400",
    "amber_bg": "#3a2c10",
    "violet": "#9b59b6",
    "scroll_bg": "transparent",
    "scroll_handle": "#3a4152",
    "scroll_hover": "#4a5266",
    "terminal_bg": "#101218",
}

_LIGHT = {
    "bg_app": "#f2f3f5",
    "bg_sidebar": "#e9ebef",
    "bg_card": "#ffffff",
    "bg_card_hover": "#f6f7f9",
    "bg_input": "#ffffff",
    "bg_banner": "#ffffff",
    "border": "#d3d7de",
    "border_soft": "#e2e5ea",
    "border_focus": "#1a6fb5",
    "text": "#232627",
    "text_dim": "#5d6772",
    "text_faint": "#8b95a1",
    "accent": "#175f9b",
    "accent_hover": "#1f80cf",
    "accent_pressed": "#155a8a",
    "on_bright": "#ffffff",    # text on bright fills (buttons, badges)
    "green": "#177233",
    "green_hover": "#27a745",
    "badge_ok_text": "#137333",
    "badge_update_bg": "#8a5a00",
    "badge_update_text": "#ffffff",
    "danger": "#c0392b",
    "red": "#c0392b",
    "amber": "#7a5200",
    "amber_bg": "#fef3d8",
    "violet": "#7d3c98",
    "scroll_bg": "transparent",
    "scroll_handle": "#c4c9d2",
    "scroll_hover": "#a8afbb",
    "terminal_bg": "#232627",
}

FONTS = {
    "family": "'Noto Sans', 'Inter', 'Segoe UI', sans-serif",
    "family_mono": "'JetBrains Mono', 'Hack', 'Menlo', monospace",
    "size_xs": "11px",
    "size_sm": "12px",
    "size_base": "14px",
    "size_lg": "16px",
    "size_xl": "20px",
    "size_2xl": "26px",
}

COLORS = {  # backward-compat alias (dark palette, old key names kept)
    "bg_primary": _DARK["bg_app"],
    "bg_secondary": _DARK["bg_card"],
    "bg_tertiary": _DARK["border"],
    "bg_hover": _DARK["accent_hover"],
    "bg_selected": _DARK["accent"],
    "bg_input": _DARK["bg_input"],
    "bg_card": _DARK["bg_card"],
    "border_primary": _DARK["border"],
    "border_secondary": _DARK["scroll_handle"],
    "border_focus": _DARK["border_focus"],
    "text_primary": _DARK["text"],
    "text_secondary": _DARK["text_dim"],
    "text_tertiary": _DARK["text_faint"],
    "text_link": _DARK["accent"],
    "accent_blue": _DARK["accent"],
    "accent_green": _DARK["green"],
    "accent_red": _DARK["red"],
    "accent_orange": _DARK["amber"],
    "accent_purple": _DARK["violet"],
    "scrollbar_bg": _DARK["bg_app"],
    "scrollbar_handle": _DARK["scroll_handle"],
    "scrollbar_hover": _DARK["scroll_hover"],
}


def detect_color_scheme() -> str:
    """Best-effort KDE/system dark-mode detection. Returns 'dark'|'light'."""
    # Explicit override (useful for testing / screenshots)
    forced = os.environ.get("DNF_GUI_THEME", "").lower()
    if forced in ("dark", "light"):
        return forced
    # KDE / Qt global hints
    for var in ("KDE_COLOR_SCHEME", "QT_QPA_PLATFORMTHEME"):
        _ = var  # placeholder for future env-based detection
    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtGui import QPalette

        app = QApplication.instance()
        if app is not None:
            base = app.palette().color(QPalette.ColorRole.Window)
            # luminance heuristic: dark window => dark scheme
            lum = 0.2126 * base.red() + 0.7152 * base.green() + 0.0722 * base.blue()
            return "dark" if lum < 128 else "light"
    except Exception:
        pass
    # color-scheme preference files used on Fedora KDE
    try:
        import pathlib

        kdeglobals = pathlib.Path.home() / ".config" / "kdeglobals"
        if kdeglobals.exists():
            text = kdeglobals.read_text(errors="ignore")
            if "ColorScheme=BreezeDark" in text or "BreezeDark" in text:
                return "dark"
    except Exception:
        pass
    return "dark"  # historic default for this app


def resolve_mode(mode: str | None = None) -> str:
    if mode in ("dark", "light"):
        return mode
    saved = get_saved_theme_mode()
    if saved in ("dark", "light"):
        return saved
    if (mode or saved) == "light":
        return "light"
    detected = detect_color_scheme()
    return detected if detected in ("dark", "light") else "dark"


def get_saved_theme_mode() -> str:
    try:
        s = QSettings(_ORG, _APP)
        v = str(s.value("theme/mode", "auto"))
        return v if v in ("auto", "dark", "light") else "auto"
    except Exception:
        return "auto"


def save_theme_mode(mode: str) -> None:
    try:
        s = QSettings(_ORG, _APP)
        s.setValue("theme/mode", mode if mode in ("auto", "dark", "light") else "auto")
        s.sync()
    except Exception:
        pass


def get_palette(mode: str | None = None) -> dict:
    return dict(_LIGHT if resolve_mode(mode) == "light" else _DARK)


def get_stylesheet(mode: str | None = None) -> str:
    """Return the complete application QSS stylesheet."""
    c = get_palette(mode)
    f = FONTS
    light = resolve_mode(mode) == "light"
    card_shadow = "border"  # flat: rely on 1px border only
    _ = (card_shadow, light)

    return f"""
    /* ── Global ── */
    QMainWindow {{
        background-color: {c['bg_app']};
        color: {c['text']};
        font-family: {f['family']};
        font-size: {f['size_base']};
    }}
    QWidget {{
        background-color: transparent;
        color: {c['text']};
        font-family: {f['family']};
    }}
    QDialog {{
        background-color: {c['bg_app']};
    }}

    /* ── Sidebar ── */
    #sidebar {{
        background-color: {c['bg_sidebar']};
        border-right: 1px solid {c['border_soft']};
        min-width: 232px;
        max-width: 232px;
    }}
    #sidebar_title {{
        font-size: {f['size_xl']};
        font-weight: 800;
        color: {c['text']};
        padding: 18px 20px 4px 20px;
        letter-spacing: -0.5px;
    }}
    #sidebar_subtitle {{
        font-size: {f['size_sm']};
        color: {c['text_dim']};
        padding: 0px 20px 8px 20px;
    }}
    #nav_section {{
        color: {c['text_dim']};
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 1px;
        padding: 14px 20px 6px 20px;
    }}
    /* Nav row label: states driven by the parent button (QSS cannot
       read parent state in code, so the button exposes active/hover). */
    QLabel#nav_label {{
        color: {c['text_dim']};
        background-color: transparent;
        font-size: {f['size_base']};
        font-weight: 500;
    }}
    /* NOTE: :hover in an ancestor position of a descendant selector
       mis-matches (all rows highlight), so hover state is exposed by the
       button as a "hovered" dynamic property instead. */
    QPushButton#nav_button[hovered="true"] QLabel#nav_label {{
        color: {c['accent']};
    }}
    QPushButton#nav_button[active="true"] QLabel#nav_label {{
        color: {c['accent']};
        font-weight: 700;
    }}
    QPushButton#nav_button {{
        background-color: transparent;
        color: {c['text_dim']};
        border: none;
        border-left: 3px solid transparent;
        border-radius: 0px;
        padding: 9px 16px 9px 13px;
        text-align: left;
        font-size: {f['size_base']};
        font-weight: 500;
        margin: 1px 8px 1px 8px;
    }}
    QPushButton#nav_button:hover {{
        background-color: {c['bg_card']};
        color: {c['text']};
        border-radius: 8px;
    }}
    QPushButton#nav_button[active="true"] {{
        background-color: {c['bg_card']};
        color: {c['text']};
        font-weight: 700;
        border-left: 3px solid {c['accent']};
        border-radius: 0px 8px 8px 0px;
    }}
    QLabel#nav_badge {{
        background-color: {c['accent']};
        color: {c['on_bright']};
        border-radius: 9px;
        padding: 1px 8px;
        font-size: 11px;
        font-weight: 700;
    }}
    #sidebar_footer {{
        border-top: 1px solid {c['border_soft']};
    }}
    QLabel#sidebar_version {{
        color: {c['text_dim']};
        font-size: 12px;
        padding: 12px 20px;
    }}
    QPushButton#theme_toggle {{
        background-color: transparent;
        color: {c['text_dim']};
        border: 1px solid {c['border']};
        border-radius: 8px;
        padding: 6px 10px;
        font-size: {f['size_sm']};
        margin: 0px 16px 12px 16px;
    }}
    QPushButton#theme_toggle:hover {{
        color: {c['text']};
        border-color: {c['border_focus']};
    }}

    /* ── Content ── */
    #content_area {{ background-color: {c['bg_app']}; }}
    #progress_bar_slot {{ background-color: {c['bg_app']}; }}
    #page_header {{
        font-size: 26px;
        font-weight: 800;
        color: {c['text']};
        margin: 0px;
        padding: 14px 0px 0px 0px;
        letter-spacing: -0.5px;
    }}
    #page_subheader {{
        font-size: 13px;
        font-weight: 400;
        color: {c['text_dim']};
        margin: 0px;
        padding: 0px 0px 14px 0px;
    }}
    #page_kicker {{
        font-size: 11px;
        font-weight: 700;
        color: {c['accent']};
        letter-spacing: 1px;
        padding: 0px;
    }}

    /* ── Cards ── */
    QFrame#card {{
        background-color: {c['bg_card']};
        border: 1px solid {c['border_soft']};
        border-radius: 10px;
        padding: 16px 18px;
    }}
    QFrame#card:hover {{ border-color: {c['border']}; }}
    QLabel#card_title {{
        font-size: {f['size_base']};
        font-weight: 600;
        color: {c['text']};
    }}
    QLabel#card_detail {{
        font-size: {f['size_sm']};
        color: {c['text_dim']};
    }}
    QLabel#card_summary {{
        font-size: {f['size_sm']};
        color: {c['text_dim']};
    }}
    QLabel#card_mono {{
        font-size: 11px;
        font-family: {f['family_mono']};
        color: {c['text_dim']};
    }}

    /* Stat hero cards */
    QFrame#stats_card {{
        background-color: {c['bg_card']};
        border: 1px solid {c['border_soft']};
        border-radius: 10px;
        padding: 14px 16px;
        min-height: 64px;
    }}
    QFrame#stats_card:hover {{ border-color: {c['border']}; }}
    QLabel#stats_number {{
        font-size: 30px;
        font-weight: 800;
        color: {c['accent']};
        letter-spacing: -1px;
    }}
    QLabel#stats_label {{
        font-size: 11px;
        color: {c['text_dim']};
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.6px;
    }}

    /* Badges (install state, repo state) */
    QLabel#badge_installed, QLabel#badge_update,
    QLabel#badge_ok, QLabel#badge_muted {{
        border-radius: 9px;
        padding: 2px 9px;
        font-size: 11px;
        font-weight: 700;
    }}
    QLabel#badge_installed {{
        background-color: {c['green']}26;
        color: {c['badge_ok_text']};
        border: 1px solid {c['green']}55;
    }}
    QLabel#badge_update {{
        background-color: {c['badge_update_bg']};
        color: {c['badge_update_text']};
        border: 1px solid {c['badge_update_bg']};
    }}
    QLabel#badge_ok {{
        background-color: {c['green']}22;
        color: {c['badge_ok_text']};
        border: 1px solid {c['green']}55;
    }}
    QLabel#badge_muted {{
        background-color: transparent;
        color: {c['text_dim']};
        border: 1px solid {c['border']};
    }}
    /* Repo status dot: plain glyph, intentionally no background/border
       so it can never look squished. */
    QLabel#repo_dot_on, QLabel#repo_dot_off {{
        background-color: transparent;
        border: none;
        font-size: 13px;
    }}
    QLabel#repo_dot_on {{ color: {c['badge_ok_text']}; }}
    QLabel#repo_dot_off {{ color: {c['text_dim']}; }}
    QLabel#txn_badge {{
        background-color: {c['accent']}1f;
        color: {c['accent']};
        border-radius: 6px;
        font-size: 13px;
        font-weight: 700;
        padding: 5px 8px;
    }}
    QLabel#tool_icon {{
        font-size: 22px;
        background-color: {c['accent']}1a;
        border: 1px solid {c['border_soft']};
        border-radius: 9px;
    }}
    QLabel#tool_title {{ font-size: {f['size_base']}; font-weight: 600; }}
    QLabel#tool_desc {{ color: {c['text_dim']}; font-size: {f['size_sm']}; }}

    /* ── Buttons ── */
    QPushButton#primary_button {{
        background-color: {c['accent']};
        color: {c['on_bright']};
        border: none;
        border-radius: 8px;
        padding: 8px 18px;
        min-height: 32px;
        font-size: {f['size_base']};
        font-weight: 700;
        min-width: 110px;
    }}
    QPushButton#primary_button:hover {{ background-color: {c['accent_hover']}; }}
    QPushButton#primary_button:pressed {{ background-color: {c['accent_pressed']}; }}
    QPushButton#primary_button:disabled {{
        background-color: {c['border_soft']};
        color: {c['text_faint']};
    }}
    QPushButton#success_button {{
        background-color: {c['green']};
        color: {c['on_bright']};
        border: none;
        border-radius: 8px;
        padding: 8px 18px;
        min-height: 32px;
        font-size: {f['size_base']};
        font-weight: 700;
        min-width: 110px;
    }}
    QPushButton#success_button:hover {{ background-color: {c['green_hover']}; }}
    QPushButton#success_button:pressed {{ background-color: {c['green']}; }}
    QPushButton#success_button:disabled {{
        background-color: {c['border_soft']};
        color: {c['text_faint']};
    }}
    QPushButton#accent_button {{
        background-color: {c['bg_card']};
        color: {c['accent']};
        border: 1px solid {c['accent']}66;
        border-radius: 8px;
        padding: 8px 18px;
        min-height: 32px;
        font-size: {f['size_base']};
        font-weight: 700;
        min-width: 110px;
    }}
    QPushButton#accent_button:hover {{
        border-color: {c['accent']};
        background-color: {c['accent']}14;
    }}
    QPushButton#accent_button:disabled {{
        background-color: transparent;
        color: {c['text_faint']};
        border-color: {c['border_soft']};
    }}
    QPushButton#warning_button {{
        background-color: {c['amber']};
        color: {c['on_bright']};
        border: none;
        border-radius: 8px;
        padding: 8px 18px;
        min-height: 32px;
        font-size: {f['size_base']};
        font-weight: 700;
        min-width: 110px;
    }}
    QPushButton#warning_button:hover {{ background-color: {c['amber']}; }}
    QPushButton#warning_button:disabled {{
        background-color: {c['border_soft']};
        color: {c['text_faint']};
    }}
    QPushButton#ghost_button {{
        background-color: transparent;
        color: {c['text_dim']};
        border: 1px solid {c['border']};
        border-radius: 8px;
        padding: 7px 16px;
        min-height: 32px;
        font-size: {f['size_base']};
        font-weight: 600;
        min-width: 72px;
    }}
    QPushButton#ghost_button:hover {{
        color: {c['text']};
        border-color: {c['border_focus']};
    }}
    QPushButton#ghost_button:disabled {{
        color: {c['text_faint']};
        border-color: {c['border_soft']};
    }}
    QPushButton#danger_button {{
        background-color: transparent;
        color: {c['danger']};
        border: 1px solid {c['border']};
        border-radius: 8px;
        padding: 7px 16px;
        min-height: 32px;
        font-size: {f['size_base']};
        font-weight: 600;
    }}
    QPushButton#danger_button:hover {{
        border-color: {c['danger']};
        background-color: {c['danger']}14;
    }}
    QPushButton#danger_button:disabled {{
        color: {c['text_faint']};
        border-color: {c['border_soft']};
    }}
    QPushButton#icon_button {{
        background-color: transparent;
        color: {c['text_dim']};
        border: none;
        border-radius: 6px;
        padding: 4px 8px;
        font-size: 16px;
    }}
    QPushButton#icon_button:hover {{
        color: {c['text']};
        background-color: {c['border_soft']};
    }}
    QPushButton#primary_button[compact="true"],
    QPushButton#success_button[compact="true"],
    QPushButton#accent_button[compact="true"],
    QPushButton#warning_button[compact="true"],
    QPushButton#danger_button[compact="true"],
    QPushButton#ghost_button[compact="true"] {{
        padding: 5px 12px;
        min-height: 24px;
        min-width: 0px;
        font-size: {f['size_sm']};
    }}

    /* ── Inputs ── */
    QCheckBox {{
        color: {c['text']};
        font-size: {f['size_base']};
        spacing: 10px;
        padding: 4px 0px;
    }}
    QCheckBox::indicator {{
        width: 18px;
        height: 18px;
        border: 1px solid {c['border']};
        border-radius: 5px;
        background-color: {c['bg_input']};
    }}
    QCheckBox::indicator:hover {{ border-color: {c['border_focus']}; }}
    QCheckBox::indicator:checked {{
        background-color: {c['accent']};
        border-color: {c['accent']};
        image: none;
    }}
    QCheckBox::indicator:disabled {{
        background-color: {c['border_soft']};
        border-color: {c['border_soft']};
    }}
    QCheckBox:disabled {{ color: {c['text_faint']}; }}
    QLabel#hint {{
        color: {c['text_dim']};
        font-size: {f['size_sm']};
    }}
    QLabel#section_label {{
        font-size: {f['size_lg']};
        font-weight: 700;
        color: {c['text']};
        padding: 10px 0px 2px 0px;
        border-bottom: 1px solid {c['border_soft']};
    }}
    QLabel#status_line {{
        color: {c['text']};
        font-size: {f['size_base']};
    }}
    QLabel#caption {{
        color: {c['text_dim']};
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1px;
        padding: 8px 0px 0px 0px;
    }}
    QFrame#status_ok, QFrame#status_warn, QFrame#status_info {{
        border-radius: 10px;
        padding: 12px 16px;
    }}
    QFrame#status_ok {{
        background-color: {c['green']}14;
        border: 1px solid {c['green']}55;
    }}
    QFrame#status_warn {{
        background-color: {c['amber']}14;
        border: 1px solid {c['amber']}55;
    }}
    QFrame#status_info {{
        background-color: {c['bg_banner']};
        border: 1px solid {c['border_soft']};
    }}
    QLabel#status_title {{
        font-size: 14px;
        font-weight: 700;
        color: {c['text']};
    }}
    QLabel#status_detail {{
        font-size: 12px;
        color: {c['text_dim']};
    }}
    QFrame#reboot_banner {{
        background-color: {c['amber_bg']};
        border: 1px solid {c['amber']};
        border-radius: 10px;
    }}
    QLabel#reboot_banner_text {{
        color: {c['amber']};
        font-size: {f['size_base']};
        font-weight: 600;
    }}
    QLineEdit#search_input {{
        background-color: {c['bg_input']};
        color: {c['text']};
        border: 1px solid {c['border']};
        border-radius: 8px;
        padding: 6px 14px;
        min-height: 26px;
        font-size: {f['size_base']};
        selection-background-color: {c['accent']};
    }}
    QLineEdit#search_input:focus {{ border-color: {c['border_focus']}; }}
    QLineEdit#search_input::placeholder {{ color: {c['text_faint']}; }}

    /* ── Lists / scroll ── */
    QScrollArea {{ border: none; background-color: transparent; }}
    QScrollArea > QWidget > QWidget {{ background-color: transparent; }}
    QScrollBar:vertical {{
        background-color: {c['scroll_bg']};
        width: 8px;
        border-radius: 4px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background-color: {c['scroll_handle']};
        border-radius: 4px;
        min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{ background-color: {c['scroll_hover']}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar:horizontal {{
        background-color: {c['scroll_bg']};
        height: 8px;
        border-radius: 4px;
    }}
    QScrollBar::handle:horizontal {{
        background-color: {c['scroll_handle']};
        border-radius: 4px;
        min-width: 30px;
    }}
    QScrollBar::handle:horizontal:hover {{ background-color: {c['scroll_hover']}; }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

    /* ── Terminal ── */
    QPlainTextEdit#terminal {{
        background-color: {c['terminal_bg']};
        color: {'#fcfcfc' if light else c['text']};
        border: 1px solid {c['border_soft']};
        border-radius: 8px;
        padding: 14px;
        font-family: {f['family_mono']};
        font-size: {f['size_sm']};
        selection-background-color: {c['accent']};
    }}
    QLabel#term_dot_ok {{ color: {c['green']}; font-size: 12px; }}
    QLabel#term_dot_run {{ color: {c['green']}; font-size: 12px; }}
    QLabel#term_dot_err {{ color: {c['danger']}; font-size: 12px; }}
    QLabel#term_dot_idle {{ color: {c['text_faint']}; font-size: 12px; }}

    /* ── Resource bars (system page) ── */
    QProgressBar#resource_bar {{
        background-color: {c['border_soft']};
        border: none;
        border-radius: 4px;
        height: 8px;
    }}
    QProgressBar#resource_bar::chunk {{
        background-color: {c['accent']};
        border-radius: 4px;
    }}
    QProgressBar {{
        background-color: {c['border_soft']};
        border: none;
        border-radius: 2px;
        height: 4px;
        text-align: center;
    }}
    QProgressBar::chunk {{
        background-color: {c['accent']};
        border-radius: 2px;
    }}

    QToolTip {{
        background-color: {c['bg_card']};
        color: {c['text']};
        border: 1px solid {c['border']};
        border-radius: 4px;
        padding: 6px 10px;
        font-size: {f['size_sm']};
    }}
    QComboBox {{
        background-color: {c['bg_input']};
        color: {c['text']};
        border: 1px solid {c['border']};
        border-radius: 8px;
        padding: 6px 12px;
        min-height: 24px;
        font-size: {f['size_base']};
        min-width: 140px;
    }}
    QComboBox:hover {{ border-color: {c['text_dim']}; }}
    QComboBox::drop-down {{ border: none; padding-right: 8px; }}
    QComboBox QAbstractItemView {{
        background-color: {c['bg_card']};
        color: {c['text']};
        border: 1px solid {c['border']};
        border-radius: 6px;
        selection-background-color: {c['border_soft']};
        padding: 4px;
    }}
    QTabWidget::pane {{ border: none; background-color: transparent; }}
    QTabBar::tab {{
        background-color: transparent;
        color: {c['text_dim']};
        border: none;
        border-bottom: 2px solid transparent;
        padding: 8px 16px;
        font-size: {f['size_base']};
        font-weight: 500;
        margin-right: 8px;
    }}
    QTabBar::tab:hover {{ color: {c['text']}; }}
    QTabBar::tab:selected {{
        color: {c['text']};
        border-bottom: 2px solid {c['accent']};
        font-weight: 600;
    }}
    QFrame#separator {{
        background-color: transparent;
        max-height: 0px;
        margin: 0px;
        border: none;
    }}
    QLabel#loading_label {{
        color: {c['text_dim']};
        font-size: {f['size_lg']};
        padding: 40px;
    }}
    QLabel#empty_title {{
        font-size: {f['size_lg']};
        font-weight: 700;
        color: {c['text']};
    }}
    QLabel#empty_hint {{
        font-size: {f['size_sm']};
        color: {c['text_dim']};
    }}
    """
