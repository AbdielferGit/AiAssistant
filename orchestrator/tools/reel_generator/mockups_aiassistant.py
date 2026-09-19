"""Mockups reales del sitio getaiassistant.app (tema "aiassistant") — cada
función recibe (overlay, draw, fase) y dibuja directo sobre el frame
completo dentro de dibujo_utils._TARJETA.

OJO (aclarado por el usuario 2026-09-19): AiAssistant como PRODUCTO
comercial ya no se comercializa aparte — es la herramienta que genera
estos reels, no algo que se le venda a un cliente (ver reels_defaults.py).
Este módulo se conserva intacto, sin usarse en la config activa, por si
hace falta reactivarlo más adelante. Separado del resto en la
modularización de 2026-09-19 — antes vivía mezclado con el resto de
reel_generator.py."""
from __future__ import annotations

import math

from .constantes import AZUL, CREMA, GRIS_BORDE, GRIS_TEXTO, LIMA, TINTA
from .dibujo_utils import _PAD, _TARJETA, _cargar_fuente, _clamp01, _dibujar_tarjeta, _envolver_texto, _ease_out_back, _revelar


def _mockup_hero(overlay, draw, fase: float) -> None:
    """Portada real del sitio — título, badge y CTA tal cual están en
    getaiassistant.app/en/."""
    x0, y0, x1, y1 = _TARJETA
    _dibujar_tarjeta(overlay, x0, y0, x1, y1)
    cx0, cx1 = x0 + _PAD, x1 - _PAD
    y = y0 + 60

    f_eyebrow = _cargar_fuente(24, 700)
    a, dy = _revelar(fase, 0.0, 0.2)
    draw.ellipse([cx0, y + 6 - dy, cx0 + 16, y + 22 - dy], fill=LIMA + (a,))
    for i, linea in enumerate(_envolver_texto(draw, "RESPONSIBLE ADOPTION · MEASURABLE RESULTS", f_eyebrow, cx1 - cx0 - 30)):
        draw.text((cx0 + 30, y + i * 32 - dy), linea, font=f_eyebrow, anchor="lm", fill=TINTA + (a,))
    y += 90

    f_h1 = _cargar_fuente(66, 700)
    a, dy = _revelar(fase, 0.15, 0.25)
    draw.text((cx0, y - dy), "Make AI work", font=f_h1, anchor="lm", fill=TINTA + (a,))
    y += 80
    a, dy = _revelar(fase, 0.3, 0.25)
    draw.text((cx0, y - dy), "as part of your team.", font=f_h1, anchor="lm", fill=AZUL + (a,))
    y += 110

    f_body = _cargar_fuente(30, 500)
    a, dy = _revelar(fase, 0.5, 0.25)
    cuerpo = "We guide your company from curiosity to real adoption — the strategy, processes and team support to move forward confidently."
    for i, linea in enumerate(_envolver_texto(draw, cuerpo, f_body, cx1 - cx0)):
        draw.text((cx0, y + i * 42 - dy), linea, font=f_body, anchor="lm", fill=GRIS_TEXTO + (a,))
    y += 170

    f_btn = _cargar_fuente(30, 700)
    p = _ease_out_back(_clamp01((fase - 0.7) / 0.3))
    if p > 0.02:
        texto = "Request your assessment  →"
        ancho = draw.textlength(texto, font=f_btn) + 80
        alto = 92
        bx0 = cx0
        by0 = y
        escala = max(0.0, min(1.15, p))
        aw, ah = ancho * escala, alto * escala
        draw.rounded_rectangle([bx0, by0, bx0 + aw, by0 + ah], radius=ah / 2, fill=AZUL + (255,))
        if escala > 0.6:
            draw.text((bx0 + aw / 2, by0 + ah / 2), texto, font=f_btn, anchor="mm", fill=(255, 255, 255, 255))


