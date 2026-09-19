"""Mockups reales del sitio TaskDoctor.ai (tema "taskdoctor") — cada
función recibe (overlay, draw, fase) y dibuja directo sobre el frame
completo dentro de dibujo_utils._TARJETA. Todo el copy es real, verificado
en vivo contra el sitio — nada acá es concepto (a diferencia de los
mockups de AiAssistant en mockups_aiassistant.py, que sí tienen una
pantalla marcada como concepto). Separado del resto en la modularización
de 2026-09-19."""
from __future__ import annotations

from .constantes import TD_GRIS_BORDE, TD_GRIS_TEXTO, TD_NARANJA, TD_NARANJA_CLARO, TD_NARANJA_DEEP, TD_TINTA
from .dibujo_utils import _PAD, _TARJETA, _cargar_fuente, _clamp01, _dibujar_tarjeta, _envolver_texto, _ease_out_back, _revelar


def _mockup_td_hero(overlay, draw, fase: float) -> None:
    """Portada real de TaskDoctor.ai — título, las 3 garantías de
    privacidad y el CTA de instalación, tal cual el sitio."""
    x0, y0, x1, y1 = _TARJETA
    _dibujar_tarjeta(overlay, x0, y0, x1, y1)
    cx0, cx1 = x0 + _PAD, x1 - _PAD
    y = y0 + 70

    f_h1 = _cargar_fuente(54, 800)
    lineas_h1 = (
        ("Find browser work", TD_TINTA, 0.00),
        ("worth automating.", TD_TINTA, 0.08),
        ("Without monitoring", TD_NARANJA, 0.20),
        ("employees.", TD_NARANJA, 0.28),
    )
    for texto, color, inicio in lineas_h1:
        a, dy = _revelar(fase, inicio, 0.2)
        draw.text((cx0, y - dy), texto, font=f_h1, anchor="lm", fill=color + (a,))
        y += 64
    y += 30

    f_body = _cargar_fuente(28, 500)
    a, dy = _revelar(fase, 0.42, 0.2)
    cuerpo = "Install the extension to spot repetitive work and choose what to automate first."
    for i, linea in enumerate(_envolver_texto(draw, cuerpo, f_body, cx1 - cx0)):
        draw.text((cx0, y + i * 40 - dy), linea, font=f_body, anchor="lm", fill=TD_GRIS_TEXTO + (a,))
    y += 110

    f_chip = _cargar_fuente(26, 600)
    for i, texto in enumerate(("No screenshots", "No page text", "No employee monitoring")):
        a, dy = _revelar(fase, 0.58 + i * 0.06, 0.16)
        if a > 2:
            yy = y - dy
            draw.ellipse([cx0, yy, cx0 + 34, yy + 34], fill=TD_NARANJA + (a,))
            draw.line([cx0 + 9, yy + 18, cx0 + 15, yy + 25, cx0 + 26, yy + 10], fill=(255, 255, 255, a), width=4, joint="curve")
            draw.text((cx0 + 48, yy + 17), texto, font=f_chip, anchor="lm", fill=TD_TINTA + (a,))
        y += 46

    y += 30
    f_btn = _cargar_fuente(30, 700)
    p = _ease_out_back(_clamp01((fase - 0.85) / 0.15))
    if p > 0.02:
        texto = "Install Free Extension"
        ancho = draw.textlength(texto, font=f_btn) + 80
        alto = 88
        escala = max(0.0, min(1.15, p))
        aw, ah = ancho * escala, alto * escala
        draw.rounded_rectangle([cx0, y, cx0 + aw, y + ah], radius=ah / 2, fill=TD_NARANJA + (255,))
        if escala > 0.6:
            draw.text((cx0 + aw / 2, y + ah / 2), texto, font=f_btn, anchor="mm", fill=(255, 255, 255, 255))


