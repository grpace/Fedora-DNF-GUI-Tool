"""Clean, modern Vercel-style UI theme for the application.

Emphasizes minimal borders, grayscale palette, and stark contrasts,
focusing entirely on content and typography instead of heavy shapes.
"""

# ─── Color Palette ──────────────────────────────────────────────────
COLORS = {
    # Backgrounds
    "bg_primary":       "#0f172a",      # Deep slate background
    "bg_secondary":     "#1e293b",      # Slate 800 surfaces
    "bg_tertiary":      "#334155",      # Slate 700
    "bg_hover":         "#2dd4bf",      # Teal hover accent
    "bg_selected":      "#14b8a6",      # Teal active accent
    "bg_input":         "#0b1120",      # Very deep slate for inputs
    "bg_card":          "#1e293b",      # Soft slate for cards

    # Borders
    "border_primary":   "#334155",      # Slate 700
    "border_secondary": "#475569",      # Slate 600
    "border_focus":     "#2dd4bf",      # Teal focus
    
    # Text
    "text_primary":     "#f8fafc",      # Slate 50
    "text_secondary":   "#94a3b8",      # Slate 400
    "text_tertiary":    "#64748b",      # Slate 500
    "text_link":        "#2dd4bf",      # Teal 400
    
    # Accents
    "accent_blue":      "#38bdf8",      # Light blue
    "accent_green":     "#10b981",      # Emerald
    "accent_red":       "#ef4444",      # Red
    "accent_orange":    "#f59e0b",      # Amber
    "accent_purple":    "#8b5cf6",      # Violet
    
    # Scrollbar
    "scrollbar_bg":     "#0f172a",
    "scrollbar_handle": "#334155",
    "scrollbar_hover":  "#475569",
}

