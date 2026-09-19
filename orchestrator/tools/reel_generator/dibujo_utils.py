"""Utilidades de dibujo compartidas por íconos y mockups: fondo animado
(mesh gradient con paneo), glow/destellos, tarjeta de mockup con sombra,
fuentes/envoltura de texto, y las curvas de easing. Nada acá conoce una
marca ni un producto en particular — eso vive en iconos.py/mockups_*.py.
Separado del resto en la modularización de 2026-09-19."""
from __future__ import annotations

import math

from .constantes import ALTO, ANCHO, CREMA, FONT_PATH, GRIS_BORDE, MINT, TEMAS

# --- easing -----------------------------------------------------------------

def _ease_out(t: float) -> float:
    return 1 - (1 - t) ** 3


def _ease_out_back(t: float, overshoot: float = 1.7) -> float:
    """Rebote suave (overshoot y asienta) — para que los elementos 'salten'
    al aparecer en vez de solo crecer, se siente más vivo."""
    t -= 1
    return 1 + (overshoot + 1) * t ** 3 + overshoot * t ** 2


def _clamp01(t: float) -> float:
    return max(0.0, min(1.0, t))


def _revelar(fase: float, inicio: float, duracion: float = 0.22):
    """Progreso (0..1) de una aparición con deslizamiento hacia arriba —
    devuelve (alpha_0_255, desplazamiento_y_px)."""
    p = _ease_out(_clamp01((fase - inicio) / duracion))
    return int(255 * p), (1 - p) * 22


# --- fuentes / texto ---------------------------------------------------------

def _cargar_fuente(tam: int, peso: int = 500):
    from PIL import ImageFont

    fuente = ImageFont.truetype(str(FONT_PATH), tam)
    try:
        fuente.set_variation_by_axes([peso])  # Work Sans es variable-weight
    except Exception:
        pass  # build de Pillow/FreeType sin soporte a fuentes variables — se usa el peso por defecto
    return fuente


def _envolver_texto(draw, texto: str, fuente, ancho_max: int) -> list[str]:
    palabras = texto.split()
    lineas, actual = [], ""
    for palabra in palabras:
        prueba = f"{actual} {palabra}".strip()
        if draw.textlength(prueba, font=fuente) <= ancho_max:
            actual = prueba
        else:
            if actual:
                lineas.append(actual)
            actual = palabra
    if actual:
        lineas.append(actual)
    return lineas


# --- fondo animado (mesh gradient + manchas de color, con paneo lento) ----
# Se genera UNA sola vez por tema (más grande que el frame final) y cada
# frame recorta una ventana con un desplazamiento lento — así se ve vivo
# sin recalcular el blur 24 veces por segundo.

_FONDO_MARGEN = 240
_fondo_cache: dict = {}  # tema -> Image.Image, cacheado a nivel de módulo


def _fondo_base(tema: str):
    from PIL import Image, ImageDraw, ImageFilter

    if tema in _fondo_cache:
        return _fondo_cache[tema]

    paleta = TEMAS[tema]
    w, h = ANCHO + _FONDO_MARGEN * 2, ALTO + _FONDO_MARGEN * 2

    # Gradiente diagonal (una columna de 1px estirada — mucho más rápido
    # que pintar pixel a pixel).
    columna = Image.new("L", (1, h))
    for y in range(h):
        columna.putpixel((0, y), int(255 * y / h))
    mascara = columna.resize((w, h))
    base = Image.composite(
        Image.new("RGB", (w, h), paleta["fondo_b"]),
        Image.new("RGB", (w, h), paleta["fondo_a"]),
        mascara,
    ).convert("RGBA")

    # Manchas de color grandes y difuminadas — look "mesh gradient", mucho
    # más atractivo que un color plano.
    manchas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(manchas)
    posiciones = ((0.18, 0.16, 460), (0.88, 0.30, 560), (0.30, 0.86, 520), (0.80, 0.92, 420))
    for (fx, fy, r), (color, alpha) in zip(posiciones, paleta["manchas"]):
        cx, cy = w * fx, h * fy
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color + (alpha,))
    manchas = manchas.filter(ImageFilter.GaussianBlur(160))

    resultado = Image.alpha_composite(base, manchas).convert("RGB")
    _fondo_cache[tema] = resultado
    return resultado


