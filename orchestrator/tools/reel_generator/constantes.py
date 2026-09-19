"""Constantes compartidas: dimensiones, rutas, paleta de marca por tema, y
el dataclass `Beat`. Sin lógica — solo datos que el resto del paquete
consulta. Separado del resto en la modularización de 2026-09-19 (antes
todo esto vivía mezclado con ~15 funciones de dibujo en un solo archivo de
1264 líneas)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
FONT_PATH = REPO_ROOT / "orchestrator" / "assets" / "fonts" / "WorkSans-Variable.ttf"
SALIDA_DIR = REPO_ROOT / "data" / "reels"

# Formato vertical estándar de Reels/Stories.
ANCHO, ALTO = 1080, 1920
FPS = 24

# Paleta de marca de Rive Intelligente — mismos valores que el logo (ver
# docs/identidad_marca.md del proyecto de prospección). No inventar
# colores nuevos acá.
NAVY = (21, 58, 70)
TEAL = (47, 167, 154)
TEAL_DEEP = (31, 127, 118)
MINT = (127, 231, 218)
BLANCO = (245, 247, 246)

# Paleta real de "AiAssistant by InnovaMontreal" (getaiassistant.app) —
# sacada en vivo del sitio (colores computados con getComputedStyle, no a
# ojo). Ya no se comercializa como producto aparte (ver reels_defaults.py)
# pero el código de sus mockups se conserva sin usarse — estos colores
# quedan acá por si hace falta reactivarlo.
CREMA = (248, 247, 242)
TINTA = (20, 35, 44)
AZUL = (31, 72, 214)
LIMA = (201, 243, 107)
GRIS_BORDE = (225, 222, 212)
GRIS_TEXTO = (117, 123, 117)

# Paleta real de TaskDoctor.ai — sacada en vivo del sitio (getComputedStyle
# + backgroundImage del botón), igual que se hizo con AiAssistant. No
# inventar tonos nuevos acá tampoco.
TD_CREMA = (255, 253, 250)
TD_TINTA = (6, 18, 38)
TD_NARANJA = (255, 103, 22)
TD_NARANJA_DEEP = (242, 91, 12)
TD_NARANJA_CLARO = (255, 178, 130)  # tinte más claro del mismo naranja, no un color nuevo
TD_GRIS_BORDE = (232, 224, 214)
TD_GRIS_TEXTO = (110, 108, 100)

# Cada "tema" define el fondo animado y la identidad (avatar/handle) del
# reel. "rive" = Rive Intelligente, el ecosistema real de cara al cliente
# (riveintelligente.ca). "taskdoctor" = TaskDoctor.ai, un servicio dentro
# de ese ecosistema. Ninguno de los dos tiene cuenta de Instagram/FB
# confirmada todavía — el handle es un placeholder (el nombre real del
# producto) hasta que exista una cuenta real.
#
# OJO: "aiassistant" ya NO está acá (sacado de la config activa el
# 2026-09-19 — era un tercer producto que ya no se comercializa aparte,
# ver reels_defaults.py) aunque sus mockups siguen definidos en
# mockups_aiassistant.py, sin usarse.
TEMAS = {
    "rive": {
        "fondo_a": NAVY, "fondo_b": TEAL_DEEP,
        "manchas": ((MINT, 130), (TEAL, 120), (TEAL_DEEP, 170), (MINT, 95)),
        "glow": TEAL, "avatar_bg": TEAL, "iniciales": "RI", "handle": "riveintelligente",
    },
    "taskdoctor": {
        "fondo_a": TD_TINTA, "fondo_b": (46, 20, 8),
        "manchas": ((TD_NARANJA, 150), (TD_NARANJA_CLARO, 90), (TD_NARANJA_DEEP, 120), (TD_NARANJA_CLARO, 70)),
        "glow": TD_NARANJA, "avatar_bg": TD_NARANJA, "iniciales": "TD", "handle": "taskdoctor.ai",
    },
}

VOZ_FR_CA_POR_DEFECTO = "fr-CA-Sylvie:DragonHDLatestNeural"  # ver docstring de voz._voz_azure para alternativas
DURACION_MIN_BEAT_SEG = 3.2  # aunque la frase sea muy corta, no menos que esto
COLCHON_TRAS_AUDIO_SEG = 0.6  # margen después de que termina la narración

# --- plantilla de audio (ver voz._construir_ssml) --------------------------
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
    visual: str  # una clave de VISUALES (ver mockups.py)