def _mockup_td_dashboard(overlay, draw, fase: float) -> None:
    """El panel real de 'esta semana' — 32% de oportunidades, 12.4 horas
    encontradas, y las 4 fuentes principales, tal cual el sitio."""
    x0, y0, x1, y1 = _TARJETA
    _dibujar_tarjeta(overlay, x0, y0, x1, y1)
    cx0, cx1 = x0 + _PAD, x1 - _PAD

    a, dy = _revelar(fase, 0.0, 0.15)
    draw.text((cx0, y0 + 60 - dy), "THIS WEEK", font=_cargar_fuente(24, 700), anchor="lm", fill=TD_NARANJA + (a,))
    a, dy = _revelar(fase, 0.06, 0.18)
    draw.text((cx0, y0 + 118 - dy), "Automation Opportunities", font=_cargar_fuente(38, 700), anchor="lm", fill=TD_TINTA + (a,))

    a, dy = _revelar(fase, 0.15, 0.25)
    draw.text((cx0, y0 + 220 - dy), "32%", font=_cargar_fuente(90, 800), anchor="lm", fill=TD_TINTA + (a,))
    a, dy = _revelar(fase, 0.3, 0.2)
    draw.text((cx0 + 230, y0 + 205 - dy), "12.4 hours found", font=_cargar_fuente(26, 600), anchor="lm", fill=TD_GRIS_TEXTO + (a,))
    if a > 2:
        chip_w = draw.textlength("$620/week est. savings", font=_cargar_fuente(22, 700)) + 36
        draw.rounded_rectangle([cx0 + 230, y0 + 225 - dy, cx0 + 230 + chip_w, y0 + 265 - dy], radius=18, fill=TD_NARANJA_CLARO + (a,))
        draw.text((cx0 + 248, y0 + 245 - dy), "$620/week est. savings", font=_cargar_fuente(22, 700), anchor="lm", fill=TD_NARANJA_DEEP + (a,))

    y_lista = y0 + 330
    a, dy = _revelar(fase, 0.42, 0.15)
    draw.text((cx0, y_lista - dy), "TOP OPPORTUNITY SOURCES", font=_cargar_fuente(22, 700), anchor="lm", fill=TD_GRIS_TEXTO + (a,))
    draw.line([(cx0, y_lista + 30), (cx1, y_lista + 30)], fill=TD_GRIS_BORDE + (255,), width=2)

    filas = [
        ("Tab Switching", 7.9, 0.52),
        ("Tool Hopping", 4.6, 0.64),
        ("Manual Copy/Paste", 3.1, 0.76),
        ("Repetitive Work", 2.9, 0.88),
    ]
    fila_y = y_lista + 66
    f_label = _cargar_fuente(28, 600)
    f_valor = _cargar_fuente(26, 700)
    for etiqueta, horas, inicio in filas:
        a, dy = _revelar(fase, inicio, 0.14)
        if a > 2:
            yy = fila_y - dy
            draw.text((cx0, yy), etiqueta, font=f_label, anchor="lm", fill=TD_TINTA + (a,))
            draw.text((cx1, yy), f"{horas}h", font=f_valor, anchor="rm", fill=TD_NARANJA + (a,))
            by = yy + 34
            draw.rounded_rectangle([cx0, by, cx1, by + 12], radius=6, fill=TD_GRIS_BORDE + (a,))
            avance = min(1.0, horas / 8.0)
            draw.rounded_rectangle([cx0, by, cx0 + (cx1 - cx0) * avance, by + 12], radius=6, fill=TD_NARANJA + (a,))
        fila_y += 92


