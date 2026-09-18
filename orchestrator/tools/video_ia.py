"""Generación de video real con IA (Google Veo, vía Gemini API) — distinto
del pipeline de reel_generator.py (que dibuja mockups/íconos a mano con
Pillow). Esto genera METRAJE REAL con un modelo generativo, a partir de un
prompt cinematográfico que escribe el agente (ver reel_producer.py) —
idealmente fundamentado en contenido real de una URL, no inventado.

Requiere GEMINI_API_KEY en .env — sacala en aistudio.google.com/apikey.
OJO (corregido tras probar en vivo — la doc oficial no lo deja claro): el
tier gratis de esa key NO alcanza para Veo, aunque sí sirve para texto/
imagen. Hace falta habilitar FACTURACIÓN en el proyecto de AI Studio (no
es un proyecto de Vertex AI completo aparte, es el mismo proyecto de la
API key — solo activarle un método de pago) o Veo devuelve 429
RESOURCE_EXHAUSTED con cualquier pedido, verificado. Reportes de la
comunidad de Google (foro oficial) indican que incluso con facturación
activa a veces sigue dando 429 de forma intermitente — no asumir que
"ya tiene facturación" garantiza que funcione a la primera.

Dependencia nueva: `google-genai` (el SDK oficial, distinto del viejo
`google-generativeai`) y `beautifulsoup4` (extraer texto legible de una
URL para `leer_url`). Ver requirements.txt.

Tools, pensadas para que el AGENTE (no este archivo) escriba el prompt
"súper pro" — este módulo solo ejecuta:
- `leer_url(url)`: descarga y devuelve el texto visible de una página,
  para que el agente fundamente el prompt en contenido real.
- `generar_video_ia(prompt, nombre_salida, ...)`: llama a Veo con ese
  prompt y guarda el .mp4 resultante.
- `mezclar_audio(ambiente, voz, peso_voz)`: combina el audio nativo de un
  clip de Veo (ambiente, sin diálogo) con una narración fr-CA generada
  aparte (ElevenLabs/Azure, ver reel_generator.py) — para reels donde la
  narración suena POR ENCIMA del ambiente real de Veo, en vez de
  reemplazarlo.
- `quemar_subtitulo(ruta_video, texto_en, ...)`: redimensiona un clip de
  Veo a 1080x1920 y le quema encima el subtítulo en inglés, mismo estilo
  visual (WorkSans, sin caja, contorno oscuro) que usan los mockups de
  reel_generator.py — el francés NUNCA se dibuja, esto es SOLO inglés.
- `producir_beat_veo(...)`: orquesta un beat completo de Veo — sintetiza
  la narración fr-CA, la mezcla con el ambiente del clip, y quema el
  subtítulo en inglés, todo en un solo llamado."""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path

log = logging.getLogger("orchestrator.tools.video_ia")

REPO_ROOT = Path(__file__).resolve().parents[2]
SALIDA_DIR = REPO_ROOT / "data" / "reels" / "video_ia"

MODELO_VEO_POR_DEFECTO = "veo-3.1-generate-preview"
ASPECT_RATIOS_VALIDOS = {"16:9", "9:16"}
DURACIONES_VALIDAS = {"4", "6", "8"}
TIMEOUT_POLLING_SEG = 360  # 6 min — el máximo documentado por Google en horas pico


def leer_url(url: str, max_caracteres: int = 6000) -> dict:
    """Descarga `url` y devuelve su texto visible (best-effort), para que
    el agente escriba el prompt de Veo fundamentado en contenido real, no
    inventado. Sitios muy dependientes de JavaScript (SPAs) pueden dar
    poco texto útil vía este fetch simple (sin navegador) — si el
    resultado parece pobre (muy corto), el agente debe decírselo al
    usuario y pedirle el contenido clave a mano en vez de inventar."""
    import httpx
    from bs4 import BeautifulSoup

    try:
        resultado = httpx.get(
            url, timeout=20, follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; AiAssistantBot/1.0)"},
        )
        resultado.raise_for_status()
    except httpx.HTTPError as exc:
        return {"status": "error", "detalle": f"No se pudo descargar {url!r}: {exc}"}

    sopa = BeautifulSoup(resultado.text, "html.parser")
    for etiqueta in sopa(["script", "style", "noscript"]):
        etiqueta.decompose()
    texto = " ".join(sopa.get_text(separator=" ").split())

    return {
        "status": "ok",
        "url": url,
        "texto": texto[:max_caracteres],
        "truncado": len(texto) > max_caracteres,
        "caracteres_totales": len(texto),
    }


