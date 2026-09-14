"""Theme system — KDE Plasma 6 Breeze aesthetic for Fedora Linux.

Design principles:
- Native KDE Breeze design tokens (elevated cards, crisp contrast, 8px radius)
- Pure QSS styling with no inline styles on widgets
- High-contrast, highly readable buttons in both Light Mode and Dark Mode
- Uncluttered button hierarchy: single primary action + clean neutral secondary buttons
- Vector icons painted via dnf_gui.ui.icons
"""

import os
from PyQt6.QtCore import QSettings

_ORG = "GregTech"
_APP = "FedoraDNFGUI"

# ── Palette Definitions ──

_DARK = {
    # Canvas & Elevation
    "bg_app": "#16181e",           # Clean dark slate canvas
    "bg_sidebar": "#121418",       # Deeper navigation rail
    "bg_card": "#1e222a",          # Elevated card surface
    "bg_card_hover": "#252b36",    # Interactive card hover
    "bg_card_active": "#2b3240",   # Selected card surface
    "bg_card_disabled": "#191c22",
    "bg_input": "#181b22",         # Recessed input field
    "bg_banner": "#1e222a",
    # Borders
    "border": "#313846",           # Visible clean container border
    "border_soft": "#252b36",      # Subtle separator border
    "border_focus": "#3daee9",     # Plasma Breeze Cyan focus ring
    # Typography
    "text": "#f0f3f8",             # Crisp high-contrast foreground
    "text_dim": "#a2abbb",         # Readable secondary text
    "text_faint": "#6b7688",       # Faint metadata / subtle captions
    # Semantic Colors (KDE Plasma 6)
    "accent": "#3daee9",           # Breeze Cyan
    "accent_hover": "#55bbee",
    "accent_pressed": "#2899d4",
    "on_bright": "#ffffff",
    "on_accent": "#0d131a",        # Deep contrast text for bright cyan fill
    "green": "#27ae60",            # Emerald success
    "green_hover": "#2ecc71",
    "badge_ok_text": "#4ade80",
    "badge_update_bg": "#f67400",
    "badge_update_text": "#ffffff",
    "danger": "#e05252",           # Plasma crimson
    "red": "#e05252",
    "amber": "#f67400",            # Plasma amber
    "amber_bg": "#2a1c0d",
    "violet": "#9b59b6",           # Plasma purple
    # Buttons Neutral / Secondary
    "btn_neutral_bg": "#222630",
    "btn_neutral_border": "#363d4e",
    "btn_neutral_text": "#e2e8f0",
    "btn_neutral_hover_bg": "#2a3140",
    "btn_neutral_hover_border": "#3daee9",
    "btn_neutral_hover_text": "#ffffff",
    # Scrollbars & Terminal
    "scroll_bg": "transparent",
    "scroll_handle": "#384152",
    "scroll_hover": "#4b566b",
    "terminal_bg": "#0d0f14",      # Obsidian terminal
}

