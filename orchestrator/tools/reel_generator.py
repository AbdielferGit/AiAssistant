"""Generador de reels verticales (9:16) para Instagram/Facebook.

Toma un guion de "beats" (cada uno con texto en francés para narrar y
texto en inglés para subtitular) y produce un archivo .mp4 con:

- Narración en francés QUEBEQUENSE (voz neuronal fr-CA de Azure Speech —
  NUNCA francés de Francia, eso es un requisito explícito del proyecto).
- Subtítulo en pantalla SOLO en inglés — el francés vive únicamente en el
  audio, nunca se dibuja como texto. No mezclar los dos idiomas en
  pantalla.
- Una animación simple por beat, dibujada a mano con Pillow (círculos,
  líneas, texto) — sin After Effects, sin navegador headless. Cada beat
  tiene un `visual` de VISUALES (ver abajo) que decide qué se dibuja.
- La estética de marca de Rive Intelligente (azul marino / verde agua /
  destello menta — mismos tonos que assets/logo_concepto_v2_circular.svg
  en el proyecto de prospección).

Pensado para los guiones ya escritos como archivos .md en
`templates/redes_sociales/campana_sitio_web_solo/` y `suite_7_semanas/`
del proyecto BecameGrowthPartner/Prospection — cada beat de esa campaña
mapea 1 a 1 a un dict {fr, en, visual} acá.

Requiere (ver requirements.txt): Pillow, moviepy, imageio-ffmpeg,
azure-cognitiveservices-speech. Y las variables de entorno
AZURE_SPEECH_KEY / AZURE_SPEECH_REGION (ver .env.example) — sin ellas,
`generar_reel` devuelve un dict con status="error" y una explicación en
vez de lanzar una excepción sin manejar (mismo principio que
receptionist.py con negocio.yaml: falta configuración no debe romper el
arranque del orchestrator, solo esta función en particular).
"""
from __future__ import annotations

import logging
import math
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("orchestrator.tools.reel_generator")

REPO_ROOT = Path(__file__).resolve().parents[2]
FONT_PATH = REPO_ROOT / "orchestrator" / "assets" / "fonts" / "WorkSans-Variable.ttf"
SALIDA_DIR = REPO_ROOT / "data" / "reels"

# Formato vertical estándar de Reels/Stories.
ANCHO, ALTO = 1080, 1920
FPS = 24

# Paleta de marca — mismos valores que el logo (ver docs/identidad_marca.md
# del proyecto de prospección). No inventar colores nuevos acá.
NAVY = (21, 58, 70)
TEAL = (47, 167, 154)
TEAL_DEEP = (31, 127, 118)
MINT = (127, 231, 218)
BLANCO = (245, 247, 246)

VOZ_FR_CA_POR_DEFECTO = "fr-CA-Sylvie:DragonHDLatestNeural"  # ver docstring de _voz_azure para alternativas
DURACION_MIN_BEAT_SEG = 3.2  # aunque la frase sea muy corta, no menos que esto
COLCHON_TRAS_AUDIO_SEG = 0.6  # margen después de que termina la narración

# --- plantilla de audio (ver _construir_ssml) -------------------------------
# Calibrados a oído sobre reels de prueba reales — no cambiar sin escuchar
# el resultado primero. Verificado con Azure real que sí acepta decimales
# en `rate` (no hace falta redondear a entero).
#
# OJO con la voz HD (la que usamos por defecto): Azure documenta que las
# voces "...:DragonHDLatestNeural" ignoran <prosody> y <emphasis> — ESO ES
# FALSO, verificado en la práctica: a -3.5% vs +25% el audio generado da un
# tamaño (duración) claramente distinto. PLANTILLA_RITMO_PCT sí tiene
# efecto real con esta voz, igual que PLANTILLA_PAUSA_MS (el <break> de
# "||"). No confiar en esa tabla de la documentación sin probar en vivo.
PLANTILLA_RITMO_PCT = -1  # ritmo de la voz, % respecto al natural (negativo = más lento)
PLANTILLA_PAUSA_MS = 120  # duración de cada pausa "||" en el guion


