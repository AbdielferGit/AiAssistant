"""Ensamblado final: valida un guion de beats, sintetiza la narración
(voz.py), compone cada frame (composicion.py) y arma el .mp4 con moviepy.
Es la capa que orquesta todo lo demás — no dibuja ni sintetiza nada por su
cuenta. Separado del resto en la modularización de 2026-09-19."""
from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from .composicion import _componer_frame
from .constantes import (
    COLCHON_TRAS_AUDIO_SEG,
    DURACION_MIN_BEAT_SEG,
    FONT_PATH,
    FPS,
    REPO_ROOT,
    SALIDA_DIR,
    ANCHO,
    ALTO,
    TEMAS,
    Beat,
)
from .mockups import VISUALES
from .voz import PROVEEDORES_VOZ, _voz_azure, _voz_elevenlabs

log = logging.getLogger("orchestrator.tools.reel_generator")


def _validar_beats(beats: list[dict], tema: str, proveedor_voz: str = "azure", voz_id: str | None = None) -> str | None:
    if not beats:
        return "beats está vacío."
    for b in beats:
        if b.get("visual") not in VISUALES:
            return f"visual {b.get('visual')!r} no existe. Opciones: {sorted(VISUALES)}."
    if tema not in TEMAS:
        return f"tema {tema!r} no existe. Opciones: {sorted(TEMAS)}."
    if proveedor_voz not in PROVEEDORES_VOZ:
        return f"proveedor_voz {proveedor_voz!r} no existe. Opciones: {sorted(PROVEEDORES_VOZ)}."
    if proveedor_voz == "elevenlabs" and not voz_id:
        return "proveedor_voz='elevenlabs' necesita voz_id (el voice_id de ElevenLabs)."
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


def generar_reel(
    beats: list[dict],
    nombre_salida: str,
    tema: str = "rive",
    proveedor_voz: str = "azure",
    voz_id: str | None = None,
) -> dict:
    """Genera el .mp4 completo en data/reels/{nombre_salida}.mp4.

    `beats`: lista de {"fr": str, "en": str, "visual": una clave de
    VISUALES}. El orden es el orden final del video. `tema`: "rive"
    (Rive Intelligente, por defecto) o "taskdoctor" (TaskDoctor.ai, un
    servicio dentro del ecosistema Rive Intelligente). `proveedor_voz`:
    "azure" (por defecto, ver VOZ_FR_CA_POR_DEFECTO en constantes.py) o
    "elevenlabs" (ver voz._voz_elevenlabs — necesita `voz_id`, el
    voice_id de ElevenLabs).

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

    error = _validar_beats(beats, tema, proveedor_voz, voz_id)
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
                extension = "mp3" if proveedor_voz == "elevenlabs" else "wav"
                wav_path = tmp_path / f"beat_{i}.{extension}"
                log.info("Sintetizando voz fr-CA (%s) para beat %d/%d: %r", proveedor_voz, i + 1, total, beat.fr)
                if proveedor_voz == "elevenlabs":
                    _voz_elevenlabs(beat.fr, voz_id, wav_path)
                else:
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


def concatenar_clips(rutas: list[str], nombre_salida: str) -> dict:
    """Concatena varios .mp4 YA GENERADOS (de cualquier origen — un video
    real de Veo vía video_ia.generar_video_ia, un reel de mockups vía
    generar_reel, lo que sea) en un solo video final, en el orden dado.

    Cada clip conserva su propio audio tal cual (ambiente nativo de Veo,
    narración fr-CA de un mockup, o silencio) — esta función NO mezcla
    pistas de audio ni agrega narración nueva, solo pega los clips en
    secuencia. Todos se reescalan a ANCHO x ALTO (1080x1920) para que el
    resultado sea consistente aunque los clips de origen tengan
    resoluciones distintas (ej. Veo entrega 720x1280, los mockups
    1080x1920 — misma proporción 9:16, se reescala sin franjas negras).

    No es una tool irreversible — solo crea un archivo nuevo."""
    try:
        from moviepy import VideoFileClip, concatenate_videoclips
    except ImportError as exc:
        return {"status": "error", "detalle": f"Falta una dependencia ({exc}). Corre `pip install -r requirements.txt`."}

    if not rutas:
        return {"status": "error", "detalle": "rutas está vacío."}

    clips = []
    for ruta in rutas:
        ruta_path = Path(ruta)
        ruta_abs = ruta_path if ruta_path.is_absolute() else REPO_ROOT / ruta_path
        if not ruta_abs.exists():
            return {"status": "error", "detalle": f"No existe el archivo: {ruta_abs}"}
        clip = VideoFileClip(str(ruta_abs))
        if clip.size != [ANCHO, ALTO]:
            clip = clip.resized(new_size=(ANCHO, ALTO))
        clips.append(clip)

    SALIDA_DIR.mkdir(parents=True, exist_ok=True)
    salida = SALIDA_DIR / f"{nombre_salida}.mp4"
    final = concatenate_videoclips(clips, method="compose")
    final.write_videofile(str(salida), fps=FPS, codec="libx264", audio_codec="aac", logger=None)

    return {
        "status": "generado",
        "ruta": str(salida.relative_to(REPO_ROOT)),
        "duracion_seg": round(final.duration, 1),
        "clips": len(rutas),
    }
