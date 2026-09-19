"""Generador de reels verticales (9:16) para Instagram/Facebook.

Toma un guion de "beats" (cada uno con texto en francés para narrar y
texto en inglés para subtitular) y produce un archivo .mp4 con:

- Narración en francés QUEBEQUENSE (voz neuronal fr-CA de Azure Speech, o
  ElevenLabs — NUNCA francés de Francia, eso es un requisito explícito
  del proyecto).
- Subtítulo en pantalla SOLO en inglés — el francés vive únicamente en el
  audio, nunca se dibuja como texto. No mezclar los dos idiomas en
  pantalla.
- Una animación simple por beat, dibujada a mano con Pillow (círculos,
  líneas, texto) — sin After Effects, sin navegador headless. Cada beat
  tiene un `visual` de VISUALES que decide qué se dibuja.
- La estética de marca del tema elegido (ver constantes.TEMAS).

Modularizado el 2026-09-19 (antes: un solo archivo de 1264 líneas) por
responsabilidad — cada pieza vive en su propio submódulo:

- `constantes.py`   — dimensiones, rutas, paleta por tema, dataclass Beat.
- `voz.py`           — síntesis de voz (Azure/ElevenLabs) + SSML.
- `dibujo_utils.py`  — fondo animado, glow, tarjeta, fuentes, easing.
- `iconos.py`        — los 5 íconos abstractos (tema "rive").
- `mockups_taskdoctor.py`  — mockups reales de TaskDoctor.ai (activo).
- `mockups_aiassistant.py` — mockups de getaiassistant.app (preservados,
  sin usarse en la config activa — ver reels_defaults.py).
- `mockups.py`       — une los dos vocabularios de `visual`.
- `composicion.py`   — arma cada frame completo (fondo+ícono/mockup+sub).
- `ensamblado.py`     — valida el guion, sintetiza audio, arma el .mp4.

Este `__init__.py` es la ÚNICA superficie pública — el resto del repo
sigue haciendo `from orchestrator.tools import reel_generator` y usando
`reel_generator.generar_reel(...)`, `reel_generator.ANCHO`, etc. exactamente
igual que antes de la modularización. Ningún import externo debería
necesitar cambiar.

Requiere (ver requirements.txt): Pillow, moviepy, imageio-ffmpeg,
azure-cognitiveservices-speech. Y las variables de entorno
AZURE_SPEECH_KEY / AZURE_SPEECH_REGION (ver .env.example) — sin ellas,
`generar_reel` devuelve un dict con status="error" y una explicación en
vez de lanzar una excepción sin manejar (mismo principio que
receptionist.py con negocio.yaml: falta configuración no debe romper el
arranque del orchestrator, solo esta función en particular)."""
from __future__ import annotations

# --- constantes / configuración --------------------------------------------
from .constantes import (
    ALTO,
    ANCHO,
    AZUL,
    BLANCO,
    COLCHON_TRAS_AUDIO_SEG,
    CREMA,
    DURACION_MIN_BEAT_SEG,
    FONT_PATH,
    FPS,
    GRIS_BORDE,
    GRIS_TEXTO,
    LIMA,
    MINT,
    NAVY,
    PLANTILLA_PAUSA_MS,
    PLANTILLA_RITMO_PCT,
    REPO_ROOT,
    SALIDA_DIR,
    TD_CREMA,
    TD_GRIS_BORDE,
    TD_GRIS_TEXTO,
    TD_NARANJA,
    TD_NARANJA_CLARO,
    TD_NARANJA_DEEP,
    TD_TINTA,
    TEAL,
    TEAL_DEEP,
    TEMAS,
    TINTA,
    VOZ_FR_CA_POR_DEFECTO,
    Beat,
)

# --- voz / SSML --------------------------------------------------------------
from .voz import (
    ELEVENLABS_MODELO_POR_DEFECTO,
    PROVEEDORES_VOZ,
    _aplicar_pausas_y_enfasis,
    _construir_ssml,
    _escapar_ssml,
    _texto_para_elevenlabs,
    _voz_azure,
    _voz_elevenlabs,
)

# --- utilidades de dibujo (usadas también por video_ia.py) ------------------
from .dibujo_utils import (
    _cargar_fuente,
    _clamp01,
    _dibujar_destellos,
    _dibujar_glow,
    _dibujar_tarjeta,
    _ease_out,
    _ease_out_back,
    _envolver_texto,
    _fondo_base,
    _recortar_fondo,
    _revelar,
)

# --- vocabularios de `visual` (íconos + mockups) ----------------------------
from .iconos import ICON_VISUALES
from .mockups import MOCKUP_VISUALES, VISUALES
from .mockups_aiassistant import _mockup_chat, _mockup_form, _mockup_hero, _mockup_roadmap
from .mockups_taskdoctor import _mockup_td_cta, _mockup_td_dashboard, _mockup_td_hero, _mockup_td_privacy

# --- composición de frame ----------------------------------------------------
from .composicion import _componer_frame

# --- ensamblado final (la API que usa el resto del repo) --------------------
from .ensamblado import _validar_beats, concatenar_clips, generar_preview_visual, generar_reel

__all__ = [
    "ALTO", "ANCHO", "AZUL", "BLANCO", "COLCHON_TRAS_AUDIO_SEG", "CREMA",
    "DURACION_MIN_BEAT_SEG", "FONT_PATH", "FPS", "GRIS_BORDE", "GRIS_TEXTO",
    "LIMA", "MINT", "NAVY", "PLANTILLA_PAUSA_MS", "PLANTILLA_RITMO_PCT",
    "REPO_ROOT", "SALIDA_DIR", "TD_CREMA", "TD_GRIS_BORDE", "TD_GRIS_TEXTO",
    "TD_NARANJA", "TD_NARANJA_CLARO", "TD_NARANJA_DEEP", "TD_TINTA", "TEAL",
    "TEAL_DEEP", "TEMAS", "TINTA", "VOZ_FR_CA_POR_DEFECTO", "Beat",
    "ELEVENLABS_MODELO_POR_DEFECTO", "PROVEEDORES_VOZ",
    "ICON_VISUALES", "MOCKUP_VISUALES", "VISUALES",
    "generar_preview_visual", "generar_reel", "concatenar_clips",
]