_LIGHT = {
    # Canvas & Elevation
    "bg_app": "#f4f6fa",           # Breeze Light clean canvas
    "bg_sidebar": "#e9edf3",       # Distinct sidebar rail
    "bg_card": "#ffffff",          # Pure white card surface
    "bg_card_hover": "#f7f9fc",    # Subtle card hover
    "bg_card_active": "#eef2f8",   # Selected card surface
    "bg_card_disabled": "#f4f6fa",
    "bg_input": "#ffffff",         # Clean input field
    "bg_banner": "#ffffff",
    # Borders
    "border": "#c8d0dc",           # Well-defined light border
    "border_soft": "#e0e5ee",      # Subtle interior separator
    "border_focus": "#1d72b8",     # Breeze Royal Blue focus
    # Typography
    "text": "#1a1f28",             # Deep charcoal/black text (high contrast)
    "text_dim": "#485363",         # Clear secondary text
    "text_faint": "#6e7b8c",       # Readable caption
    # Semantic Colors (KDE Plasma 6 Light)
    "accent": "#1d72b8",           # Breeze Royal Blue (high contrast against white)
    "accent_hover": "#175c94",
    "accent_pressed": "#114670",
    "on_bright": "#ffffff",
    "on_accent": "#ffffff",        # White text on royal blue
    "green": "#1e824c",            # Forest green (readable on light backgrounds)
    "green_hover": "#17673c",
    "badge_ok_text": "#15633a",
    "badge_update_bg": "#c85a00",
    "badge_update_text": "#ffffff",
    "danger": "#c0392b",           # Rich red
    "red": "#c0392b",
    "amber": "#c85a00",            # Deep amber
    "amber_bg": "#fff3e0",
    "violet": "#7b1fa2",
    # Buttons Neutral / Secondary
    "btn_neutral_bg": "#ffffff",
    "btn_neutral_border": "#c8d0dc",
    "btn_neutral_text": "#1a1f28",
    "btn_neutral_hover_bg": "#f0f4f9",
    "btn_neutral_hover_border": "#1d72b8",
    "btn_neutral_hover_text": "#1d72b8",
    # Scrollbars & Terminal
    "scroll_bg": "transparent",
    "scroll_handle": "#c2c9d4",
    "scroll_hover": "#a2abb8",
    "terminal_bg": "#14171d",
}

FONTS = {
    "family": "'Noto Sans', 'Inter', 'Segoe UI', sans-serif",
    "family_mono": "'JetBrains Mono', 'Fira Code', 'Hack', monospace",
    "size_xs": "11px",
    "size_sm": "12px",
    "size_base": "13px",
    "size_md": "14px",
    "size_lg": "16px",
    "size_xl": "20px",
    "size_2xl": "24px",
}

