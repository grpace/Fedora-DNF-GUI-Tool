"""Modern dark theme stylesheet for the application.

Inspired by KDE Breeze Dark with enhanced modern aesthetics.
Uses a deep blue-gray palette with vibrant accent colors.
"""


# ─── Color Palette ──────────────────────────────────────────────────
COLORS = {
    # Backgrounds
    "bg_primary":       "#0d1117",      # Main background (deep dark)
    "bg_secondary":     "#161b22",      # Cards, sidebar
    "bg_tertiary":      "#1c2333",      # Elevated surfaces
    "bg_hover":         "#21262d",      # Hover state
    "bg_selected":      "#1a3a5c",      # Selected/active item
    "bg_input":         "#0d1117",      # Input field background

    # Borders
    "border_primary":   "#30363d",      # Default borders
    "border_secondary": "#21262d",      # Subtle borders
    "border_focus":     "#58a6ff",      # Focus ring
    
    # Text
    "text_primary":     "#e6edf3",      # Primary text
    "text_secondary":   "#8b949e",      # Secondary/muted text
    "text_tertiary":    "#6e7681",      # Disabled text
    "text_link":        "#58a6ff",      # Links
    
    # Accents
    "accent_blue":      "#58a6ff",      # Primary accent
    "accent_green":     "#3fb950",      # Success / install
    "accent_red":       "#f85149",      # Danger / remove
    "accent_orange":    "#d29922",      # Warning / updates
    "accent_purple":    "#bc8cff",      # Info accent
    
    # Gradients (for sidebar active indicator)
    "gradient_start":   "#58a6ff",
    "gradient_end":     "#bc8cff",
    
    # Scrollbar
    "scrollbar_bg":     "#161b22",
    "scrollbar_handle": "#30363d",
    "scrollbar_hover":  "#484f58",
}

# ─── Font Settings ──────────────────────────────────────────────────
FONTS = {
    "family":       "'Inter', 'Segoe UI', 'Noto Sans', sans-serif",
    "family_mono":  "'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace",
    "size_xs":      "11px",
    "size_sm":      "12px",
    "size_base":    "13px",
    "size_lg":      "15px",
    "size_xl":      "18px",
    "size_2xl":     "24px",
}