@dataclass(frozen=True)
class Beat:
    fr: str  # se narra, nunca se dibuja en pantalla
    en: str  # se dibuja como subtítulo, nunca se narra
    visual: str  # una clave de VISUALES


# --- síntesis de voz -------------------------------------------------------

def _voz_azure(texto: str, destino_wav: Path) -> None:
    """Sintetiza `texto` con una voz neuronal fr-CA (Quebec) de Azure
    Cognitive Services Speech y la escribe en `destino_wav`.

    Por qué Azure y no otro proveedor: es el que tiene voces neuronales
    fr-CA genuinas y bien documentadas — no una voz de Francia con
    subtítulo "canadiense". Probadas y verificadas en vivo:
    fr-CA-Sylvie:DragonHDLatestNeural / fr-CA-Thierry:DragonHDLatestNeural
    (voces "HD", más naturales — la que se usa por defecto, ver nota sobre
    <prosody>/<emphasis> junto a PLANTILLA_RITMO_PCT más arriba) y las
    estándar fr-CA-SylvieNeural / fr-CA-AntoineNeural / fr-CA-JeanNeural /
    fr-CA-ThierryNeural (sí soportan rate/emphasis, suenan algo más
    robóticas). ElevenLabs y Google Cloud TTS también ofrecen fr-CA, pero
    no se implementaron acá — si se quiere agregar uno como alternativa,
    hacerlo como una función `_voz_<proveedor>` más y elegir por
    TTS_PROVIDER en .env (mismo patrón que negocio.yaml: nunca romper el
    arranque si falta configuración, solo esta función)."""
    import azure.cognitiveservices.speech as speechsdk

    key = os.getenv("AZURE_SPEECH_KEY", "")
    region = os.getenv("AZURE_SPEECH_REGION", "")
    if not key or not region:
        raise RuntimeError(
            "Faltan AZURE_SPEECH_KEY / AZURE_SPEECH_REGION en .env — "
            "necesarias para sintetizar voz en francés quebequense. Crea "
            "un recurso 'Speech' en Azure (tiene capa gratuita) y copia la "
            "clave y la región."
        )
    voz = os.getenv("AZURE_SPEECH_VOICE_FR_CA", VOZ_FR_CA_POR_DEFECTO)

    speech_config = speechsdk.SpeechConfig(subscription=key, region=region)
    speech_config.speech_synthesis_voice_name = voz
    audio_config = speechsdk.audio.AudioOutputConfig(filename=str(destino_wav))
    synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)

    ssml = _construir_ssml(texto, voz)
    resultado = synthesizer.speak_ssml_async(ssml).get()
    if resultado.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
        detalle = getattr(resultado, "cancellation_details", None)
        raise RuntimeError(f"Azure Speech no pudo sintetizar: {detalle.reason if detalle else resultado.reason}")


def _escapar_ssml(texto: str) -> str:
    return (
        texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        .replace('"', "&quot;").replace("'", "&apos;")
    )


