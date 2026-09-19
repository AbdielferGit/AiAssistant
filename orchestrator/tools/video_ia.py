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
  subtítulo en inglés, todo en un solo llamado.
- `generar_imagen_ia(prompt, nombre_salida, ...)`: genera una imagen fija
  (Gemini/"Nano Banana") pensada como `imagen_inicial` de
  generar_video_ia — la misma GEMINI_API_KEY (misma facturación de Veo)
  sirve para esto, no hace falta ninguna cuenta nueva."""
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

# Mapeo calidad -> modelo real. "lite"/"fast" son para VALIDAR barato un
# prompt/composición nueva antes de pagar "standard" (la que da el mejor
# resultado, y la que usamos por defecto para la versión final). Precios
# verificados (720p, sin audio): lite ~$0.05/seg, fast ~$0.10/seg,
# standard ~$0.20/seg — con audio nativo cuesta ~el doble, por eso
# generate_audio=False por defecto (igual reemplazamos el audio con
# ElevenLabs/Azure, pagar el audio nativo de Veo era plata tirada).
MODELOS_POR_CALIDAD = {
    "lite": "veo-3.1-lite-generate-preview",
    "fast": "veo-3.1-fast-generate-preview",
    "standard": MODELO_VEO_POR_DEFECTO,
}

# Mismo criterio que MODELOS_POR_CALIDAD pero para imagen fija. Precios
# verificados en ai.google.dev/gemini-api/docs/pricing (2026-09-17):
# "boceto" ~$0.04/imagen — para probar composición/prompt barato antes de
# pagar "pro" (Nano Banana Pro, ~$0.13-0.24/imagen, la mejor calidad —
# usar solo cuando el boceto ya convenció). Sin free tier vía API para
# ninguno de los tres (verificado contra la doc oficial de precios).
MODELOS_IMAGEN_POR_CALIDAD = {
    "boceto": "gemini-2.5-flash-image",
    "flash": "gemini-3.1-flash-image",
    "pro": "gemini-3-pro-image",
}


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


def _cargar_imagen_local(ruta: str):
    """Carga un archivo de imagen local (png/jpg) como types.Image, para
    `imagen_inicial`/`imagenes_referencia` de generar_video_ia."""
    from google.genai import types

    ruta_path = Path(ruta)
    ruta_abs = ruta_path if ruta_path.is_absolute() else REPO_ROOT / ruta_path
    if not ruta_abs.exists():
        raise RuntimeError(f"No existe la imagen: {ruta_abs}")
    mime = "image/png" if ruta_abs.suffix.lower() == ".png" else "image/jpeg"
    return types.Image(image_bytes=ruta_abs.read_bytes(), mime_type=mime)


def generar_video_ia(
    prompt: str,
    nombre_salida: str,
    aspect_ratio: str = "9:16",
    duracion_seg: str = "8",
    calidad: str = "standard",
    generate_audio: bool = False,
    imagen_inicial: str | None = None,
    imagenes_referencia: list[str] | None = None,
    negative_prompt: str | None = None,
    seed: int | None = None,
) -> dict:
    """Genera un video real con Veo a partir de `prompt` (texto libre,
    en inglés — Veo entiende mejor inglés, ver system prompt del agente).

    OJO idioma/audio: este proyecto narra en francés quebequense aparte
    (ElevenLabs/Azure, ver reel_generator.py) — `prompt` NO debe pedir
    diálogo hablado ni narración. `generate_audio=False` por defecto NO
    significa "pedile a Veo que no genere audio" — verificado en vivo
    (2026-09-18): con una GEMINI_API_KEY común (Gemini Developer API),
    el parámetro generate_audio ni siquiera se puede enviar, da error
    ValueError sea cual sea su valor ("solo soportado en Gemini
    Enterprise Agent Platform mode"). Con `generate_audio=False` (el
    default) simplemente NO se manda el parámetro, y el audio nativo que
    venga con el clip es el que Veo decida — igual lo reemplazamos/
    mezclamos con ElevenLabs/Azure después, así que no importa. Pasar
    `generate_audio=True` a propósito SÍ lo manda explícito (puede fallar
    si tu key tampoco soporta eso — no confirmado).

    `calidad`: "lite" (~$0.05/seg, para VALIDAR barato un prompt/
    composición nueva) | "fast" (~$0.10/seg) | "standard" (~$0.20/seg,
    default — usar solo cuando el prompt ya está validado). Ir de lite a
    standard cuando el resultado convence, no al revés.

    `imagen_inicial`: ruta a una imagen local que fija el primer frame —
    ancla la composición/sujeto exacto, deja solo el movimiento como
    variable. `imagenes_referencia`: hasta 3 rutas de imágenes locales
    para guiar el estilo visual (ver VideoGenerationReferenceImage).

    `seed`/`negative_prompt`: existen en el SDK instalado aunque la doc
    pública de Veo 3.1 no los documenta — probalos con cautela, su efecto
    real no está confirmado (a diferencia del resto de esta función, que
    sí está verificado en vivo).

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
    if calidad not in MODELOS_POR_CALIDAD:
        raise RuntimeError(f"calidad {calidad!r} inválida. Opciones: {sorted(MODELOS_POR_CALIDAD)}.")
    if imagenes_referencia and len(imagenes_referencia) > 3:
        raise RuntimeError(f"imagenes_referencia admite máximo 3, llegaron {len(imagenes_referencia)}.")

    from google import genai
    from google.genai import types

    modelo = os.getenv("GEMINI_VEO_MODEL") or MODELOS_POR_CALIDAD[calidad]
    client = genai.Client(api_key=key)

    config_kwargs = dict(
        aspect_ratio=aspect_ratio,
        duration_seconds=duracion_seg,
    )
    # OJO (verificado en vivo el 2026-09-18, contradice lo que decía el
    # comentario original de esta función): con una GEMINI_API_KEY común
    # ("Gemini Developer API"), el parámetro generate_audio NI SIQUIERA SE
    # PUEDE ENVIAR — la API devuelve ValueError "generate_audio parameter
    # is only supported in Gemini Enterprise Agent Platform mode", pase lo
    # que pase su valor (True o False). Solo lo mandamos si se pidió
    # generate_audio=True a propósito (ahí el usuario asume el riesgo de
    # que falle); dejarlo en False (el default) significa "no lo mandes",
    # no "pedile a Veo que no genere audio" — con esta key no hay forma de
    # controlar eso, el audio nativo que venga es el que Veo decida.
    if generate_audio:
        config_kwargs["generate_audio"] = generate_audio
    if negative_prompt:
        config_kwargs["negative_prompt"] = negative_prompt
    if seed is not None:
        config_kwargs["seed"] = seed
    if imagenes_referencia:
        config_kwargs["reference_images"] = [
            types.VideoGenerationReferenceImage(
                image=_cargar_imagen_local(ruta),
                reference_type=types.VideoGenerationReferenceType.STYLE,
            )
            for ruta in imagenes_referencia
        ]

    generate_kwargs = dict(model=modelo, prompt=prompt, config=types.GenerateVideosConfig(**config_kwargs))
    if imagen_inicial:
        generate_kwargs["image"] = _cargar_imagen_local(imagen_inicial)

    log.info(
        "Pidiendo video a Veo (%s, calidad=%s, %s, %ss, audio=%s): %r",
        modelo, calidad, aspect_ratio, duracion_seg, generate_audio, prompt,
    )
    operation = client.models.generate_videos(**generate_kwargs)

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
        "calidad": calidad,
        "aspect_ratio": aspect_ratio,
        "duracion_seg": duracion_seg,
        "generate_audio": generate_audio,
    }


