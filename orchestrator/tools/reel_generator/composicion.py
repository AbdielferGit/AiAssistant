"""Composición del frame completo: fondo animado + barra de progreso +
identidad (avatar/handle) + ícono o mockup del beat + subtítulo en inglés.
Es la única función que junta paleta (constantes.py), utilidades de dibujo
(dibujo_utils.py) e íconos/mockups (mockups.py) en una imagen final.
Separado del resto en la modularización de 2026-09-19."""
from __future__ import annotations

import math

from .constantes import ALTO, ANCHO, BLANCO, MINT, TEMAS, Beat
from .dibujo_utils import (
    _ICONO_PX,
    _TARJETA,
    _cargar_fuente,
    _dibujar_destellos,
    _dibujar_glow,
    _envolver_texto,
    _recortar_fondo,
)
from .iconos import ICON_VISUALES, _GLOW_COLOR
from .mockups import MOCKUP_VISUALES


def _componer_frame(beat: Beat, fase: float, indice: int, total: int, tema: str = "rive"):
    from PIL import Image, ImageDraw

    paleta = TEMAS[tema]
    img = _recortar_fondo(indice, total, fase, tema).convert("RGB")
    overlay = Image.new("RGBA", (ANCHO, ALTO), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Barra de progreso estilo Reel (un segmento por beat)
    margen, gap = 40, 8
    ancho_seg = (ANCHO - margen * 2 - gap * (total - 1)) / total
    for i in range(total):
        x0 = margen + i * (ancho_seg + gap)
        y0, y1 = 44, 50
        draw.rounded_rectangle([x0, y0, x0 + ancho_seg, y1], radius=3, fill=(255, 255, 255, 60))
        if i < indice:
            draw.rounded_rectangle([x0, y0, x0 + ancho_seg, y1], radius=3, fill=MINT + (255,))
        elif i == indice:
            draw.rounded_rectangle([x0, y0, x0 + ancho_seg * fase, y1], radius=3, fill=MINT + (255,))

    # Fila de identidad (avatar + handle), estilo IG — según el tema
    fuente_handle = _cargar_fuente(30, 500)
    draw.ellipse([margen, 76, margen + 56, 132], fill=paleta["avatar_bg"])
    fuente_ini = _cargar_fuente(22, 600)
    draw.text((margen + 28, 104), paleta["iniciales"], font=fuente_ini, anchor="mm", fill=BLANCO)
    draw.text((margen + 72, 104), paleta["handle"], font=fuente_handle, anchor="lm", fill=BLANCO)

    if beat.visual in MOCKUP_VISUALES:
        # Mockups: sombra + glow suave detrás de toda la tarjeta, sin
        # destellos (se vería recargado sobre una interfaz).
        centro = ((_TARJETA[0] + _TARJETA[2]) // 2, (_TARJETA[1] + _TARJETA[3]) // 2)
        intensidad = 0.35 + 0.1 * math.sin(fase * 2 * math.pi * 0.8)
        _dibujar_glow(overlay, centro, paleta["glow"], radio=int((_TARJETA[2] - _TARJETA[0]) * 0.6), intensidad=intensidad)
        MOCKUP_VISUALES[beat.visual](overlay, draw, fase)
    else:
        # Halo + destellos detrás del ícono, y el ícono encima — más
        # atractivo que un dibujo suelto sobre fondo plano.
        centro_icono = (ANCHO // 2, 560 + _ICONO_PX // 2)
        color_glow = _GLOW_COLOR.get(beat.visual, paleta["glow"])
        intensidad = 0.55 + 0.25 * math.sin(fase * 2 * math.pi * 1.4)
        _dibujar_glow(overlay, centro_icono, color_glow, radio=int(_ICONO_PX * 0.62), intensidad=intensidad)
        _dibujar_destellos(draw, centro_icono, fase)

        icono = Image.new("RGBA", (_ICONO_PX, _ICONO_PX), (0, 0, 0, 0))
        ICON_VISUALES[beat.visual](ImageDraw.Draw(icono), fase)
        overlay.alpha_composite(icono, ((ANCHO - _ICONO_PX) // 2, 560))

    # Subtítulo en inglés, grande y sin caja de fondo — solo un contorno
    # oscuro en el propio texto para que siga siendo legible sobre el fondo
    # animado. El francés NUNCA se dibuja, solo se narra.
    fuente_sub = _cargar_fuente(58, 600)
    lineas = _envolver_texto(draw, beat.en, fuente_sub, ANCHO - 140)
    alto_linea = 72
    y0 = ALTO - 210 - len(lineas) * alto_linea
    for i, linea in enumerate(lineas):
        draw.text(
            (ANCHO / 2, y0 + i * alto_linea), linea, font=fuente_sub, anchor="ma",
            fill=BLANCO, stroke_width=6, stroke_fill=(9, 19, 17, 235),
        )

    img.paste(Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB"))
    return img