def get_stylesheet() -> str:
    """Return the complete application QSS stylesheet."""
    c = COLORS
    f = FONTS
    
    return f"""
    /* ────────── Global ────────── */
    
    QMainWindow {{
        background-color: {c['bg_primary']};
        color: {c['text_primary']};
        font-family: {f['family']};
        font-size: {f['size_base']};
    }}
    
    QWidget {{
        background-color: transparent;
        color: {c['text_primary']};
        font-family: {f['family']};
    }}
    
    /* ────────── Sidebar ────────── */
    
    #sidebar {{
        background-color: {c['bg_secondary']};
        border-right: 1px solid {c['border_primary']};
        min-width: 220px;
        max-width: 220px;
    }}
    
    #sidebar_title {{
        font-size: {f['size_xl']};
        font-weight: 700;
        color: {c['text_primary']};
        padding: 20px 16px 8px 16px;
    }}
    
    #sidebar_subtitle {{
        font-size: {f['size_xs']};
        color: {c['text_tertiary']};
        padding: 0px 16px 16px 16px;
    }}
    
    QPushButton#nav_button {{
        background-color: transparent;
        color: {c['text_secondary']};
        border: none;
        border-radius: 8px;
        padding: 10px 16px;
        text-align: left;
        font-size: {f['size_base']};
        font-weight: 500;
        margin: 2px 8px;
    }}
    
    QPushButton#nav_button:hover {{
        background-color: {c['bg_hover']};
        color: {c['text_primary']};
    }}
    
    QPushButton#nav_button[active="true"] {{
        background-color: {c['bg_selected']};
        color: {c['accent_blue']};
        font-weight: 600;
    }}
    
    /* ────────── Content Area ────────── */
    
    #content_area {{
        background-color: {c['bg_primary']};
    }}
    
    #page_header {{
        font-size: {f['size_2xl']};
        font-weight: 700;
        color: {c['text_primary']};
        padding: 24px 32px 8px 32px;
    }}
    
    #page_subheader {{
        font-size: {f['size_sm']};
        color: {c['text_secondary']};
        padding: 0px 32px 16px 32px;
    }}
    
    /* ────────── Cards ────────── */
    
    QFrame#card {{
        background-color: {c['bg_secondary']};
        border: 1px solid {c['border_primary']};
        border-radius: 12px;
        padding: 16px;
    }}
    
    QFrame#card:hover {{
        border-color: {c['border_focus']};
        background-color: {c['bg_tertiary']};
    }}
    
    /* ────────── Stats Card ────────── */
    
    QFrame#stats_card {{
        background-color: {c['bg_secondary']};
        border: 1px solid {c['border_primary']};
        border-radius: 12px;
        padding: 20px;
        min-height: 80px;
    }}
    
    QLabel#stats_number {{
        font-size: {f['size_2xl']};
        font-weight: 700;
        color: {c['accent_blue']};
    }}
    
    QLabel#stats_label {{
        font-size: {f['size_sm']};
        color: {c['text_secondary']};
    }}
    
    /* ────────── Buttons ────────── */
    
    QPushButton#primary_button {{
        background-color: {c['accent_blue']};
        color: #ffffff;
        border: none;
        border-radius: 8px;
        padding: 10px 20px;
        font-size: {f['size_base']};
        font-weight: 600;
        min-width: 120px;
    }}
    
    QPushButton#primary_button:hover {{
        background-color: #79c0ff;
    }}
    
    QPushButton#primary_button:pressed {{
        background-color: #388bfd;
    }}
    
    QPushButton#primary_button:disabled {{
        background-color: {c['bg_hover']};
        color: {c['text_tertiary']};
    }}
    
    QPushButton#danger_button {{
        background-color: transparent;
        color: {c['accent_red']};
        border: 1px solid {c['accent_red']};
        border-radius: 8px;
        padding: 8px 16px;
        font-size: {f['size_sm']};
        font-weight: 600;
    }}
    
    QPushButton#danger_button:hover {{
        background-color: {c['accent_red']};
        color: #ffffff;
    }}
    
    QPushButton#success_button {{
        background-color: transparent;
        color: {c['accent_green']};
        border: 1px solid {c['accent_green']};
        border-radius: 8px;
        padding: 8px 16px;
        font-size: {f['size_sm']};
        font-weight: 600;
    }}
    
    QPushButton#success_button:hover {{
        background-color: {c['accent_green']};
        color: #ffffff;
    }}
    
    /* ────────── Search Input ────────── */
    
    QLineEdit#search_input {{
        background-color: {c['bg_input']};
        color: {c['text_primary']};
        border: 1px solid {c['border_primary']};
        border-radius: 8px;
        padding: 10px 16px;
        font-size: {f['size_base']};
        selection-background-color: {c['accent_blue']};
    }}
    
    QLineEdit#search_input:focus {{
        border-color: {c['accent_blue']};
    }}
    
    QLineEdit#search_input::placeholder {{
        color: {c['text_tertiary']};
    }}
    
    /* ────────── Package List ────────── */
    
    QScrollArea {{
        border: none;
        background-color: transparent;
    }}
    
    QScrollArea > QWidget > QWidget {{
        background-color: transparent;
    }}
    
    /* ────────── Scrollbars ────────── */
    
    QScrollBar:vertical {{
        background-color: {c['scrollbar_bg']};
        width: 10px;
        border-radius: 5px;
        margin: 0;
    }}
    
    QScrollBar::handle:vertical {{
        background-color: {c['scrollbar_handle']};
        border-radius: 5px;
        min-height: 30px;
    }}
    
    QScrollBar::handle:vertical:hover {{
        background-color: {c['scrollbar_hover']};
    }}
    
    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    
    QScrollBar:horizontal {{
        background-color: {c['scrollbar_bg']};
        height: 10px;
        border-radius: 5px;
    }}
    
    QScrollBar::handle:horizontal {{
        background-color: {c['scrollbar_handle']};
        border-radius: 5px;
        min-width: 30px;
    }}
    
    QScrollBar::handle:horizontal:hover {{
        background-color: {c['scrollbar_hover']};
    }}
    
    QScrollBar::add-line:horizontal,
    QScrollBar::sub-line:horizontal {{
        width: 0;
    }}
    
    /* ────────── Terminal Output ────────── */
    
    QPlainTextEdit#terminal {{
        background-color: {c['bg_primary']};
        color: {c['accent_green']};
        border: 1px solid {c['border_primary']};
        border-radius: 8px;
        padding: 12px;
        font-family: {f['family_mono']};
        font-size: {f['size_sm']};
        selection-background-color: {c['bg_selected']};
    }}
    
    /* ────────── Status Bar ────────── */
    
    QStatusBar {{
        background-color: {c['bg_secondary']};
        color: {c['text_secondary']};
        border-top: 1px solid {c['border_primary']};
        font-size: {f['size_xs']};
        padding: 4px 12px;
    }}
    
    /* ────────── Progress Bar ────────── */
    
    QProgressBar {{
        background-color: {c['bg_hover']};
        border: none;
        border-radius: 4px;
        height: 6px;
        text-align: center;
    }}
    
    QProgressBar::chunk {{
        background-color: {c['accent_blue']};
        border-radius: 4px;
    }}
    
    /* ────────── Tooltips ────────── */
    
    QToolTip {{
        background-color: {c['bg_tertiary']};
        color: {c['text_primary']};
        border: 1px solid {c['border_primary']};
        border-radius: 6px;
        padding: 6px 10px;
        font-size: {f['size_sm']};
    }}
    
    /* ────────── Combo Box ────────── */
    
    QComboBox {{
        background-color: {c['bg_input']};
        color: {c['text_primary']};
        border: 1px solid {c['border_primary']};
        border-radius: 8px;
        padding: 8px 12px;
        font-size: {f['size_sm']};
        min-width: 140px;
    }}
    
    QComboBox:hover {{
        border-color: {c['accent_blue']};
    }}
    
    QComboBox::drop-down {{
        border: none;
        padding-right: 8px;
    }}
    
    QComboBox QAbstractItemView {{
        background-color: {c['bg_secondary']};
        color: {c['text_primary']};
        border: 1px solid {c['border_primary']};
        border-radius: 8px;
        selection-background-color: {c['bg_selected']};
        padding: 4px;
    }}
    
    /* ────────── Tab Widget ────────── */
    
    QTabWidget::pane {{
        border: none;
        background-color: transparent;
    }}
    
    QTabBar::tab {{
        background-color: transparent;
        color: {c['text_secondary']};
        border: none;
        border-bottom: 2px solid transparent;
        padding: 8px 16px;
        font-size: {f['size_sm']};
        font-weight: 500;
    }}
    
    QTabBar::tab:hover {{
        color: {c['text_primary']};
    }}
    
    QTabBar::tab:selected {{
        color: {c['accent_blue']};
        border-bottom: 2px solid {c['accent_blue']};
        font-weight: 600;
    }}
    
    /* ────────── Separator ────────── */
    
    QFrame#separator {{
        background-color: {c['border_primary']};
        max-height: 1px;
        margin: 8px 16px;
    }}
    
    /* ────────── Badge Labels ────────── */
    
    QLabel#badge_update {{
        background-color: {c['accent_orange']};
        color: #ffffff;
        border-radius: 10px;
        padding: 2px 8px;
        font-size: {f['size_xs']};
        font-weight: 700;
    }}
    
    QLabel#badge_installed {{
        background-color: {c['accent_green']};
        color: #ffffff;
        border-radius: 10px;
        padding: 2px 8px;
        font-size: {f['size_xs']};
        font-weight: 700;
    }}
    
    /* ────────── Loading Indicator ────────── */
    
    QLabel#loading_label {{
        color: {c['text_secondary']};
        font-size: {f['size_lg']};
        padding: 40px;
    }}
    """