def _construir_ssml(texto: str, voz: str) -> str:
    """Arma el SSML de un beat completo con pausas y entonación pensadas
    para sonar natural y motivador — no una narración plana.

    Dos marcadores que se pueden usar al escribir el `fr` de un beat (se
    procesan acá, nunca llegan a leerse en voz alta):

    - `||` inserta una pausa de respiración antes de lo que sigue. Úsalo
      antes del remate o del llamado a la acción de un beat, ej.:
      "Avant un gros projet d'IA, || il y a une étape plus simple."
    - `**así**` narra esa palabra o frase con énfasis. Úsalo en la palabra
      que le da la fuerza motivadora a la frase, ej.: "**Commencez
      simple.**" — no abusar, 1 énfasis por beat como máximo suena natural,
      más de eso suena forzado.

    Además, cualquier oración que termine en "?" se narra con una
    entonación ascendente hacia el final (como una pregunta real hecha en
    conversación) en vez del tono plano por defecto.

    Los valores concretos de ritmo y pausa viven en PLANTILLA_RITMO_PCT /
    PLANTILLA_PAUSA_MS (arriba) — verificado que Azure acepta decimales en
    `rate`, no hace falta redondear a entero."""
    oraciones = [o for o in re.split(r"(?<=[.!?])\s+", texto.strip()) if o]
    partes_ssml = []
    for oracion in oraciones:
        cuerpo = _aplicar_pausas_y_enfasis(oracion)
        if oracion.rstrip().endswith("?"):
            # Sube de tono hacia el final de la oración — entonación de
            # pregunta real, no un texto leído de corrido.
            cuerpo = f'<prosody contour="(60%,+6%) (100%,+14%)">{cuerpo}</prosody>'
        partes_ssml.append(cuerpo)
    cuerpo_total = " ".join(partes_ssml)
    return (
        f'<speak version="1.0" xml:lang="fr-CA" xmlns:mstts="https://www.w3.org/2001/mstts">'
        f'<voice name="{voz}"><prosody rate="{PLANTILLA_RITMO_PCT}%">{cuerpo_total}</prosody></voice>'
        f"</speak>"
    )


def _aplicar_pausas_y_enfasis(oracion: str) -> str:
    trozos = oracion.split("||")
    pausa = f'<break time="{PLANTILLA_PAUSA_MS}ms"/>'
    con_pausas = pausa.join(_escapar_ssml(t.strip()) for t in trozos)
    return re.sub(
        r"\*\*(.+?)\*\*",
        lambda m: f'<emphasis level="strong">{m.group(1)}</emphasis>',
        con_pausas,
    )


# --- fondo animado (mesh gradient + manchas de color, con paneo lento) ----
# Reemplaza el navy plano de antes. Se genera UNA sola vez (más grande que
# el frame final) y cada frame recorta una ventana con un desplazamiento
# lento — así se ve vivo sin recalcular el blur 24 veces por segundo.

# Paleta real de "AiAssistant by InnovaMontreal" (getaiassistant.app) —
# sacada en vivo del sitio (colores computados con getComputedStyle, no a
# ojo): fondo crema, tinta casi negra, azul de los CTA, verde lima del
# indicador de estado. No inventar tonos nuevos acá tampoco.
CREMA = (248, 247, 242)
TINTA = (20, 35, 44)
AZUL = (31, 72, 214)
LIMA = (201, 243, 107)
GRIS_BORDE = (225, 222, 212)
GRIS_TEXTO = (117, 123, 117)

# Cada "tema" define el fondo animado y la identidad (avatar/handle) del
# reel. "rive" = Rive Intelligente (marca original de este proyecto).
# "aiassistant" = AiAssistant by InnovaMontreal (getaiassistant.app, sitio
# real del usuario) — sin cuenta de Instagram confirmada todavía, el
# handle de acá es un placeholder hasta que exista una real.
TEMAS = {
    "rive": {
        "fondo_a": NAVY, "fondo_b": TEAL_DEEP,
        "manchas": ((MINT, 130), (TEAL, 120), (TEAL_DEEP, 170), (MINT, 95)),
        "glow": TEAL, "avatar_bg": TEAL, "iniciales": "RI", "handle": "riveintelligente",
    },
    "aiassistant": {
        "fondo_a": TINTA, "fondo_b": (16, 38, 89),
        "manchas": ((AZUL, 150), (LIMA, 90), (AZUL, 115), (LIMA, 70)),
        "glow": AZUL, "avatar_bg": AZUL, "iniciales": "AI", "handle": "AiAssistant",
    },
}

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