def _mockup_roadmap(overlay, draw, fase: float) -> None:
    """La hoja de ruta real del sitio — 3 pasos, progreso 68%, tal cual el
    dashboard de la home."""
    x0, y0, x1, y1 = _TARJETA
    _dibujar_tarjeta(overlay, x0, y0, x1, y1)
    cx0, cx1 = x0 + _PAD, x1 - _PAD

    f_eyebrow = _cargar_fuente(24, 700)
    a, dy = _revelar(fase, 0.0, 0.15)
    draw.text((cx0, y0 + 66 - dy), "ROADMAP", font=f_eyebrow, anchor="lm", fill=AZUL + (a,))

    f_titulo = _cargar_fuente(46, 700)
    a, dy = _revelar(fase, 0.1, 0.2)
    draw.text((cx0, y0 + 130 - dy), "AI adoption plan", font=f_titulo, anchor="lm", fill=TINTA + (a,))

    f_small = _cargar_fuente(24, 600)
    a, dy = _revelar(fase, 0.15, 0.2)
    draw.text((cx0, y0 + 200 - dy), "Team progress", font=f_small, anchor="lm", fill=GRIS_TEXTO + (a,))
    draw.text((cx1, y0 + 200 - dy), "68%", font=_cargar_fuente(36, 700), anchor="rm", fill=TINTA + (a,))

    pista_y = y0 + 230
    draw.rounded_rectangle([cx0, pista_y, cx1, pista_y + 18], radius=9, fill=GRIS_BORDE + (255,))
    avance = _clamp01(fase / 0.45) * 0.68
    if avance > 0:
        draw.rounded_rectangle([cx0, pista_y, cx0 + (cx1 - cx0) * avance, pista_y + 18], radius=9, fill=AZUL + (255,))

    filas = [
        ("check", TINTA, "Assessment", "Opportunities prioritized", "DONE", GRIS_TEXTO, 0.35),
        ("02", AZUL, "Implementation", "3 workflows in development", "NOW", AZUL, 0.55),
        ("03", GRIS_BORDE, "Adoption", "Training and support", "NEXT", GRIS_TEXTO, 0.75),
    ]
    fila_y = pista_y + 70
    f_num = _cargar_fuente(26, 700)
    f_fila_titulo = _cargar_fuente(32, 700)
    f_fila_sub = _cargar_fuente(24, 500)
    f_tag = _cargar_fuente(20, 700)
    for numero, color_badge, titulo, sub, tag, color_tag, inicio in filas:
        a, dy = _revelar(fase, inicio, 0.2)
        if a <= 2:
            fila_y += 145
            continue
        yy = fila_y - dy
        color_num_txt = (255, 255, 255, a) if color_badge != GRIS_BORDE else TINTA + (a,)
        draw.rounded_rectangle([cx0, yy, cx0 + 70, yy + 70], radius=18, fill=color_badge + (a,))
        if numero == "check":
            # el check se dibuja con trazos — el font no trae el glifo ✓
            draw.line([(cx0 + 20, yy + 36), (cx0 + 31, yy + 48), (cx0 + 52, yy + 24)], fill=color_num_txt, width=6, joint="curve")
        else:
            draw.text((cx0 + 35, yy + 35), numero, font=f_num, anchor="mm", fill=color_num_txt)
        draw.text((cx0 + 96, yy + 12), titulo, font=f_fila_titulo, anchor="lm", fill=TINTA + (a,))
        draw.text((cx0 + 96, yy + 50), sub, font=f_fila_sub, anchor="lm", fill=GRIS_TEXTO + (a,))
        draw.text((cx1, yy + 35), tag, font=f_tag, anchor="rm", fill=color_tag + (a,))
        draw.line([(cx0, yy + 110), (cx1, yy + 110)], fill=GRIS_BORDE + (a,), width=2)
        fila_y += 145


def _mockup_form(overlay, draw, fase: float) -> None:
    """El formulario real de diagnóstico — mismos campos y placeholders
    que getaiassistant.app/en/, termina el reel mostrando cómo se agenda
    la llamada."""
    x0, y0, x1, y1 = _TARJETA
    _dibujar_tarjeta(overlay, x0, y0, x1, y1)
    cx0, cx1 = x0 + _PAD, x1 - _PAD

    f_eyebrow = _cargar_fuente(24, 700)
    a, dy = _revelar(fase, 0.0, 0.15)
    draw.text((cx0, y0 + 60 - dy), "INITIAL ASSESSMENT", font=f_eyebrow, anchor="lm", fill=AZUL + (a,))

    f_titulo = _cargar_fuente(44, 700)
    a, dy = _revelar(fase, 0.05, 0.2)
    draw.text((cx0, y0 + 122 - dy), "Tell us about yourself", font=f_titulo, anchor="lm", fill=TINTA + (a,))
    draw.line([(cx0, y0 + 160), (cx1, y0 + 160)], fill=GRIS_BORDE + (255,), width=2)

    f_label = _cargar_fuente(24, 700)
    f_place = _cargar_fuente(26, 500)
    campos = [
        ("Name", "Your name", 0.12),
        ("Company", "Company name", 0.28),
        ("Work email", "you@company.com", 0.44),
        ("Team size", "Select an option", 0.60),
    ]
    campo_y = y0 + 200
    for etiqueta, placeholder, inicio in campos:
        a, dy = _revelar(fase, inicio, 0.16)
        if a > 2:
            yy = campo_y - dy
            draw.text((cx0, yy), etiqueta, font=f_label, anchor="lm", fill=TINTA + (a,))
            draw.rounded_rectangle([cx0, yy + 26, cx1, yy + 100], radius=14, fill=(255, 255, 255, min(a, 255)), outline=GRIS_BORDE + (a,), width=2)
            draw.text((cx0 + 26, yy + 63), placeholder, font=f_place, anchor="lm", fill=GRIS_TEXTO + (a,))
            # cursor parpadeante en el primer campo, mientras está "activo"
            if etiqueta == "Name" and inicio + 0.16 < fase < 0.28 and math.sin(fase * 46) > 0:
                draw.line([(cx0 + 26, yy + 45), (cx0 + 26, yy + 80)], fill=TINTA + (a,), width=3)
            if etiqueta == "Team size":
                # chevron dibujado — el font no trae el glifo ⌄
                cvx, cvy = cx1 - 30, yy + 60
                draw.line([(cvx - 10, cvy - 5), (cvx, cvy + 6), (cvx + 10, cvy - 5)], fill=GRIS_TEXTO + (a,), width=4, joint="curve")
        campo_y += 136

    f_btn = _cargar_fuente(30, 700)
    p = _ease_out_back(_clamp01((fase - 0.8) / 0.2))
    if p > 0.02:
        texto = "Book my assessment  →"
        ancho = draw.textlength(texto, font=f_btn) + 80
        alto = 88
        escala = max(0.0, min(1.15, p))
        aw, ah = ancho * escala, alto * escala
        draw.rounded_rectangle([cx0, campo_y, cx0 + aw, campo_y + ah], radius=ah / 2, fill=AZUL + (255,))
        if escala > 0.6:
            draw.text((cx0 + aw / 2, campo_y + ah / 2), texto, font=f_btn, anchor="mm", fill=(255, 255, 255, 255))