def _mockup_td_privacy(overlay, draw, fase: float) -> None:
    """La cuadrícula real de garantías de privacidad — 'construido para
    eficiencia, no para vigilar empleados'. Todo verificado en el sitio,
    nada de esto es un concepto."""
    x0, y0, x1, y1 = _TARJETA
    _dibujar_tarjeta(overlay, x0, y0, x1, y1)
    cx0, cx1 = x0 + _PAD, x1 - _PAD

    f_h2 = _cargar_fuente(42, 800)
    for i, (texto, inicio) in enumerate((
        ("Built for business", 0.0), ("efficiency, not", 0.06), ("employee monitoring.", 0.12),
    )):
        a, dy = _revelar(fase, inicio, 0.2)
        draw.text((cx0, y0 + 70 + i * 56 - dy), texto, font=f_h2, anchor="lm", fill=TD_TINTA + (a,))

    items = ["No Screenshots", "No Page Content", "No Messages", "No Passwords", "No Personal Data", "No Employee Monitoring"]
    col_w = (cx1 - cx0 - 30) / 2
    f_item = _cargar_fuente(24, 600)
    fila_y0 = y0 + 300
    for i, texto in enumerate(items):
        col, fila = i % 2, i // 2
        a, dy = _revelar(fase, 0.32 + fila * 0.14 + col * 0.03, 0.16)
        if a > 2:
            cx = cx0 + col * (col_w + 30)
            yy = fila_y0 + fila * 90 - dy
            draw.ellipse([cx, yy, cx + 30, yy + 30], fill=TD_NARANJA + (a,))
            draw.line([cx + 8, yy + 16, cx + 13, yy + 22, cx + 23, yy + 9], fill=(255, 255, 255, a), width=3, joint="curve")
            for j, linea in enumerate(_envolver_texto(draw, texto, f_item, col_w - 44)):
                draw.text((cx + 42, yy + 15 + j * 30), linea, font=f_item, anchor="lm", fill=TD_TINTA + (a,))

    a, dy = _revelar(fase, 0.85, 0.15)
    draw.text(((cx0 + cx1) / 2, y1 - 55 - dy), "Verified on taskdoctor.ai", font=_cargar_fuente(20, 600), anchor="mm", fill=TD_GRIS_TEXTO + (a,))


def _mockup_td_cta(overlay, draw, fase: float) -> None:
    """Cierre real — instalar la extensión gratis, funciona en Chrome."""
    x0, y0, x1, y1 = _TARJETA
    _dibujar_tarjeta(overlay, x0, y0, x1, y1)
    cx0, cx1 = x0 + _PAD, x1 - _PAD
    y = y0 + 90

    f_h1 = _cargar_fuente(50, 800)
    for i, (texto, inicio) in enumerate((("Install the", 0.0), ("extension free.", 0.1))):
        a, dy = _revelar(fase, inicio, 0.2)
        draw.text((cx0, y + i * 64 - dy), texto, font=f_h1, anchor="lm", fill=TD_TINTA + (a,))
    y += 170

    a, dy = _revelar(fase, 0.28, 0.2)
    draw.text((cx0, y - dy), "Free to start. Under 1 minute to set up.", font=_cargar_fuente(28, 500), anchor="lm", fill=TD_GRIS_TEXTO + (a,))
    y += 80

    f_btn = _cargar_fuente(34, 700)
    p = _ease_out_back(_clamp01((fase - 0.45) / 0.25))
    if p > 0.02:
        texto = "Install Free Extension"
        ancho = draw.textlength(texto, font=f_btn) + 90
        alto = 100
        escala = max(0.0, min(1.15, p))
        aw, ah = ancho * escala, alto * escala
        cx = cx0 + aw / 2
        draw.rounded_rectangle([cx0, y, cx0 + aw, y + ah], radius=ah / 2, fill=TD_NARANJA + (255,))
        if escala > 0.6:
            draw.text((cx0 + aw / 2, y + ah / 2), texto, font=f_btn, anchor="mm", fill=(255, 255, 255, 255))
        # Anillos de "ping" — invita a tocar. OJO: ImageDraw sobre RGBA no
        # mezcla, sobrescribe el pixel — dibujar un anillo semi-transparente
        # directo sobre el botón ya opaco lo deja mal (termina fundiéndose
        # con el fondo al componer, no con el botón). Se dibuja en un
        # parche aparte y se pega con alpha_composite, como el glow.
        from PIL import Image as _Image, ImageDraw as _ImageDraw

        for n in range(2):
            fase_ping = ((fase - 0.45) / 0.55 + n * 0.5) % 1.0
            rr = 60 + fase_ping * 50
            alpha = int(140 * (1 - fase_ping))
            if alpha > 0 and fase > 0.45:
                lado = int(rr * 2 + 20)
                parche = _Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
                _ImageDraw.Draw(parche).ellipse([10, 10, lado - 10, lado - 10], outline=TD_NARANJA + (alpha,), width=4)
                cy = y + ah / 2
                overlay.alpha_composite(parche, (int(cx - lado / 2), int(cy - lado / 2)))
    y += 140

    a, dy = _revelar(fase, 0.75, 0.2)
    draw.text((cx0, y - dy), "Works on Chrome. More browsers coming soon.", font=_cargar_fuente(24, 500), anchor="lm", fill=TD_GRIS_TEXTO + (a,))