# --- "mockups" de sitio real (getaiassistant.app) --------------------------
# A diferencia de los íconos abstractos de abajo, estos dibujan directo
# sobre el frame completo (no un lienzo chico) — son una tarjeta de
# navegador/app con contenido real del sitio de AiAssistant by
# InnovaMontreal (copy verificado en vivo, versión EN del sitio — el
# francés NUNCA se dibuja, ver regla del proyecto). Cada función recibe
# (overlay, draw, fase).

_TARJETA = (90, 460, 990, 1500)  # x0, y0, x1, y1 dentro del frame 1080x1920
_PAD = 70

_sombra_cache: dict = {}


def _clamp01(t: float) -> float:
    return max(0.0, min(1.0, t))


def _revelar(fase: float, inicio: float, duracion: float = 0.22):
    """Progreso (0..1) de una aparición con deslizamiento hacia arriba —
    devuelve (alpha_0_255, desplazamiento_y_px)."""
    p = _ease_out(_clamp01((fase - inicio) / duracion))
    return int(255 * p), (1 - p) * 22


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


MOCKUP_VISUALES = {
    "mockup_hero": _mockup_hero,
    "mockup_roadmap": _mockup_roadmap,
    "mockup_form": _mockup_form,
    "mockup_chat": _mockup_chat,
}


# --- dibujo de cada "visual" (Pillow puro, sin librerías de animación) ----
# Cada función recibe fase (0..1, tiempo dentro del beat) y dibuja sobre
# `draw`, ya centrado en un lienzo de _ICONO_PX de lado, colocado por
# _componer_frame. Formas rellenas y de colores vivos — nada de solo
# contornos finos, para que se vea atractivo, no sobrio.

_ICONO_PX = 460

_GLOW_COLOR = {
    "simplify": MINT,
    "search": TEAL,
    "clock": TEAL_DEEP,
    "chat": MINT,
    "cta": TEAL,
}


def _ease_out(t: float) -> float:
    return 1 - (1 - t) ** 3


def _ease_out_back(t: float, overshoot: float = 1.7) -> float:
    """Rebote suave (overshoot y asienta) — para que los elementos 'salten'
    al aparecer en vez de solo crecer, se siente más vivo."""
    t -= 1
    return 1 + (overshoot + 1) * t ** 3 + overshoot * t ** 2


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

# Unión de los dos "vocabularios" de visual — sólo para validar la clave
# que llega en cada beat. _componer_frame decide cuál pipeline usar según
# a qué dict pertenece la clave (ver abajo).
VISUALES = {**ICON_VISUALES, **MOCKUP_VISUALES}


# --- composición del frame completo (chrome + icono + subtítulo) ---------

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
        _dibujar_glow(overlay, centro, AZUL, radio=int((_TARJETA[2] - _TARJETA[0]) * 0.6), intensidad=intensidad)
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


# --- ensamblado final -------------------------------------------------------

def _validar_beats(beats: list[dict], tema: str) -> str | None:
    if not beats:
        return "beats está vacío."
    for b in beats:
        if b.get("visual") not in VISUALES:
            return f"visual {b.get('visual')!r} no existe. Opciones: {sorted(VISUALES)}."
    if tema not in TEMAS:
        return f"tema {tema!r} no existe. Opciones: {sorted(TEMAS)}."
    if not FONT_PATH.exists():
        return f"Falta la fuente en {FONT_PATH}."
    return None


