"""Síntesis de voz fr-CA (Azure / ElevenLabs) y el SSML que le da ritmo y
énfasis a la narración. Separado de la composición visual y del
ensamblado en la modularización de 2026-09-19."""
from __future__ import annotations

import os
import re
from pathlib import Path

from .constantes import PLANTILLA_PAUSA_MS, PLANTILLA_RITMO_PCT, VOZ_FR_CA_POR_DEFECTO

PROVEEDORES_VOZ = {"azure", "elevenlabs"}
ELEVENLABS_MODELO_POR_DEFECTO = "eleven_multilingual_v2"


def _voz_azure(texto: str, destino_wav: Path) -> None:
    """Sintetiza `texto` con una voz neuronal fr-CA (Quebec) de Azure
    Cognitive Services Speech y la escribe en `destino_wav`.

    Por qué Azure y no otro proveedor: es el que tiene voces neuronales
    fr-CA genuinas y bien documentadas — no una voz de Francia con
    subtítulo "canadiense". Probadas y verificadas en vivo:
    fr-CA-Sylvie:DragonHDLatestNeural / fr-CA-Thierry:DragonHDLatestNeural
    (voces "HD", más naturales — la que se usa por defecto, ver nota sobre
    <prosody>/<emphasis> junto a PLANTILLA_RITMO_PCT en constantes.py) y
    las estándar fr-CA-SylvieNeural / fr-CA-AntoineNeural / fr-CA-JeanNeural /
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


def _texto_para_elevenlabs(texto: str) -> str:
    """Convierte los marcadores `||` y `**texto**` (pensados para el SSML
    de Azure) a algo seguro para ElevenLabs: su API estándar no soporta
    `<break>`/`<emphasis>` de forma confiable (eso lo leería literal), así
    que `||` se convierte en una elipsis — pausa natural que cualquier TTS
    reconoce — y `**texto**` se desenvuelve a texto plano."""
    texto = re.sub(r"\*\*(.+?)\*\*", r"\1", texto)
    return texto.replace("||", "…")


def _voz_elevenlabs(texto: str, voice_id: str, destino_audio: Path) -> None:
    """Sintetiza `texto` con una voz puntual de ElevenLabs (`voice_id`,
    por ejemplo una elegida a mano en su Voice Library) y la escribe en
    `destino_audio` (mp3).

    Alternativa a Azure para probar una voz específica de ElevenLabs.
    Requiere ELEVENLABS_API_KEY en .env. Si `voice_id` es una voz de la
    Voice Library (no una tuya propia), ElevenLabs exige plan pago para
    usarla por API — verificado en vivo: el plan Free devuelve 402
    Payment Required aunque la misma voz funcione gratis en su web."""
    import httpx

    key = os.getenv("ELEVENLABS_API_KEY", "")
    if not key:
        raise RuntimeError(
            "Falta ELEVENLABS_API_KEY en .env — necesaria para sintetizar "
            "voz con ElevenLabs. Sacala en "
            "elevenlabs.io/app/settings/api-keys (con permiso de "
            "text-to-speech habilitado)."
        )
    modelo = os.getenv("ELEVENLABS_MODEL_ID", ELEVENLABS_MODELO_POR_DEFECTO)

    resultado = httpx.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        headers={"xi-api-key": key, "Content-Type": "application/json"},
        json={"text": _texto_para_elevenlabs(texto), "model_id": modelo},
        timeout=60,
    )
    if resultado.status_code != 200:
        raise RuntimeError(
            f"ElevenLabs no pudo sintetizar (HTTP {resultado.status_code}): {resultado.text[:300]}"
        )
    destino_audio.write_bytes(resultado.content)


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
    PLANTILLA_PAUSA_MS (constantes.py) — verificado que Azure acepta
    decimales en `rate`, no hace falta redondear a entero."""
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
