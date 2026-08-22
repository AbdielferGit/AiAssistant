"""
Enrutador de agentes — decide, ANTES de generar cualquier respuesta, cuál
de los agentes registrados en `orchestrator/agents/` debe atender el
mensaje del usuario. Si ninguno especializado encaja con claridad, cae en
el agente marcado como predeterminado (ver `Agent_0.es_predeterminado`).

Usa un modelo rápido y barato (Haiku) para esta decisión — clasificar "qué
agente le toca a este mensaje" no necesita el modelo grande, y hacerlo con
uno barato mantiene el costo bajo incluso corriendo esta clasificación en
cada turno.
"""
from __future__ import annotations

import logging

import anthropic

from orchestrator.agents import Agent_0, agente_predeterminado
from orchestrator.config import settings

log = logging.getLogger("orchestrator.router")

MODELO_ENRUTADOR = "claude-haiku-4-5-20251001"
MAX_TOKENS_ENRUTADOR = 20


def _prompt_enrutador(agentes: dict[str, Agent_0]) -> str:
    lineas = [
        "Eres un enrutador. Tu única tarea es decidir qué agente debe "
        "atender el mensaje del usuario, según la descripción de cada uno. "
        "Responde ÚNICAMENTE con el id exacto del agente elegido, en una "
        "sola palabra, sin explicación ni puntuación adicional.",
        "",
        "Agentes disponibles:",
    ]
    for id_, agente in agentes.items():
        descripcion = agente.descripcion_enrutador or "Agente de propósito general."
        lineas.append(f"- {id_}: {descripcion}")
    return "\n".join(lineas)


async def elegir_agente(texto_usuario: str, agentes: dict[str, Agent_0]) -> Agent_0:
    """Devuelve el Agent_0 que debe atender este mensaje. Nunca lanza: si el
    enrutador falla o devuelve algo irreconocible, cae en el agente
    predeterminado en vez de bloquear la conversación."""
    predeterminado = agente_predeterminado()

    if len(agentes) <= 1:
        return predeterminado

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    try:
        respuesta = await client.messages.create(
            model=MODELO_ENRUTADOR,
            max_tokens=MAX_TOKENS_ENRUTADOR,
            system=_prompt_enrutador(agentes),
            messages=[{"role": "user", "content": texto_usuario}],
        )
        id_elegido = "".join(b.text for b in respuesta.content if b.type == "text").strip().lower()
    except Exception:
        log.exception("El enrutador falló — uso el agente predeterminado (%s)", predeterminado.id)
        return predeterminado

    agente = agentes.get(id_elegido)
    if agente is None:
        log.info(
            "Enrutador devolvió %r (no coincide con ningún agente) — uso el predeterminado (%s)",
            id_elegido, predeterminado.id,
        )
        return predeterminado

    log.info("Enrutador eligió: %s", agente.id)
    return agente