def generar_video_ia(
    prompt: str,
    nombre_salida: str,
    aspect_ratio: str = "9:16",
    duracion_seg: str = "8",
) -> dict:
    """Genera un video real con Veo a partir de `prompt` (texto libre,
    en inglés — Veo entiende mejor inglés, ver system prompt del agente).

    OJO idioma/audio: este proyecto narra en francés quebequense aparte
    (ElevenLabs/Azure, ver reel_generator.py) — `prompt` NO debe pedir
    diálogo hablado ni narración; Veo puede generar audio nativo si el
    prompt lo sugiere, y eso chocaría con la narración que se agrega
    después. Pedí solo imagen/movimiento/ambiente, sin diálogo.

    Llamada asíncrona del lado de Google — esta función espera
    (polling cada 10s) hasta que el video esté listo o hasta
    TIMEOUT_POLLING_SEG. Puede tardar de un minuto a varios.
    Guarda en data/reels/video_ia/{nombre_salida}.mp4."""
    key = os.getenv("GEMINI_API_KEY", "")
    if not key:
        raise RuntimeError(
            "Falta GEMINI_API_KEY en .env — necesaria para generar video con "
            "Veo. Sacala en aistudio.google.com/apikey — OJO: hay que "
            "habilitar facturación en ese proyecto para que Veo funcione "
            "(el tier gratis solo alcanza para texto/imagen, no video — "
            "verificado: sin facturación devuelve 429 RESOURCE_EXHAUSTED)."
        )
    if aspect_ratio not in ASPECT_RATIOS_VALIDOS:
        raise RuntimeError(f"aspect_ratio {aspect_ratio!r} inválido. Opciones: {sorted(ASPECT_RATIOS_VALIDOS)}.")
    if duracion_seg not in DURACIONES_VALIDAS:
        raise RuntimeError(f"duracion_seg {duracion_seg!r} inválida. Opciones: {sorted(DURACIONES_VALIDAS)}.")

    from google import genai
    from google.genai import types

    modelo = os.getenv("GEMINI_VEO_MODEL", MODELO_VEO_POR_DEFECTO)
    client = genai.Client(api_key=key)

    log.info("Pidiendo video a Veo (%s, %s, %ss): %r", modelo, aspect_ratio, duracion_seg, prompt)
    operation = client.models.generate_videos(
        model=modelo,
        prompt=prompt,
        config=types.GenerateVideosConfig(aspect_ratio=aspect_ratio, duration_seconds=duracion_seg),
    )

    inicio = time.time()
    while not operation.done:
        if time.time() - inicio > TIMEOUT_POLLING_SEG:
            return {"status": "error", "detalle": f"Veo no respondió en {TIMEOUT_POLLING_SEG}s — probablemente hora pico, reintentar."}
        time.sleep(10)
        operation = client.operations.get(operation)

    if not operation.response or not operation.response.generated_videos:
        return {"status": "error", "detalle": f"Veo no generó video: {getattr(operation, 'error', 'motivo desconocido')}"}

    SALIDA_DIR.mkdir(parents=True, exist_ok=True)
    salida = SALIDA_DIR / f"{nombre_salida}.mp4"
    video = operation.response.generated_videos[0]
    client.files.download(file=video.video)
    video.video.save(str(salida))

    return {
        "status": "generado",
        "ruta": str(salida.relative_to(REPO_ROOT)),
        "modelo": modelo,
        "aspect_ratio": aspect_ratio,
        "duracion_seg": duracion_seg,
    }


def mezclar_audio(ambiente, voz, peso_voz: float):
    """Combina dos pistas de audio de moviepy con un balance de volumen.

    `peso_voz` va de 0 a 1: 0 = solo `ambiente` (la voz queda muda),
    1 = solo `voz` (el ambiente queda mudo), valores intermedios mezclan
    las dos — ej. 0.7 = voz bien presente, ambiente de fondo apenas
    audible. La pista resultante dura lo que dure la más larga de las
    dos (comportamiento de CompositeAudioClip)."""
    if not 0.0 <= peso_voz <= 1.0:
        raise ValueError(f"peso_voz debe estar entre 0 y 1, llegó {peso_voz!r}.")

    from moviepy import CompositeAudioClip

    ambiente_escalado = ambiente.with_volume_scaled(1.0 - peso_voz)
    voz_escalada = voz.with_volume_scaled(peso_voz)
    return CompositeAudioClip([ambiente_escalado, voz_escalada])


def aplicar_narracion_sobre_video(ruta_video: str, ruta_audio_narracion: str, peso_voz: float, nombre_salida: str):
    """Toma un .mp4 de Veo ya generado (con su ambiente nativo) y un audio
    de narración ya sintetizado (ver reel_generator._voz_elevenlabs/
    _voz_azure), y guarda un nuevo .mp4 con las dos pistas mezcladas vía
    `mezclar_audio`. El video se recorta a la duración del clip original
    (si la narración es más larga, se corta; si es más corta, el resto
    queda solo con ambiente — no se estira ni se repite)."""
    from moviepy import AudioFileClip, VideoFileClip

    video = VideoFileClip(ruta_video)
    narracion = AudioFileClip(ruta_audio_narracion)
    mezcla = mezclar_audio(video.audio, narracion, peso_voz).subclipped(0, video.duration)

    SALIDA_DIR.mkdir(parents=True, exist_ok=True)
    salida = SALIDA_DIR / f"{nombre_salida}.mp4"
    video.with_audio(mezcla).write_videofile(str(salida), codec="libx264", audio_codec="aac", logger=None)

    return {"status": "generado", "ruta": str(salida.relative_to(REPO_ROOT))}