def _recortar_fondo(indice: int, total: int, fase: float, tema: str):
    """Ventana del fondo grande para este frame — se desplaza lento y
    orgánico a lo largo de todo el reel."""
    fondo = _fondo_base(tema)
    t = (indice + fase) / max(total, 1)
    ang = t * 2 * math.pi
    ox = _FONDO_MARGEN + math.sin(ang * 0.9) * (_FONDO_MARGEN * 0.7)
    oy = _FONDO_MARGEN + math.cos(ang * 0.6) * (_FONDO_MARGEN * 0.5)
    return fondo.crop((int(ox), int(oy), int(ox) + ANCHO, int(oy) + ALTO))


# --- halo/glow detrás del ícono (blur calculado 1 sola vez, reusado) ------

_glow_cache: dict = {}


def _glow_sprite(color: tuple, radio: int):
    from PIL import Image, ImageDraw, ImageFilter

    lado = radio * 4
    img = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    c = lado / 2
    draw.ellipse([c - radio, c - radio, c + radio, c + radio], fill=color + (255,))
    return img.filter(ImageFilter.GaussianBlur(radio * 0.45))


def _dibujar_glow(overlay, centro_xy: tuple, color: tuple, radio: int, intensidad: float) -> None:
    clave = (color, radio)
    sprite = _glow_cache.get(clave)
    if sprite is None:
        sprite = _glow_sprite(color, radio)
        _glow_cache[clave] = sprite
    intensidad = max(0.0, min(1.0, intensidad))
    if intensidad <= 0:
        return
    capa = sprite.copy()
    capa.putalpha(sprite.split()[3].point(lambda a: int(a * intensidad)))
    x = centro_xy[0] - sprite.width // 2
    y = centro_xy[1] - sprite.height // 2
    overlay.alpha_composite(capa, (x, y))


def _dibujar_destellos(draw, centro: tuple, fase: float) -> None:
    """Pequeños destellos que titilan alrededor del ícono — el detalle que
    le da vida y 'ganas de interactuar' a la escena."""
    cx, cy = centro
    posiciones = ((-280, -320, 0.0, 15), (300, -280, 0.35, 11), (-320, 280, 0.6, 13), (320, 320, 0.15, 17), (0, -390, 0.5, 10))
    for dx, dy, fase_off, tam in posiciones:
        brillo = max(0.0, math.sin((fase + fase_off) * 2 * math.pi * 1.6))
        if brillo <= 0.05:
            continue
        alpha = int(255 * brillo)
        x, y = cx + dx, cy + dy
        draw.line([(x - tam, y), (x + tam, y)], fill=MINT + (alpha,), width=3)
        draw.line([(x, y - tam), (x, y + tam)], fill=MINT + (alpha,), width=3)


# --- tarjeta de mockup (fondo blanco/crema + sombra) ------------------------
# Bounding box compartido por TODOS los mockups (AiAssistant y TaskDoctor
# por igual) dentro del frame de 1080x1920 — cada mockup posiciona su
# contenido relativo a esto.

_TARJETA = (90, 460, 990, 1500)  # x0, y0, x1, y1 dentro del frame 1080x1920
_PAD = 70
_ICONO_PX = 460  # lado del lienzo cuadrado donde se dibuja cada ícono abstracto

_sombra_cache: dict = {}


def _dibujar_tarjeta(overlay, x0: int, y0: int, x1: int, y1: int, radio: int = 40) -> None:
    """Tarjeta blanca/crema estilo 'card' real, con una sombra suave
    calculada una sola vez (se cachea — es igual en todos los frames de un
    mismo mockup) y reusada, no recalculada 24 veces por segundo."""
    from PIL import Image, ImageDraw, ImageFilter

    clave = (x0, y0, x1, y1, radio)
    sombra = _sombra_cache.get(clave)
    if sombra is None:
        capa = Image.new("RGBA", overlay.size, (0, 0, 0, 0))
        ImageDraw.Draw(capa).rounded_rectangle([x0, y0 + 26, x1, y1 + 26], radius=radio, fill=(0, 0, 0, 130))
        sombra = capa.filter(ImageFilter.GaussianBlur(30))
        _sombra_cache[clave] = sombra
    overlay.alpha_composite(sombra)
    ImageDraw.Draw(overlay).rounded_rectangle([x0, y0, x1, y1], radius=radio, fill=CREMA + (255,), outline=GRIS_BORDE + (255,), width=2)
