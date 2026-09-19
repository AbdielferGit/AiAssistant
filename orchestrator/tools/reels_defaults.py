"""Parámetros de generación de reels — voz (proveedor, id, ritmo/pausa) y
metadata de cada producto (URL fuente real, tema, guion por defecto).

Este archivo tiene PRIORIDAD para el agente "productor_reels"
(orchestrator/agents/reel_producer.py): antes de improvisar
tema/proveedor_voz/voz_id, el agente usa lo que está acá, salvo que el
usuario pida explícitamente algo distinto en la conversación. Es el
equivalente, para reels, de lo que `config/negocio.yaml` es para el
agente "recepcionista" — un lugar central y editable a mano.

No tiene secretos (las API keys viven solo en .env, nunca acá) — es
seguro tenerlo en git. Editalo directo para cambiar la voz/ritmo por
defecto sin tocar el resto del código.

Actualizado 2026-09-14 — valores confirmados por el usuario tras comparar
en vivo las voces estándar de Azure (fr-CA-Sylvie/Antoine/Jean/Thierry),
las voces "HD" de Azure (Sylvie/Thierry:DragonHDLatestNeural) y una voz
de ElevenLabs elegida a mano por el usuario en su Voice Library."""
from __future__ import annotations

from orchestrator.tools import guiones_reels

# --- voz -----------------------------------------------------------------
# Proveedor activo hoy. Ver reel_generator.generar_reel(proveedor_voz=...).
PROVEEDOR_VOZ_POR_DEFECTO = "elevenlabs"

# Elegida a mano por el usuario en elevenlabs.io/app/voice-library — OJO:
# es una voz de la "Voice Library" (no propia), ElevenLabs exige plan
# pago para usarla por API (verificado: el plan Free devuelve 402
# Payment Required aunque la misma voz sea gratis en su web).
ELEVENLABS_VOZ_ID_POR_DEFECTO = "oziFLKtaxVDHQAh7o45V"
ELEVENLABS_MODELO_POR_DEFECTO = "eleven_multilingual_v2"

# Fallback si ElevenLabs no está disponible (sin ELEVENLABS_API_KEY, plan
# sin permiso, error de red) — ver reel_generator.VOZ_FR_CA_POR_DEFECTO /
# PLANTILLA_RITMO_PCT / PLANTILLA_PAUSA_MS. OJO: ritmo y pausa son
# específicos de Azure (van al SSML) — con ElevenLabs no tienen efecto,
# ahí "||" se convierte en una elipsis y "**texto**" se desenvuelve a
# texto plano (ver _texto_para_elevenlabs en reel_generator.py).
AZURE_VOZ_FR_CA_POR_DEFECTO = "fr-CA-Sylvie:DragonHDLatestNeural"
AZURE_RITMO_PCT = -1
AZURE_PAUSA_MS = 120

# --- productos -------------------------------------------------------------
# Un reel siempre es de uno de estos. `guion` es la lista de beats ya
# aprobada por el usuario (ver guiones_reels.py) — None si todavía no hay
# una para ese producto.
#
# OJO arquitectura del negocio (aclarado por el usuario 2026-09-19):
# AiAssistant (este repo) es la HERRAMIENTA — el sistema de agentes que
# crea todo esto, no un producto que se le venda a nadie. Rive Intelligente
# es el ecosistema/marca real de cara al cliente, y TaskDoctor es uno de
# los servicios dentro de ese ecosistema. Por eso "aiassistant" (el
# producto getaiassistant.app) salió de esta lista — ya no se comercializa
# aparte. El código de sus mockups (mockup_hero/mockup_roadmap/mockup_chat/
# mockup_form) sigue en reel_generator.py sin usarse, por si hace falta
# reactivarlo — no se borró, solo se sacó de la config activa.
PRODUCTOS: dict[str, dict] = {
    "taskdoctor": {
        "tema": "taskdoctor",
        "url_fuente": "https://taskdoctor.ai/",
        "guion": guiones_reels.GUION_TASKDOCTOR_LANZAMIENTO,
        "nota": (
            "Contenido y cifras (32%, 12.4h, $620/semana, las 4 fuentes de "
            "fricción, la cuadrícula de privacidad) son el propio ejemplo y "
            "copy que muestra el sitio real — nada es concepto ni inventado. "
            "Servicio dentro del ecosistema Rive Intelligente."
        ),
    },
    "rive": {
        "tema": "rive",
        "url_fuente": "https://riveintelligente.ca/",
        "guion": None,
        "nota": (
            "Marca/ecosistema real de cara al cliente — riveintelligente.ca "
            "SÍ existe y está en producción (Next.js, repo aparte "
            "github.com/AbdielferGit/RiveIntelligente, deploy en Bluehost — "
            "verificado en vivo 2026-09-19, corrige una nota vieja de este "
            "archivo que decía que no tenía sitio propio). Los reels de tema "
            "'rive' hoy usan los íconos abstractos (ICON_VISUALES en "
            "reel_generator.py), no mockups del sitio real — sin guion "
            "aprobado todavía ni mockups del sitio real construidos."
        ),
    },
}


def parametros_para(producto: str) -> dict:
    """tema/url_fuente/guion/nota de un producto — nunca lanza (mismo
    principio que negocio.yaml: un producto no configurado no debe romper
    el arranque ni la tool, solo cae a valores vacíos/tema 'rive')."""
    return PRODUCTOS.get(producto, {"tema": "rive", "url_fuente": None, "guion": None, "nota": None})


def resolver_voz(proveedor_voz: str | None, voz_id: str | None) -> tuple[str, str | None]:
    """Aplica los valores por defecto de acá cuando el agente (o quien
    llame) no especifica proveedor_voz/voz_id explícitamente. Nunca pisa
    un valor que sí vino explícito."""
    proveedor = proveedor_voz or PROVEEDOR_VOZ_POR_DEFECTO
    if voz_id is None and proveedor == "elevenlabs":
        voz_id = ELEVENLABS_VOZ_ID_POR_DEFECTO
    return proveedor, voz_id