def _imagen_subtitulo(ancho: int, alto: int, texto_en: str):
    """Overlay PNG (transparente) del subtítulo en inglés — mismo estilo
    visual que reel_generator._componer_frame (WorkSans, blanco, contorno
    oscuro, sin caja de fondo), para que los clips de Veo se vean
    consistentes con los mockups en el mismo reel."""
    from PIL import Image, ImageDraw

    from orchestrator.tools import reel_generator as rg

    overlay = Image.new("RGBA", (ancho, alto), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    fuente = rg._cargar_fuente(58, 600)
    lineas = rg._envolver_texto(draw, texto_en, fuente, ancho - 140)
    alto_linea = 72
    y0 = alto - 210 - len(lineas) * alto_linea
    for i, linea in enumerate(lineas):
        draw.text(
            (ancho / 2, y0 + i * alto_linea), linea, font=fuente, anchor="ma",
            fill=(245, 247, 246, 255), stroke_width=6, stroke_fill=(9, 19, 17, 235),
        )
    return overlay


def quemar_subtitulo(ruta_video: str, texto_en: str, nombre_salida: str) -> dict:
    """Redimensiona `ruta_video` (ej. 720x1280 de Veo) a 1080x1920 y le
    quema encima `texto_en` como subtítulo — el francés NUNCA se dibuja,
    esto es SOLO para el texto en inglés."""
    import numpy as np
    from moviepy import CompositeVideoClip, ImageClip, VideoFileClip

    from orchestrator.tools import reel_generator as rg

    ruta_video_path = Path(ruta_video)
    ruta_abs = ruta_video_path if ruta_video_path.is_absolute() else REPO_ROOT / ruta_video_path
    video = VideoFileClip(str(ruta_abs))
    if video.size != [rg.ANCHO, rg.ALTO]:
        video = video.resized(new_size=(rg.ANCHO, rg.ALTO))

    overlay_img = _imagen_subtitulo(rg.ANCHO, rg.ALTO, texto_en)
    overlay_clip = ImageClip(np.array(overlay_img), transparent=True).with_duration(video.duration)

    final = CompositeVideoClip([video, overlay_clip]).with_audio(video.audio)

    SALIDA_DIR.mkdir(parents=True, exist_ok=True)
    salida = SALIDA_DIR / f"{nombre_salida}.mp4"
    final.write_videofile(str(salida), codec="libx264", audio_codec="aac", logger=None)

    return {"status": "generado", "ruta": str(salida.relative_to(REPO_ROOT))}


def producir_beat_veo(
    ruta_video_veo: str,
    texto_fr: str,
    texto_en: str,
    nombre_salida: str,
    peso_voz: float = 0.7,
    proveedor_voz: str | None = None,
    voz_id: str | None = None,
) -> dict:
    """Orquesta un beat completo a partir de un clip de Veo YA GENERADO:
    sintetiza `texto_fr` con el proveedor de voz de siempre (ver
    reels_defaults.resolver_voz), mezcla esa narración con el ambiente
    nativo del clip (`peso_voz`, 0=solo ambiente, 1=solo voz), y quema
    `texto_en` como subtítulo — mismas reglas de idioma que el resto del
    proyecto (fr narrado, en dibujado, nunca al revés)."""
    import tempfile

    from orchestrator.tools import reel_generator as rg
    from orchestrator.tools import reels_defaults as rd

    proveedor_voz, voz_id = rd.resolver_voz(proveedor_voz, voz_id)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        audio_path = tmp_path / "narracion.mp3" if proveedor_voz == "elevenlabs" else tmp_path / "narracion.wav"
        if proveedor_voz == "elevenlabs":
            rg._voz_elevenlabs(texto_fr, voz_id, audio_path)
        else:
            rg._voz_azure(texto_fr, audio_path)

        con_audio = aplicar_narracion_sobre_video(
            ruta_video_veo, str(audio_path), peso_voz, f"{nombre_salida}_audio_tmp"
        )
        if con_audio["status"] != "generado":
            return con_audio

        resultado = quemar_subtitulo(con_audio["ruta"], texto_en, nombre_salida)

    ruta_tmp_audio = SALIDA_DIR / f"{nombre_salida}_audio_tmp.mp4"
    if ruta_tmp_audio.exists():
        ruta_tmp_audio.unlink()

    return resultado
