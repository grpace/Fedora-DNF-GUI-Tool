"""Minimal stroke icons drawn in code — no distro icon-theme dependency.

System icon themes (Breeze, Papirus, …) ship icons with fixed colors that
can vanish or clash on light/dark surfaces (e.g. white symbolic icons on a
light sidebar). These 9 navigation glyphs are painted with QPainter using
the *current theme* foreground color, so contrast is deterministic in both
modes. Every sidebar item gets exactly one icon, all in the same style.
"""

from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPen, QPixmap

KINDS = (
    "updates",
    "installed",
    "flatpak",
    "sysinfo",
    "tools",
    "repos",
    "history",
    "terminal",
    "settings",
)


def paint_icon(kind: str, color: QColor | str, size: int = 20) -> QPixmap:
    """Render a minimal stroke icon. Never raises — falls back to a dot.

    Always paints a fixed 48px master. Icon labels use setScaledContents
    so the glyph is scaled to fit the label: this keeps geometry correct
    on every display pipeline (native Wayland, XWayland, fractional
    scaling), where pixmap-DPR tricks and ratio queries proved unreliable
    and produced zoomed/cropped glyphs.
    """
    MASTER = 48
    pix = QPixmap(MASTER, MASTER)
    pix.fill(Qt.GlobalColor.transparent)
    try:
        qcolor = QColor(color) if isinstance(color, str) else QColor(color)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.scale(MASTER / float(size), MASTER / float(size))
        pen = QPen(qcolor)
        pen.setWidthF(max(1.4, size / 11.0))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        _draw(kind, p, float(size))
        p.end()
    except Exception:
        try:
            p.end()
        except Exception:
            pass
    return pix


def _draw(kind: str, p: QPainter, s: float) -> None:
    m = s * 0.20
    box = QRectF(m, m, s - 2 * m, s - 2 * m)
    cx, cy = s / 2.0, s / 2.0

    if kind == "updates":
        # Circular arrow centered on a common optical box: arc with a
        # small gap at top-right, head tangent to clockwise travel.
        r = s * 0.30
        head_deg = 70.0
        p.drawArc(QRectF(cx - r, cy - r, 2 * r, 2 * r),
                  int(head_deg * 16), int(285 * 16))
        a = math.radians(head_deg)
        tip = QPointF(cx + r * math.cos(a), cy - r * math.sin(a))
        tx, ty = math.sin(a), math.cos(a)      # clockwise tangent
        nx, ny = math.cos(a), -math.sin(a)     # outward normal
        len_, wid = s * 0.22, s * 0.12
        p1 = QPointF(tip.x() - tx * len_ + nx * wid,
                     tip.y() - ty * len_ + ny * wid)
        p2 = QPointF(tip.x() - tx * len_ - nx * wid,
                     tip.y() - ty * len_ - ny * wid)
        p.setBrush(p.pen().color())
        p.drawPolygon([tip, p1, p2])

    elif kind == "installed":
        # package box: body + lid
        p.drawRect(QRectF(s * 0.24, s * 0.36, s * 0.52, s * 0.42))
        p.drawRect(QRectF(s * 0.20, s * 0.24, s * 0.60, s * 0.14))
        p.drawLine(QPointF(cx, s * 0.38), QPointF(cx, s * 0.78))

    elif kind == "flatpak":
        # 2x2 grid of rounded squares
        g, gap = s * 0.30, s * 0.07
        x0, y0 = cx - g - gap / 2.0, cy - g - gap / 2.0
        for ix in (0, 1):
            for iy in (0, 1):
                p.drawRoundedRect(
                    QRectF(x0 + ix * (g + gap), y0 + iy * (g + gap), g, g),
                    s * 0.04, s * 0.04)

    elif kind == "sysinfo":
        # monitor + stand
        p.drawRoundedRect(QRectF(s * 0.18, s * 0.24, s * 0.64, s * 0.42),
                          s * 0.04, s * 0.04)
        p.drawLine(QPointF(cx, s * 0.66), QPointF(cx, s * 0.76))
        p.drawLine(QPointF(s * 0.36, s * 0.78), QPointF(s * 0.64, s * 0.78))

    elif kind == "tools":
        # gear: ring + 6 spokes
        p.drawEllipse(QPointF(cx, cy), s * 0.13, s * 0.13)
        for i in range(6):
            a = math.radians(i * 60.0)
            dx, dy = math.cos(a), math.sin(a)
            p.drawLine(QPointF(cx + dx * s * 0.17, cy + dy * s * 0.17),
                       QPointF(cx + dx * s * 0.28, cy + dy * s * 0.28))

    elif kind == "repos":
        # database cylinder, kept inside the common optical box
        x0, ww = s * 0.28, s * 0.44
        p.drawEllipse(QRectF(x0, s * 0.30, ww, s * 0.15))
        p.drawLine(QPointF(x0, s * 0.375), QPointF(x0, s * 0.625))
        p.drawLine(QPointF(x0 + ww, s * 0.375), QPointF(x0 + ww, s * 0.625))
        p.drawArc(QRectF(x0, s * 0.55, ww, s * 0.15), 180 * 16, 180 * 16)

    elif kind == "history":
        # clock + hands at ~10:10
        p.drawEllipse(QPointF(cx, cy), s * 0.30, s * 0.30)
        p.drawLine(QPointF(cx, cy), QPointF(cx - s * 0.13, cy - s * 0.06))
        p.drawLine(QPointF(cx, cy), QPointF(cx + s * 0.13, cy - s * 0.10))

    elif kind == "terminal":
        # window + prompt chevron
        p.drawRoundedRect(QRectF(s * 0.18, s * 0.26, s * 0.64, s * 0.48),
                          s * 0.05, s * 0.05)
        p.drawLine(QPointF(s * 0.32, s * 0.42), QPointF(s * 0.42, s * 0.50))
        p.drawLine(QPointF(s * 0.42, s * 0.50), QPointF(s * 0.32, s * 0.58))
        p.drawLine(QPointF(s * 0.48, s * 0.60), QPointF(s * 0.62, s * 0.60))

    elif kind == "settings":
        # three sliders with knobs
        knobs = (0.38, 0.62, 0.46)
        for i, y in enumerate((s * 0.32, s * 0.50, s * 0.68)):
            p.drawLine(QPointF(s * 0.22, y), QPointF(s * 0.78, y))
            kx = s * (0.22 + knobs[i] * 0.56)
            p.drawEllipse(QPointF(kx, y), s * 0.075, s * 0.075)

    else:
        p.drawEllipse(QPointF(cx, cy), s * 0.10, s * 0.10)

    _ = box
