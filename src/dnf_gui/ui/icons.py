"""Vector icon painter for navigation and actions.

Draws crisp, antialiased, scalable icons using QPainter paths.
Deliberately avoids QIcon.fromTheme for consistent rendering across
different desktop environments and light/dark color schemes.
"""

from PyQt6.QtGui import QIcon, QPixmap, QPainter, QPainterPath, QColor, QPen
from PyQt6.QtCore import Qt, QRectF, QPointF


def paint_icon(kind: str, color: QColor | str, size: int = 20) -> QPixmap:
    """Render a vector icon of the requested kind into a QPixmap."""
    if isinstance(color, str):
        color = QColor(color)

    scale = 2  # high-DPI supersampling
    px_size = size * scale
    pixmap = QPixmap(px_size, px_size)
    pixmap.fill(Qt.GlobalColor.transparent)

    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

    _draw(p, kind, float(px_size), color)
    p.end()

    pixmap.setDevicePixelRatio(scale)
    return pixmap


def make_icon(kind: str, color: QColor | str, size: int = 20) -> QIcon:
    """Create a QIcon from the vector painter."""
    return QIcon(paint_icon(kind, color, size))


def _draw(p: QPainter, kind: str, s: float, color: QColor):
    """Draw the icon path within an s x s bounding box."""
    pen = QPen(color)
    pen.setWidthF(max(1.8, s * 0.075))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)

    cx, cy = s / 2.0, s / 2.0

    if kind == "updates":
        # Two elegant looping sync arrows with directional arrowheads
        r = s * 0.30
        box = QRectF(cx - r, cy - r, 2 * r, 2 * r)
        p.drawArc(box, int(35 * 16), int(120 * 16))
        p.drawArc(box, int(215 * 16), int(120 * 16))
        # Top right arrow tip
        p.drawLine(QPointF(cx + r * 0.95, cy - r * 0.45), QPointF(cx + r * 0.95, cy - r * 0.05))
        p.drawLine(QPointF(cx + r * 0.95, cy - r * 0.05), QPointF(cx + r * 0.55, cy - r * 0.05))
        # Bottom left arrow tip
        p.drawLine(QPointF(cx - r * 0.95, cy + r * 0.45), QPointF(cx - r * 0.95, cy + r * 0.05))
        p.drawLine(QPointF(cx - r * 0.95, cy + r * 0.05), QPointF(cx - r * 0.55, cy + r * 0.05))

    elif kind == "installed":
        # Clean package box with opened lid flap
        x0, y0 = s * 0.20, s * 0.28
        w, h = s * 0.60, s * 0.52
        p.drawRoundedRect(QRectF(x0, y0, w, h), s * 0.06, s * 0.06)
        p.drawLine(QPointF(x0, y0 + h * 0.30), QPointF(x0 + w, y0 + h * 0.30))
        # Center seal handle
        seal_w = s * 0.18
        p.drawRoundedRect(QRectF(cx - seal_w / 2, y0 + h * 0.20, seal_w, s * 0.16), s * 0.04, s * 0.04)

    elif kind == "flatpak":
        # Isometric 3D application container cube
        path = QPainterPath()
        path.moveTo(cx, s * 0.18)
        path.lineTo(s * 0.78, s * 0.33)
        path.lineTo(s * 0.78, s * 0.67)
        path.lineTo(cx, s * 0.82)
        path.lineTo(s * 0.22, s * 0.67)
        path.lineTo(s * 0.22, s * 0.33)
        path.closeSubpath()
        p.drawPath(path)
        # Inner isometric facets
        p.drawLine(QPointF(cx, s * 0.48), QPointF(cx, s * 0.82))
        p.drawLine(QPointF(cx, s * 0.48), QPointF(s * 0.78, s * 0.33))
        p.drawLine(QPointF(cx, s * 0.48), QPointF(s * 0.22, s * 0.33))

    elif kind == "sysinfo":
        # Precision CPU/SoC chip with symmetrical pin contacts
        bw = s * 0.48
        box = QRectF(cx - bw / 2, cy - bw / 2, bw, bw)
        p.drawRoundedRect(box, s * 0.08, s * 0.08)
        # Center die
        dw = s * 0.20
        p.drawRoundedRect(QRectF(cx - dw / 2, cy - dw / 2, dw, dw), s * 0.04, s * 0.04)
        # External connector pins
        for pos in (0.37, 0.63):
            v = s * pos
            p.drawLine(QPointF(v, s * 0.14), QPointF(v, s * 0.26))
            p.drawLine(QPointF(v, s * 0.74), QPointF(v, s * 0.86))
            p.drawLine(QPointF(s * 0.14, v), QPointF(s * 0.26, v))
            p.drawLine(QPointF(s * 0.74, v), QPointF(s * 0.86, v))

    elif kind == "tools":
        # Crossed precision wrench & screwdriver
        # Wrench
        w_path = QPainterPath()
        w_path.moveTo(s * 0.28, s * 0.72)
        w_path.lineTo(s * 0.58, s * 0.42)
        p.drawPath(w_path)
        # Wrench head
        wh = QPainterPath()
        wh.moveTo(s * 0.54, s * 0.46)
        wh.lineTo(s * 0.62, s * 0.38)
        wh.lineTo(s * 0.74, s * 0.42)
        wh.lineTo(s * 0.78, s * 0.30)
        wh.lineTo(s * 0.68, s * 0.20)
        wh.lineTo(s * 0.56, s * 0.24)
        wh.lineTo(s * 0.60, s * 0.36)
        wh.closeSubpath()
        p.drawPath(wh)
        # Screwdriver / hammer cross
        p.drawLine(QPointF(s * 0.72, s * 0.72), QPointF(s * 0.30, s * 0.30))
        p.drawLine(QPointF(s * 0.24, s * 0.36), QPointF(s * 0.36, s * 0.24))

    elif kind == "repos":
        # Layered server storage discs / database stack
        dw, dh = s * 0.54, s * 0.18
        rx, ry = cx - dw / 2, s * 0.22
        # Top disc
        p.drawRoundedRect(QRectF(rx, ry, dw, dh), dh / 2, dh / 2)
        # Middle disc
        p.drawRoundedRect(QRectF(rx, ry + s * 0.22, dw, dh), dh / 2, dh / 2)
        # Bottom disc
        p.drawRoundedRect(QRectF(rx, ry + s * 0.44, dw, dh), dh / 2, dh / 2)

    elif kind == "history":
        # Sleek clock face with counter-clockwise rewind arc
        r = s * 0.32
        box = QRectF(cx - r, cy - r, 2 * r, 2 * r)
        p.drawArc(box, int(50 * 16), int(290 * 16))
        # Arrow tip on the arc
        p.drawLine(QPointF(cx + r * 0.85, cy - r * 0.50), QPointF(cx + r * 0.95, cy - r * 0.15))
        p.drawLine(QPointF(cx + r * 0.95, cy - r * 0.15), QPointF(cx + r * 0.60, cy - r * 0.20))
        # Clock hands pointing backwards
        p.drawLine(QPointF(cx, cy), QPointF(cx, cy - s * 0.18))
        p.drawLine(QPointF(cx, cy), QPointF(cx - s * 0.12, cy))

    elif kind == "terminal":
        # Sleek window frame with prompt chevron and cursor
        x0, y0 = s * 0.16, s * 0.22
        w, h = s * 0.68, s * 0.54
        p.drawRoundedRect(QRectF(x0, y0, w, h), s * 0.08, s * 0.08)
        # Prompt chevron '>'
        path = QPainterPath()
        path.moveTo(s * 0.28, s * 0.40)
        path.lineTo(s * 0.40, s * 0.49)
        path.lineTo(s * 0.28, s * 0.58)
        p.drawPath(path)
        # Cursor '_'
        p.drawLine(QPointF(s * 0.46, s * 0.58), QPointF(s * 0.62, s * 0.58))

    elif kind == "settings":
        # Precision slider controls with tactile adjustment knobs
        knobs = (0.32, 0.68, 0.45)
        for i, y in enumerate((s * 0.30, s * 0.50, s * 0.70)):
            p.drawLine(QPointF(s * 0.20, y), QPointF(s * 0.80, y))
            kx = s * (0.20 + knobs[i] * 0.60)
            p.setBrush(color)
            p.drawEllipse(QPointF(kx, y), s * 0.065, s * 0.065)
            p.setBrush(Qt.BrushStyle.NoBrush)

    # ── Quick Tools Icons (Redesigned for Desktop KDE Fidelity) ──
    elif kind in ("rpmfusion_free", "rpmfusion_nonfree"):
        # Elegant software repository package box
        path = QPainterPath()
        path.moveTo(cx, s * 0.18)
        path.lineTo(s * 0.78, s * 0.33)
        path.lineTo(s * 0.78, s * 0.67)
        path.lineTo(cx, s * 0.82)
        path.lineTo(s * 0.22, s * 0.67)
        path.lineTo(s * 0.22, s * 0.33)
        path.closeSubpath()
        p.drawPath(path)
        p.drawLine(QPointF(cx, s * 0.48), QPointF(cx, s * 0.82))
        p.drawLine(QPointF(cx, s * 0.48), QPointF(s * 0.78, s * 0.33))
        p.drawLine(QPointF(cx, s * 0.48), QPointF(s * 0.22, s * 0.33))
        if kind == "rpmfusion_free":
            # Subtle checkmark badge in top facet
            p.drawLine(QPointF(cx - s * 0.06, s * 0.34), QPointF(cx - s * 0.01, s * 0.40))
            p.drawLine(QPointF(cx - s * 0.01, s * 0.40), QPointF(cx + s * 0.08, s * 0.28))

    elif kind == "add_flathub":
        # Flathub isometric box with plus badge
        path = QPainterPath()
        path.moveTo(cx, s * 0.18)
        path.lineTo(s * 0.78, s * 0.33)
        path.lineTo(s * 0.78, s * 0.67)
        path.lineTo(cx, s * 0.82)
        path.lineTo(s * 0.22, s * 0.67)
        path.lineTo(s * 0.22, s * 0.33)
        path.closeSubpath()
        p.drawPath(path)
        # Plus in center facet
        p.drawLine(QPointF(cx, s * 0.52), QPointF(cx, s * 0.66))
        p.drawLine(QPointF(cx - s * 0.07, s * 0.59), QPointF(cx + s * 0.07, s * 0.59))

    elif kind == "firmware_check":
        # Modern motherboard/CPU chip with test radar dot
        bw = s * 0.48
        p.drawRoundedRect(QRectF(cx - bw / 2, cy - bw / 2, bw, bw), s * 0.08, s * 0.08)
        # Inner die
        dw = s * 0.22
        p.drawRoundedRect(QRectF(cx - dw / 2, cy - dw / 2, dw, dw), s * 0.04, s * 0.04)
        # External connector pins (clean paired tracks)
        for pos in (0.38, 0.62):
            v = s * pos
            p.drawLine(QPointF(v, s * 0.15), QPointF(v, s * 0.26))
            p.drawLine(QPointF(v, s * 0.74), QPointF(v, s * 0.85))
            p.drawLine(QPointF(s * 0.15, v), QPointF(s * 0.26, v))
            p.drawLine(QPointF(s * 0.74, v), QPointF(s * 0.85, v))

    elif kind == "firmware_update":
        # Modern CPU chip with clean download/update arrow
        bw = s * 0.48
        p.drawRoundedRect(QRectF(cx - bw / 2, cy - bw / 2, bw, bw), s * 0.08, s * 0.08)
        for pos in (0.38, 0.62):
            v = s * pos
            p.drawLine(QPointF(v, s * 0.15), QPointF(v, s * 0.26))
            p.drawLine(QPointF(v, s * 0.74), QPointF(v, s * 0.85))
            p.drawLine(QPointF(s * 0.15, v), QPointF(s * 0.26, v))
            p.drawLine(QPointF(s * 0.74, v), QPointF(s * 0.85, v))
        # Arrow inside
        p.drawLine(QPointF(cx, cy - s * 0.12), QPointF(cx, cy + s * 0.12))
        p.drawLine(QPointF(cx - s * 0.08, cy + s * 0.04), QPointF(cx, cy + s * 0.12))
        p.drawLine(QPointF(cx + s * 0.08, cy + s * 0.04), QPointF(cx, cy + s * 0.12))

    elif kind == "clean_cache":
        # Minimalist angled sweep broom with sparkle stars
        # Handle
        p.drawLine(QPointF(s * 0.68, s * 0.20), QPointF(s * 0.44, s * 0.52))
        # Bristle base
        b_path = QPainterPath()
        b_path.moveTo(s * 0.48, s * 0.48)
        b_path.lineTo(s * 0.36, s * 0.56)
        b_path.lineTo(s * 0.22, s * 0.78)
        b_path.lineTo(s * 0.46, s * 0.82)
        b_path.lineTo(s * 0.56, s * 0.66)
        b_path.closeSubpath()
        p.drawPath(b_path)
        # Sweep lines
        p.drawLine(QPointF(s * 0.32, s * 0.66), QPointF(s * 0.30, s * 0.78))
        p.drawLine(QPointF(s * 0.42, s * 0.62), QPointF(s * 0.42, s * 0.80))
        # Sparkle star
        sp_x, sp_y = s * 0.72, s * 0.44
        p.drawLine(QPointF(sp_x, sp_y - s * 0.08), QPointF(sp_x, sp_y + s * 0.08))
        p.drawLine(QPointF(sp_x - s * 0.08, sp_y), QPointF(sp_x + s * 0.08, sp_y))

    elif kind == "rebuild_cache":
        # Layered database storage cylinders with refresh arc
        dw, dh = s * 0.54, s * 0.18
        rx = cx - dw / 2
        # Upper cylinder
        p.drawRoundedRect(QRectF(rx, s * 0.24, dw, dh), dh / 2, dh / 2)
        # Lower cylinder
        p.drawRoundedRect(QRectF(rx, s * 0.48, dw, dh), dh / 2, dh / 2)
        # Connecting vertical edges
        p.drawLine(QPointF(rx, s * 0.33), QPointF(rx, s * 0.57))
        p.drawLine(QPointF(rx + dw, s * 0.33), QPointF(rx + dw, s * 0.57))
        # Center status dot
        p.setBrush(color)
        p.drawEllipse(QPointF(cx, s * 0.33), s * 0.04, s * 0.04)
        p.drawEllipse(QPointF(cx, s * 0.57), s * 0.04, s * 0.04)
        p.setBrush(Qt.BrushStyle.NoBrush)

    elif kind == "distro_sync":
        # Precision double-loop circular synchronization arrows
        r = s * 0.29
        box = QRectF(cx - r, cy - r, 2 * r, 2 * r)
        p.drawArc(box, int(35 * 16), int(120 * 16))
        p.drawArc(box, int(215 * 16), int(120 * 16))
        # Arrowhead 1 (top right)
        p.drawLine(QPointF(cx + r * 0.95, cy - r * 0.42), QPointF(cx + r * 0.95, cy - r * 0.08))
        p.drawLine(QPointF(cx + r * 0.95, cy - r * 0.08), QPointF(cx + r * 0.58, cy - r * 0.08))
        # Arrowhead 2 (bottom left)
        p.drawLine(QPointF(cx - r * 0.95, cy + r * 0.42), QPointF(cx - r * 0.95, cy + r * 0.08))
        p.drawLine(QPointF(cx - r * 0.95, cy + r * 0.08), QPointF(cx - r * 0.58, cy + r * 0.08))

    elif kind == "sun":
        # Clean sun with center disc and 8 balanced radial rays
        r = s * 0.20
        p.drawEllipse(QPointF(cx, cy), r, r)
        ray_in = s * 0.30
        ray_out = s * 0.42
        diag_in = ray_in * 0.7071
        diag_out = ray_out * 0.7071
        # Cardinal rays
        p.drawLine(QPointF(cx, cy - ray_in), QPointF(cx, cy - ray_out))
        p.drawLine(QPointF(cx, cy + ray_in), QPointF(cx, cy + ray_out))
        p.drawLine(QPointF(cx - ray_in, cy), QPointF(cx - ray_out, cy))
        p.drawLine(QPointF(cx + ray_in, cy), QPointF(cx + ray_out, cy))
        # Diagonal rays
        p.drawLine(QPointF(cx - diag_in, cy - diag_in), QPointF(cx - diag_out, cy - diag_out))
        p.drawLine(QPointF(cx + diag_in, cy - diag_in), QPointF(cx + diag_out, cy - diag_out))
        p.drawLine(QPointF(cx - diag_in, cy + diag_in), QPointF(cx - diag_out, cy + diag_out))
        p.drawLine(QPointF(cx + diag_in, cy + diag_in), QPointF(cx + diag_out, cy + diag_out))

    elif kind == "moon":
        # Crescent moon
        path = QPainterPath()
        path.moveTo(cx + s * 0.08, cy - s * 0.36)
        path.cubicTo(
            cx - s * 0.36, cy - s * 0.28,
            cx - s * 0.36, cy + s * 0.28,
            cx + s * 0.08, cy + s * 0.36
        )
        path.cubicTo(
            cx - s * 0.14, cy + s * 0.20,
            cx - s * 0.14, cy - s * 0.20,
            cx + s * 0.08, cy - s * 0.36
        )
        path.closeSubpath()
        p.drawPath(path)

    else:
        # Graceful fallback: clean rounded rectangle with center bullet
        p.drawRoundedRect(QRectF(s * 0.2, s * 0.2, s * 0.6, s * 0.6), s * 0.1, s * 0.1)
        p.setBrush(color)
        p.drawEllipse(QPointF(cx, cy), s * 0.08, s * 0.08)