def _mockup_chat(overlay, draw, fase: float) -> None:
    """Concepto de chat con el mismo lenguaje visual del sitio — ESTO NO
    ES una captura real, getaiassistant.app todavía no tiene un chat en
    vivo (verificado, no hay ningún widget en la página). Se dibuja como
    concepto y se marca como tal en pantalla — no afirmar que ya existe."""
    x0, y0, x1, y1 = _TARJETA
    _dibujar_tarjeta(overlay, x0, y0, x1, y1)
    cx0, cx1 = x0 + _PAD, x1 - _PAD
    y = y0 + 60

    draw.ellipse([cx0, y, cx0 + 64, y + 64], fill=AZUL + (255,))
    draw.text((cx0 + 32, y + 32), "AI", font=_cargar_fuente(24, 700), anchor="mm", fill=(255, 255, 255, 255))
    draw.text((cx0 + 84, y + 14), "AiAssistant", font=_cargar_fuente(34, 700), anchor="lm", fill=TINTA + (255,))
    draw.ellipse([cx0 + 84, y + 44, cx0 + 96, y + 56], fill=LIMA + (255,))
    draw.text((cx0 + 106, y + 50), "Online", font=_cargar_fuente(22, 500), anchor="lm", fill=GRIS_TEXTO + (255,))
    y += 100
    draw.line([(cx0, y), (cx1, y)], fill=GRIS_BORDE + (255,), width=2)
    y += 40

    f_burbuja = _cargar_fuente(28, 500)

    def _burbuja(texto: str, y_tope: float, alineado_izq: bool, fondo, color_txt) -> float:
        ancho_max = int((cx1 - cx0) * 0.72) - 60
        lineas = _envolver_texto(draw, texto, f_burbuja, ancho_max)
        alto = 36 + len(lineas) * 38
        ancho = max(draw.textlength(l, font=f_burbuja) for l in lineas) + 60
        bx0 = cx0 if alineado_izq else cx1 - ancho
        draw.rounded_rectangle([bx0, y_tope, bx0 + ancho, y_tope + alto], radius=24, fill=fondo)
        for i, linea in enumerate(lineas):
            draw.text((bx0 + 30, y_tope + 18 + i * 38), linea, font=f_burbuja, anchor="lm", fill=color_txt)
        return alto

    a1, dy1 = _revelar(fase, 0.12, 0.2)
    if a1 > 2:
        alto = _burbuja("Hi! What would you like to improve first?", y - dy1, True, TINTA + (a1,), (255, 255, 255, a1))
        y += alto + 26

    a2, dy2 = _revelar(fase, 0.42, 0.2)
    if a2 > 2:
        alto = _burbuja("Reduce time spent on weekly reports.", y - dy2, False, CREMA + (a2,), TINTA + (a2,))
        y += alto + 26

    a3, dy3 = _revelar(fase, 0.68, 0.15)
    if a3 > 2:
        alto = 90
        draw.rounded_rectangle([cx0, y - dy3, cx0 + 160, y - dy3 + alto], radius=24, fill=TINTA + (a3,))
        for i, dx in enumerate((40, 80, 120)):
            fase_local = (fase * 3 - i * 0.2) % 1.0
            subida = abs(math.sin(fase_local * math.pi)) * 10
            cyy = y - dy3 + alto / 2 - subida
            draw.ellipse([cx0 + dx - 8, cyy - 8, cx0 + dx + 8, cyy + 8], fill=(255, 255, 255, a3))

    draw.text(((cx0 + cx1) / 2, y1 - 50), "CONCEPT · COMING SOON", font=_cargar_fuente(22, 700), anchor="mm", fill=GRIS_TEXTO + (210,))