def generar_imagen_ia(
    prompt: str,
    nombre_salida: str,
    aspect_ratio: str = "9:16",
    calidad: str = "boceto",
    imagenes_referencia: list[str] | None = None,
) -> dict:
    """Genera una imagen fija con Gemini ("Nano Banana") a partir de
    `prompt` (texto libre, en inglés). Pensada como punto de partida de
    calidad para `generar_video_ia` (parámetro `imagen_inicial`): ancla
    composición/sujeto/estilo antes de animarlo con Veo.

    `calidad`: "boceto" (gemini-2.5-flash-image, ~$0.04/imagen — para
    probar composición/prompt barato) | "flash" (gemini-3.1-flash-image,
    ~$0.05-0.15) | "pro" (gemini-3-pro-image / Nano Banana Pro,
    ~$0.13-0.24, la mejor calidad — usar solo cuando el boceto ya
    convenció). Default "boceto": ir subiendo de calidad recién cuando el
    resultado lo justifica, no al revés.

    `imagenes_referencia`: hasta 3 rutas de imágenes locales (ej. una
    captura real de riveintelligente.ca/taskdoctor.ai) para guiar estilo/
    fidelidad de marca — se pasan como parte del mismo mensaje, junto con
    `prompt`, porque esta API es una llamada de chat multimodal normal
    (no un endpoint de imagen aparte).

    Guarda en data/reels/video_ia/{nombre_salida}.png. Sin polling — a
    diferencia de Veo, esta llamada es síncrona."""
    key = os.getenv("GEMINI_API_KEY", "")
    if not key:
        raise RuntimeError(
            "Falta GEMINI_API_KEY en .env — la misma key/facturación que "
            "ya usamos para Veo sirve para esto, no hace falta ninguna "
            "cuenta nueva. Sacala en aistudio.google.com/apikey."
        )
    if aspect_ratio not in ASPECT_RATIOS_VALIDOS:
        raise RuntimeError(f"aspect_ratio {aspect_ratio!r} inválido. Opciones: {sorted(ASPECT_RATIOS_VALIDOS)}.")
    if calidad not in MODELOS_IMAGEN_POR_CALIDAD:
        raise RuntimeError(f"calidad {calidad!r} inválida. Opciones: {sorted(MODELOS_IMAGEN_POR_CALIDAD)}.")
    if imagenes_referencia and len(imagenes_referencia) > 3:
        raise RuntimeError(f"imagenes_referencia admite máximo 3, llegaron {len(imagenes_referencia)}.")

    from google import genai
    from google.genai import types

    modelo = MODELOS_IMAGEN_POR_CALIDAD[calidad]
    client = genai.Client(api_key=key)

    partes = [types.Part.from_text(text=prompt)]
    for ruta in imagenes_referencia or []:
        imagen = _cargar_imagen_local(ruta)
        partes.append(types.Part.from_bytes(data=imagen.image_bytes, mime_type=imagen.mime_type))

    log.info("Pidiendo imagen a Gemini (%s, calidad=%s, %s): %r", modelo, calidad, aspect_ratio, prompt)
    respuesta = client.models.generate_content(
        model=modelo,
        contents=partes,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio=aspect_ratio),
        ),
    )

    if not respuesta.candidates:
        return {"status": "error", "detalle": f"Gemini no devolvió candidatos: {getattr(respuesta, 'prompt_feedback', 'motivo desconocido')}"}

    imagen_generada = None
    for parte in respuesta.candidates[0].content.parts:
        imagen_generada = parte.as_image()
        if imagen_generada is not None:
            break
    if imagen_generada is None:
        return {"status": "error", "detalle": "Gemini respondió sin imagen (puede haber bloqueado el prompt por seguridad)."}

    SALIDA_DIR.mkdir(parents=True, exist_ok=True)
    salida = SALIDA_DIR / f"{nombre_salida}.png"
    salida.write_bytes(imagen_generada.image_bytes)

    return {
        "status": "generado",
        "ruta": str(salida.relative_to(REPO_ROOT)),
        "modelo": modelo,
        "calidad": calidad,
        "aspect_ratio": aspect_ratio,
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
