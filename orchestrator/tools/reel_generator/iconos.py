"""Íconos abstractos dibujados a mano (tema "rive") — cada función recibe
(draw, fase) y dibuja sobre un lienzo cuadrado de dibujo_utils._ICONO_PX
de lado, ya centrado por composicion._componer_frame. Formas rellenas y
de colores vivos — nada de solo contornos finos, para que se vea
atractivo, no sobrio. Separado del resto en la modularización de
2026-09-19."""
from __future__ import annotations

import math

from .constantes import BLANCO, MINT, TEAL, TEAL_DEEP
from .dibujo_utils import _ICONO_PX, _ease_out, _ease_out_back

_GLOW_COLOR = {
    "simplify": MINT,
    "search": TEAL,
    "clock": TEAL_DEEP,
    "chat": MINT,
    "cta": TEAL,
}


def _visual_simplify(draw, fase: float) -> None:
    """Puntos de colores que convergen en un nodo brillante que rebota al
    asentarse — 'antes de un gran proyecto de IA, empiece más simple'."""
    centro = (_ICONO_PX / 2, _ICONO_PX / 2)
    puntos_origen = [(90, 110), (370, 96), (76, 336), (360, 352), (230, 60), (60, 220)]
    avance = _ease_out(min(fase / 0.7, 1.0))
    for idx, (ox, oy) in enumerate(puntos_origen):
        x = ox + (centro[0] - ox) * avance
        y = oy + (centro[1] - oy) * avance
        alpha = max(0.0, 1.0 - avance * 1.1)
        if alpha > 0:
            draw.line([(x, y), centro], fill=TEAL_DEEP + (int(200 * alpha),), width=5)
            r = 14
            color = MINT if idx % 2 == 0 else TEAL
            draw.ellipse([x - r, y - r, x + r, y + r], fill=color + (255,))
    if fase > 0.5:
        t = _ease_out_back(min((fase - 0.5) / 0.4, 1.0))
        r = max(0.0, min(60.0, 46 * t))
        draw.ellipse([centro[0] - r - 10, centro[1] - r - 10, centro[0] + r + 10, centro[1] + r + 10],
                     outline=MINT + (160,), width=4)
        draw.ellipse([centro[0] - r, centro[1] - r, centro[0] + r, centro[1] + r], fill=MINT)


def _visual_search(draw, fase: float) -> None:
    """Barra de búsqueda llena de color con lupa recorriéndola, luego una
    tarjeta de resultado con check que rebota al aparecer — 'un sitio que
    se encuentra en Google'."""
    bx0, by0, bx1, by1 = 40, 190, 420, 264
    draw.rounded_rectangle([bx0, by0, bx1, by1], radius=37, fill=TEAL_DEEP + (255,), outline=MINT, width=5)
    despl = math.sin(min(fase / 0.65, 1.0) * math.pi) if fase < 0.65 else 0
    lx = bx0 + 66 + despl * 230
    ly = (by0 + by1) / 2
    draw.ellipse([lx - 26, ly - 26, lx + 26, ly + 26], outline=BLANCO, width=8, fill=TEAL + (90,))
    draw.line([lx + 17, ly + 17, lx + 40, ly + 40], fill=BLANCO, width=8)
    if fase > 0.55:
        t = _ease_out_back(min((fase - 0.55) / 0.35, 1.0))
        cy = 330 + max(0.0, (1 - min(t, 1.4)) * 40)
        alpha = int(255 * min(1.0, t + 0.3))
        draw.rounded_rectangle([bx0, cy, bx1, cy + 60], radius=16, fill=MINT + (max(0, min(255, alpha)),))
        draw.line([bx0 + 34, cy + 30, bx0 + 52, cy + 46, bx0 + 86, cy + 14], fill=TEAL_DEEP + (255,), width=7, joint="curve")