COLORS = {  # backward-compat alias
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


def detect_system_theme() -> str:
    """Detect whether system is dark or light mode."""
    try:
        val = os.environ.get("KDE_COLOR_SCHEME_PATH", "").lower()
        if "dark" in val:
            return "dark"
        if "light" in val:
            return "light"
    except Exception:
        pass
    return "dark"


def resolve_mode(mode: str | None = None) -> str:
    """Resolve theme mode: 'auto' -> detect, 'light'/'dark' -> as is."""
    if mode in ("light", "dark"):
        return mode
    return detect_system_theme()


def get_saved_theme_mode() -> str:
    try:
        s = QSettings(_ORG, _APP)
        return s.value("theme/mode", "auto")
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
    is_light = resolve_mode(mode) == "light"

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
        font-size: {f['size_lg']};
        font-weight: 700;
        color: {c['text']};
        padding: 0px;
        letter-spacing: -0.2px;
    }}
    #sidebar_subtitle {{
        font-size: {f['size_xs']};
        color: {c['accent']};
        font-weight: 600;
        padding: 2px 0px 0px 0px;
        letter-spacing: 0.4px;
    }}
    #nav_section {{
        color: {c['text_faint']};
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 1.2px;
        padding: 16px 16px 6px 16px;
    }}
    QLabel#nav_label {{
        color: {c['text_dim']};
        background-color: transparent;
        font-size: {f['size_base']};
        font-weight: 500;
    }}
    QPushButton#nav_button[hovered="true"] QLabel#nav_label {{
        color: {c['text']};
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
        border-radius: 8px;
        padding: 9px 12px 9px 12px;
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
        color: {c['accent']};
        font-weight: 700;
        border-left: 3px solid {c['accent']};
        border-radius: 0px 8px 8px 0px;
    }}
    QLabel#nav_badge {{
        background-color: {c['accent']};
        color: {c['on_accent']};
        border-radius: 9px;
        padding: 1px 7px;
        font-size: 11px;
        font-weight: 700;
    }}
    #sidebar_footer {{
        border-top: 1px solid {c['border_soft']};
        padding: 10px 0px 6px 0px;
    }}
    QLabel#sidebar_version {{
        color: {c['text_faint']};
        font-size: 11px;
        font-weight: 500;
        padding: 6px 16px;
    }}
    QPushButton#theme_toggle {{
        background-color: {c['btn_neutral_bg']};
        color: {c['btn_neutral_text']};
        border: 1px solid {c['btn_neutral_border']};
        border-radius: 8px;
        padding: 7px 12px;
        text-align: center;
        font-size: {f['size_sm']};
        font-weight: 600;
        margin: 4px 12px 6px 12px;
    }}
    QPushButton#theme_toggle:hover {{
        background-color: {c['btn_neutral_hover_bg']};
        border-color: {c['btn_neutral_hover_border']};
        color: {c['btn_neutral_hover_text']};
    }}

    /* ── Content & Headers ── */
    #content_area {{ background-color: {c['bg_app']}; }}
    #progress_bar_slot {{ background-color: {c['bg_app']}; }}
    #page_header {{
        font-size: 21px;
        font-weight: 700;
        color: {c['text']};
        margin: 0px;
        padding: 0px;
        letter-spacing: -0.3px;
    }}
    #page_subheader {{
        font-size: 13px;
        font-weight: 400;
        color: {c['text_dim']};
        margin: 0px;
        padding: 0px;
    }}
    #page_kicker {{
        font-size: 11px;
        font-weight: 700;
        color: {c['accent']};
        letter-spacing: 1px;
        padding: 0px;
    }}

    /* ── Cards & Surfaces ── */
    QFrame#card {{
        background-color: {c['bg_card']};
        border: 1px solid {c['border_soft']};
        border-radius: 10px;
        padding: 14px 16px;
    }}
    QFrame#card:hover {{
        border-color: {c['border']};
    }}
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

    /* Stat Cards */
    QFrame#stats_card {{
        background-color: {c['bg_card']};
        border: 1px solid {c['border_soft']};
        border-radius: 10px;
        padding: 14px 16px;
        min-height: 64px;
    }}
    QFrame#stats_card:hover {{
        border-color: {c['border']};
        background-color: {c['bg_card_hover']};
    }}
    QLabel#stats_number {{
        font-size: 26px;
        font-weight: 700;
        color: {c['accent']};
        letter-spacing: -0.6px;
    }}
    QLabel#stats_label {{
        font-size: 11px;
        color: {c['text_dim']};
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }}

    /* Badges */
    QLabel#badge_installed, QLabel#badge_update,
    QLabel#badge_ok, QLabel#badge_muted {{
        border-radius: 6px;
        padding: 2px 8px;
        font-size: 11px;
        font-weight: 600;
    }}
    QLabel#badge_installed {{
        background-color: {c['green']}22;
        color: {c['badge_ok_text']};
        border: 1px solid {c['green']}44;
    }}
    QLabel#badge_update {{
        background-color: {c['badge_update_bg']};
        color: {c['badge_update_text']};
        border: 1px solid {c['badge_update_bg']};
    }}
    QLabel#badge_ok {{
        background-color: {c['green']}22;
        color: {c['badge_ok_text']};
        border: 1px solid {c['green']}44;
    }}
    QLabel#badge_muted {{
        background-color: transparent;
        color: {c['text_dim']};
        border: 1px solid {c['border']};
    }}
    QLabel#repo_dot_on, QLabel#repo_dot_off {{
        background-color: transparent;
        border: none;
        font-size: 13px;
    }}
    QLabel#repo_dot_on {{ color: {c['badge_ok_text']}; }}
    QLabel#repo_dot_off {{ color: {c['text_faint']}; }}
    QLabel#txn_badge {{
        background-color: {c['accent']}1f;
        color: {c['accent']};
        border-radius: 6px;
        font-size: 12px;
        font-weight: 700;
        padding: 4px 8px;
    }}

    /* Quick Tools Cards — Clean Desktop Style */
    QLabel#tool_icon {{
        background-color: transparent;
        border: none;
        padding: 0px;
    }}
    QLabel#tool_title {{
        font-size: {f['size_base']};
        font-weight: 600;
        color: {c['text']};
    }}
    QLabel#tool_desc {{
        color: {c['text_dim']};
        font-size: {f['size_sm']};
    }}

    /* ── High-Contrast, Unified Buttons ── */
    QPushButton#primary_button {{
        background-color: {c['accent']};
        color: {c['on_accent'] if not is_light else c['on_bright']};
        border: none;
        border-radius: 8px;
        padding: 8px 18px;
        min-height: 32px;
        font-size: {f['size_base']};
        font-weight: 600;
        min-width: 100px;
    }}
    QPushButton#primary_button:hover {{
        background-color: {c['accent_hover']};
    }}
    QPushButton#primary_button:pressed {{
        background-color: {c['accent_pressed']};
    }}
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
        font-weight: 600;
        min-width: 100px;
    }}
    QPushButton#success_button:hover {{
        background-color: {c['green_hover']};
    }}
    QPushButton#success_button:disabled {{
        background-color: {c['border_soft']};
        color: {c['text_faint']};
    }}

    QPushButton#accent_button {{
        background-color: {c['btn_neutral_bg']};
        color: {c['accent']};
        border: 1px solid {c['accent']};
        border-radius: 8px;
        padding: 8px 18px;
        min-height: 32px;
        font-size: {f['size_base']};
        font-weight: 600;
        min-width: 100px;
    }}
    QPushButton#accent_button:hover {{
        background-color: {c['btn_neutral_hover_bg']};
        border-color: {c['accent_hover']};
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
        font-weight: 600;
        min-width: 100px;
    }}
    QPushButton#warning_button:hover {{
        background-color: {c['amber']};
        opacity: 0.9;
    }}
    QPushButton#warning_button:disabled {{
        background-color: {c['border_soft']};
        color: {c['text_faint']};
    }}

    QPushButton#ghost_button {{
        background-color: {c['btn_neutral_bg']};
        color: {c['btn_neutral_text']};
        border: 1px solid {c['btn_neutral_border']};
        border-radius: 8px;
        padding: 7px 16px;
        min-height: 32px;
        font-size: {f['size_base']};
        font-weight: 600;
        min-width: 72px;
    }}
    QPushButton#ghost_button:hover {{
        background-color: {c['btn_neutral_hover_bg']};
        border-color: {c['btn_neutral_hover_border']};
        color: {c['btn_neutral_hover_text']};
    }}
    QPushButton#ghost_button:disabled {{
        background-color: {c['bg_card_disabled']};
        color: {c['text_faint']};
        border-color: {c['border_soft']};
    }}

    QPushButton#danger_button {{
        background-color: {c['btn_neutral_bg']};
        color: {c['danger']};
        border: 1px solid {c['danger']}66;
        border-radius: 8px;
        padding: 7px 16px;
        min-height: 32px;
        font-size: {f['size_base']};
        font-weight: 600;
    }}
    QPushButton#danger_button:hover {{
        border-color: {c['danger']};
        background-color: {c['danger']}18;
    }}
    QPushButton#danger_button:disabled {{
        background-color: transparent;
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

    /* ── Inputs & Controls ── */
    QCheckBox {{
        color: {c['text']};
        font-size: {f['size_base']};
        spacing: 8px;
    }}
    QCheckBox::indicator {{
        width: 18px;
        height: 18px;
        border: 1px solid {c['border']};
        border-radius: 5px;
        background-color: {c['bg_input']};
    }}
    QCheckBox::indicator:hover {{
        border-color: {c['border_focus']};
    }}
    QCheckBox::indicator:checked {{
        background-color: {c['accent']};
        border-color: {c['accent']};
    }}

    QLineEdit#search_input {{
        background-color: {c['bg_input']};
        color: {c['text']};
        border: 1px solid {c['border']};
        border-radius: 8px;
        padding: 8px 14px;
        font-size: {f['size_base']};
        selection-background-color: {c['accent']};
    }}
    QLineEdit#search_input:focus {{
        border-color: {c['border_focus']};
    }}

    QComboBox {{
        background-color: {c['bg_input']};
        color: {c['text']};
        border: 1px solid {c['border']};
        border-radius: 8px;
        padding: 7px 12px;
        text-align: center;
        min-width: 140px;
        font-size: {f['size_sm']};
    }}
    QComboBox:focus {{
        border-color: {c['border_focus']};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {c['bg_card']};
        color: {c['text']};
        border: 1px solid {c['border']};
        border-radius: 8px;
        padding: 4px;
        selection-background-color: {c['accent']};
    }}

    /* ── Reboot Banner ── */
    QFrame#reboot_banner {{
        background-color: {c['amber_bg']};
        border: 1px solid {c['amber']};
        border-radius: 10px;
        padding: 12px 16px;
    }}
    QLabel#reboot_banner_text {{
        color: {c['amber']};
        font-size: {f['size_base']};
        font-weight: 600;
    }}

    /* ── Tabs ── */
    QTabWidget::pane {{
        border: none;
        background-color: transparent;
    }}
    QTabBar::tab {{
        background-color: transparent;
        color: {c['text_dim']};
        border: none;
        border-bottom: 2px solid transparent;
        padding: 8px 18px;
        font-size: {f['size_base']};
        font-weight: 600;
        margin-right: 8px;
    }}
    QTabBar::tab:hover {{
        color: {c['text']};
    }}
    QTabBar::tab:selected {{
        color: {c['accent']};
        border-bottom: 2px solid {c['accent']};
    }}

    /* ── Progress & Resources ── */
    QProgressBar {{
        background-color: {c['border_soft']};
        border: none;
        border-radius: 4px;
        text-align: center;
    }}
    QProgressBar::chunk {{
        background-color: {c['accent']};
        border-radius: 4px;
    }}
    QProgressBar#resource_bar {{
        background-color: {c['border_soft']};
        border: none;
        border-radius: 4px;
        min-height: 8px;
        max-height: 8px;
    }}
    QProgressBar#resource_bar::chunk {{
        background-color: {c['accent']};
        border-radius: 4px;
    }}

    /* ── Scrollbars ── */
    QScrollArea {{
        border: none;
        background-color: transparent;
    }}
    QScrollBar:vertical {{
        border: none;
        background: {c['scroll_bg']};
        width: 8px;
        margin: 0px;
    }}
    QScrollBar::handle:vertical {{
        background: {c['scroll_handle']};
        min-height: 24px;
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {c['scroll_hover']};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: none;
        border: none;
    }}

    /* ── Terminal ── */
    QPlainTextEdit#terminal {{
        background-color: {c['terminal_bg']};
        color: #d8dee9;
        border: 1px solid {c['border_soft']};
        border-radius: 8px;
        padding: 12px;
        font-family: {f['family_mono']};
        font-size: 12px;
        line-height: 1.4;
    }}

    /* ── Terminal Status Dots ── */
    QLabel#term_dot_idle, QLabel#term_dot_run,
    QLabel#term_dot_ok, QLabel#term_dot_err {{
        background-color: transparent;
        border: none;
        font-size: 14px;
    }}
    QLabel#term_dot_idle {{ color: {c['text_faint']}; }}
    QLabel#term_dot_run  {{ color: {c['accent']}; }}
    QLabel#term_dot_ok   {{ color: {c['green']}; }}
    QLabel#term_dot_err  {{ color: {c['danger']}; }}

    /* ── Typography Helpers ── */
    QLabel#section_label {{
        font-size: {f['size_md']};
        font-weight: 700;
        color: {c['text']};
        letter-spacing: -0.2px;
        padding: 8px 0px 4px 0px;
    }}
    QLabel#hint {{
        color: {c['text_dim']};
        font-size: {f['size_sm']};
    }}
    QLabel#caption {{
        color: {c['text_faint']};
        font-size: {f['size_xs']};
    }}
    QLabel#status_line {{
        color: {c['text_dim']};
        font-size: {f['size_sm']};
    }}
    QLabel#loading_label {{
        color: {c['text_dim']};
        font-size: {f['size_base']};
        padding: 40px;
    }}
    QFrame#separator {{
        background-color: {c['border_soft']};
        max-height: 1px;
    }}
    """