# ─── Font Settings ──────────────────────────────────────────────────
FONTS = {
    "family":       "'Inter', 'Segoe UI', 'Helvetica Neue', sans-serif",
    "family_mono":  "'JetBrains Mono', 'Fira Code', 'Menlo', monospace",
    "size_xs":      "11px",
    "size_sm":      "12px",
    "size_base":    "14px",
    "size_lg":      "16px",
    "size_xl":      "20px",
    "size_2xl":     "28px",
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
        background-color: {c['bg_primary']};
        border-right: 1px solid {c['border_primary']};
        min-width: 250px;
        max-width: 250px;
    }}
    
    #sidebar_title {{
        font-size: {f['size_xl']};
        font-weight: 800;
        color: {c['text_primary']};
        padding: 36px 24px 20px 24px;
        letter-spacing: -0.5px;
    }}
    
    QPushButton#nav_button {{
        background-color: transparent;
        color: {c['text_secondary']};
        border: none;
        border-radius: 8px;
        padding: 12px 20px;
        text-align: left;
        font-size: {f['size_base']};
        font-weight: 500;
        margin: 4px 16px;
    }}
    
    QPushButton#nav_button:hover {{
        background-color: {c['bg_secondary']};
        color: {c['text_primary']};
    }}
    
    QPushButton#nav_button[active="true"] {{
        background-color: {c['bg_selected']};
        color: #ffffff;
        font-weight: 700;
    }}
    
    /* ────────── Content Area ────────── */
    
    #content_area {{
        background-color: {c['bg_primary']};
    }}

    #progress_bar_slot {{
        background-color: {c['bg_primary']};
    }}
    
    #page_header {{
        font-size: 32px;
        font-weight: 800;
        color: {c['text_primary']};
        margin: 0px;
        padding: 36px 0px 8px 0px;
        letter-spacing: -0.5px;
    }}
    
    #page_subheader {{
        font-size: {f['size_lg']};
        color: {c['text_secondary']};
        margin: 0px;
        padding: 0px 0px 32px 0px;
    }}
    
    /* ────────── Cards ────────── */
    
    QFrame#card {{
        background-color: {c['bg_card']};
        border: 1px solid {c['border_primary']};
        border-radius: 12px;
        padding: 20px;
    }}
    
    QFrame#card:hover {{
        border-color: {c['border_secondary']};
        background-color: #212e42;
    }}
    
    /* ────────── Stats Card ────────── */
    
    QFrame#stats_card {{
        background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {c['bg_card']}, stop:1 {c['bg_tertiary']});
        border: 1px solid {c['border_primary']};
        border-radius: 12px;
        padding: 24px;
        min-height: 80px;
    }}
    
    QLabel#stats_number {{
        font-size: 36px;
        font-weight: 800;
        color: {c['bg_selected']};
        letter-spacing: -1px;
    }}
    
    QLabel#stats_label {{
        font-size: {f['size_base']};
        color: {c['text_primary']};
        font-weight: 600;
    }}
    
    /* ────────── Buttons ────────── */
    
    QPushButton#primary_button {{
        background-color: {c['bg_selected']};
        color: #ffffff;
        border: none;
        border-radius: 8px;
        padding: 10px 20px;
        min-height: 36px;
        font-size: {f['size_base']};
        font-weight: 700;
        min-width: 120px;
    }}
    
    QPushButton#primary_button:hover {{
        background-color: {c['bg_hover']};
    }}
    
    QPushButton#primary_button:pressed {{
        background-color: #0d9488;
    }}
    
    QPushButton#primary_button:disabled {{
        background-color: {c['bg_tertiary']};
        color: {c['text_tertiary']};
    }}
    
    QPushButton#danger_button {{
        background-color: transparent;
        color: {c['accent_red']};
        border: 1px solid {c['border_primary']};
        border-radius: 8px;
        padding: 8px 20px;
        min-height: 36px;
        font-size: {f['size_base']};
        font-weight: 600;
    }}
    
    QPushButton#danger_button:hover {{
        border-color: {c['accent_red']};
        background-color: rgba(239, 68, 68, 0.1);
    }}

    QPushButton#danger_button:pressed {{
        background-color: rgba(239, 68, 68, 0.2);
    }}
    
    QPushButton#success_button {{
        background-color: transparent;
        color: {c['accent_green']};
        border: 1px solid {c['border_primary']};
        border-radius: 8px;
        padding: 8px 20px;
        min-height: 36px;
        font-size: {f['size_base']};
        font-weight: 600;
    }}
    
    QPushButton#success_button:hover {{
        border-color: {c['accent_green']};
        background-color: rgba(16, 185, 129, 0.1);
    }}
    
    /* ────────── Search Input ────────── */
    
    QLineEdit#search_input {{
        background-color: {c['bg_primary']};
        color: {c['text_primary']};
        border: 1px solid {c['border_primary']};
        border-radius: 6px;
        padding: 6px 16px;
        min-height: 24px;
        font-size: {f['size_base']};
        selection-background-color: {c['text_secondary']};
    }}
    
    QLineEdit#search_input:focus {{
        border-color: {c['border_focus']};
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
        width: 8px;
        border-radius: 4px;
        margin: 0;
    }}
    
    QScrollBar::handle:vertical {{
        background-color: {c['scrollbar_handle']};
        border-radius: 4px;
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
        height: 8px;
        border-radius: 4px;
    }}
    
    QScrollBar::handle:horizontal {{
        background-color: {c['scrollbar_handle']};
        border-radius: 4px;
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
        color: {c['text_primary']};
        border: 1px solid {c['border_primary']};
        border-radius: 6px;
        padding: 16px;
        font-family: {f['family_mono']};
        font-size: {f['size_sm']};
        selection-background-color: {c['border_primary']};
    }}
    
    /* ────────── Progress Bar ────────── */
    
    QProgressBar {{
        background-color: {c['border_secondary']};
        border: none;
        border-radius: 2px;
        height: 4px;
        text-align: center;
    }}
    
    QProgressBar::chunk {{
        background-color: {c['text_primary']};
        border-radius: 2px;
    }}
    
    /* ────────── Tooltips ────────── */
    
    QToolTip {{
        background-color: {c['bg_primary']};
        color: {c['text_primary']};
        border: 1px solid {c['border_primary']};
        border-radius: 4px;
        padding: 6px 10px;
        font-size: {f['size_sm']};
    }}
    
    /* ────────── Combo Box ────────── */
    
    QComboBox {{
        background-color: {c['bg_primary']};
        color: {c['text_primary']};
        border: 1px solid {c['border_primary']};
        border-radius: 6px;
        padding: 6px 12px;
        min-height: 24px;
        font-size: {f['size_base']};
        min-width: 140px;
    }}
    
    QComboBox:hover {{
        border-color: {c['text_secondary']};
    }}
    
    QComboBox::drop-down {{
        border: none;
        padding-right: 8px;
    }}
    
    QComboBox QAbstractItemView {{
        background-color: {c['bg_primary']};
        color: {c['text_primary']};
        border: 1px solid {c['border_primary']};
        border-radius: 6px;
        selection-background-color: {c['bg_secondary']};
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
        font-size: {f['size_base']};
        font-weight: 500;
        margin-right: 8px;
    }}
    
    QTabBar::tab:hover {{
        color: {c['text_primary']};
    }}
    
    QTabBar::tab:selected {{
        color: {c['text_primary']};
        border-bottom: 2px solid {c['text_primary']};
        font-weight: 600;
    }}
    
    /* ────────── Separator ────────── */
    
    QFrame#separator {{
        background-color: transparent;
        max-height: 0px;
        margin: 0px;
        border: none;
    }}
    
    /* ────────── Loading Indicator ────────── */
    
    QLabel#loading_label {{
        color: {c['text_secondary']};
        font-size: {f['size_lg']};
        padding: 40px;
    }}
    """