def _visual_clock(draw, fase: float) -> None:
    """Esfera de reloj llena de color con marcas de hora, manecilla
    girando rápido + íconos apareciendo con rebote — 'disponible a toda
    hora'."""
    cx, cy, r = 230, 240, 130
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=TEAL_DEEP + (255,), outline=MINT, width=6)
    for m in range(12):
        ang = m / 12 * 2 * math.pi
        x0, y0 = cx + math.sin(ang) * (r - 14), cy - math.cos(ang) * (r - 14)
        x1, y1 = cx + math.sin(ang) * (r - 30), cy - math.cos(ang) * (r - 30)
        draw.line([(x0, y0), (x1, y1)], fill=MINT + (180,), width=4)
    angulo = fase * 6 * 2 * math.pi
    hx = cx + math.sin(angulo) * (r - 34)
    hy = cy - math.cos(angulo) * (r - 34)
    draw.line([cx, cy, hx, hy], fill=BLANCO, width=8)
    draw.line([cx, cy, cx, cy - 56], fill=MINT, width=8)
    draw.ellipse([cx - 10, cy - 10, cx + 10, cy + 10], fill=BLANCO)
    posiciones = [(66, 46), (394, 46), (230, 20)]
    for i, (px, py) in enumerate(posiciones):
        umbral = 0.15 + i * 0.18
        if fase > umbral:
            a = min((fase - umbral) / 0.2, 1.0)
            rr = max(0.0, min(36.0, 30 * _ease_out_back(a)))
            draw.ellipse([px - rr, py - rr, px + rr, py + rr], fill=MINT)


def _visual_chat(draw, fase: float) -> None:
    """Burbuja de chat llena de color con puntos 'escribiendo' + destello
    de IA que pulsa — 'un agente que habla como usted'."""
    draw.rounded_rectangle([30, 110, 430, 320], radius=34, fill=TEAL_DEEP + (255,), outline=MINT, width=5)
    draw.polygon([(110, 320), (110, 366), (168, 320)], fill=TEAL_DEEP)
    for i, dx in enumerate((150, 230, 310)):
        fase_local = (fase * 2 - i * 0.18) % 1.0
        dy = 215 - abs(math.sin(fase_local * math.pi)) * 20
        draw.ellipse([dx - 14, dy - 14, dx + 14, dy + 14], fill=MINT)
    if fase > 0.4:
        pulso = 0.85 + 0.3 * math.sin((fase - 0.4) * 11)
        cx, cy, s = 388, 70, 30 * pulso
        pts = [(cx, cy - s), (cx + s * 0.28, cy - s * 0.28), (cx + s, cy),
               (cx + s * 0.28, cy + s * 0.28), (cx, cy + s), (cx - s * 0.28, cy + s * 0.28),
               (cx - s, cy), (cx - s * 0.28, cy - s * 0.28)]
        draw.polygon(pts, fill=MINT)


def _visual_cta(draw, fase: float) -> None:
    """Sobre abriéndose + insignia con anillos de 'ping' expandiéndose —
    cierre / llamado a la acción, invita a tocar."""
    t = _ease_out(min(fase / 0.45, 1.0))
    dy = (1 - t) * -18
    draw.rounded_rectangle([44, 140 + dy, 416, 300 + dy], radius=18, fill=TEAL_DEEP + (255,), outline=MINT, width=5)
    draw.line([(44, 148 + dy), (230, 260 + dy), (416, 148 + dy)], fill=MINT, width=7, joint="curve")
    if fase > 0.45:
        a = min((fase - 0.45) / 0.3, 1.0)
        r = max(0.0, min(70.0, 58 * _ease_out_back(a)))
        cx, cy = 230, 380
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=MINT)
        draw.line([cx - 26, cy + 2, cx - 8, cy + 22, cx + 30, cy - 20], fill=TEAL_DEEP + (255,), width=8, joint="curve")
        for n in range(2):
            fase_ping = ((fase - 0.45) / 0.55 + n * 0.5) % 1.0
            rr = 70 + fase_ping * 60
            alpha = int(160 * (1 - fase_ping))
            if alpha > 0:
                draw.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=MINT + (alpha,), width=4)


ICON_VISUALES = {
    "simplify": _visual_simplify,
    "search": _visual_search,
    "clock": _visual_clock,
    "chat": _visual_chat,
    "cta": _visual_cta,
}
