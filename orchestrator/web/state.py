"""Estado compartido entre routers — todo en memoria del proceso. Un solo
lugar para que auth/chat/reels/leads (orchestrator/web/routers/) lean y
escriban lo mismo sin importarse entre sí, evitando imports circulares.

Suficiente para el uso personal / por-invitación de hoy (unos pocos
usuarios a la vez, un proceso). Si esto crece de verdad, la migración es
de infraestructura (mover a Redis/SQLite), no de diseño — este archivo es
el único lugar que tocaría.

Separado de app.py en la modularización de 2026-09-19 (antes: un solo
archivo de 556 líneas mezclando auth, chat, reels y leads)."""
from __future__ import annotations

from pathlib import Path

import anthropic

from orchestrator.config import settings

STATIC_DIR = Path(__file__).resolve().parent / "static"
MAX_TOKENS = 1536

# Tools irreversibles que, además del modal normal, exigen un PIN de un
# solo uso porque tocan la lista blanca misma (ver
# contacts.generar_pin_confirmacion). El PIN se genera en
# routers/chat.py y solo viaja al FRONTEND (para que el humano lo vea en
# el modal) — nunca se pone en un tool_result, así que el modelo no lo ve.
TOOLS_CON_PIN = {"agregar_contacto"}

client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

# --- Estado en memoria, por invitado -------------------------------------
conversaciones: dict[str, list[dict]] = {}
pendientes: dict[str, dict] = {}

# Trabajos de generación de reels — en memoria, igual que lo de arriba.
# Un trabajo pasa por "en_progreso" -> "listo" | "error".
trabajos_reels: dict[str, dict] = {}


def clave_conversacion(sesion_id: str, agente_id: str) -> str:
    """Cada (invitado, agente) tiene su propio historial — así el panel
    lateral puede tener una conversación por agente sin que se mezclen."""
    return f"{sesion_id}::{agente_id}"