def generar_preview_visual(beats: list[dict], nombre_salida: str, tema: str = "rive", duracion_beat: float = 4.0) -> dict:
    """Genera SOLO el video (sin audio, sin llamar a Azure) — para
    aprobar el look de fondo/animación/mockups antes de gastar en síntesis
    de voz real. Mismo `_componer_frame` que `generar_reel`, cada beat dura
    `duracion_beat` segundos fijos en vez de calcularse del audio."""
    try:
        import numpy as np
        from moviepy import VideoClip, concatenate_videoclips
    except ImportError as exc:
        return {
            "status": "error",
            "detalle": (
                f"Falta una dependencia ({exc}). Corre "
                "`pip install -r requirements.txt` (incluye moviepy y Pillow)."
            ),
        }

    error = _validar_beats(beats, tema)
    if error:
        return {"status": "error", "detalle": error}

    SALIDA_DIR.mkdir(parents=True, exist_ok=True)
    total = len(beats)
    clips = []
    for i, data in enumerate(beats):
        beat = Beat(fr=data["fr"], en=data["en"], visual=data["visual"])

        def make_frame(t, beat=beat, i=i):
            fase = min(t / duracion_beat, 1.0)
            return np.array(_componer_frame(beat, fase, i, total, tema))

        clips.append(VideoClip(make_frame, duration=duracion_beat))

    reel = concatenate_videoclips(clips, method="compose")
    salida = SALIDA_DIR / f"{nombre_salida}.mp4"
    reel.write_videofile(str(salida), fps=FPS, codec="libx264", logger=None)
    return {
        "status": "generado",
        "ruta": str(salida.relative_to(REPO_ROOT)),
        "duracion_seg": round(reel.duration, 1),
        "beats": total,
        "nota": "Sin audio — preview visual únicamente.",
    }


def generar_reel(beats: list[dict], nombre_salida: str, tema: str = "rive") -> dict:
    """Genera el .mp4 completo en data/reels/{nombre_salida}.mp4.

    `beats`: lista de {"fr": str, "en": str, "visual": una clave de
    VISUALES}. El orden es el orden final del video. `tema`: "rive"
    (Rive Intelligente, por defecto) o "aiassistant" (AiAssistant by
    InnovaMontreal, getaiassistant.app).

    No es una tool irreversible — solo crea un archivo nuevo, no modifica
    ni borra nada existente."""
    try:
        import numpy as np
        from moviepy import AudioFileClip, VideoClip, concatenate_videoclips
    except ImportError as exc:
        return {
            "status": "error",
            "detalle": (
                f"Falta una dependencia ({exc}). Corre "
                "`pip install -r requirements.txt` (incluye moviepy, Pillow, "
                "imageio-ffmpeg, azure-cognitiveservices-speech)."
            ),
        }

    error = _validar_beats(beats, tema)
    if error:
        return {"status": "error", "detalle": error}

    SALIDA_DIR.mkdir(parents=True, exist_ok=True)
    clips = []
    total = len(beats)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        try:
            for i, data in enumerate(beats):
                beat = Beat(fr=data["fr"], en=data["en"], visual=data["visual"])
                wav_path = tmp_path / f"beat_{i}.wav"
                log.info("Sintetizando voz fr-CA para beat %d/%d: %r", i + 1, total, beat.fr)
                _voz_azure(beat.fr, wav_path)

                audio_clip = AudioFileClip(str(wav_path))
                duracion = max(DURACION_MIN_BEAT_SEG, audio_clip.duration + COLCHON_TRAS_AUDIO_SEG)

                def make_frame(t, beat=beat, duracion=duracion, i=i):
                    fase = min(t / duracion, 1.0)
                    frame = _componer_frame(beat, fase, i, total, tema)
                    return np.array(frame)

                clip = VideoClip(make_frame, duration=duracion).with_audio(audio_clip)
                clips.append(clip)
        except RuntimeError as exc:
            return {"status": "error", "detalle": str(exc)}

        reel = concatenate_videoclips(clips, method="compose")
        salida = SALIDA_DIR / f"{nombre_salida}.mp4"
        reel.write_videofile(str(salida), fps=FPS, codec="libx264", audio_codec="aac", logger=None)

    return {
        "status": "generado",
        "ruta": str(salida.relative_to(REPO_ROOT)),
        "duracion_seg": round(reel.duration, 1),
        "beats": total,
    }
