"""
Agent_0 — clase plantilla para crear agentes nuevos.

Para agregar un agente al sistema NO se toca ni el orchestrator ni el
registro (`orchestrator/agents/__init__.py`): solo se crea un archivo
`.py` nuevo dentro de esta carpeta que instancie `Agent_0` con sus propias
instrucciones, y quede asignado a una variable de nivel de módulo (el
nombre de la variable no importa — se detecta por tipo). El escaneo
automático del paquete lo recoge solo la próxima vez que arranque el
orchestrator.

Ejemplo mínimo — un agente nuevo, puramente conversacional (sin tools),
inspirado en el Analista de CEO:

    # orchestrator/agents/mi_agente.py
    from orchestrator.agents.base import Agent_0

    AGENTE = Agent_0(
        id="mi_agente",
        nombre="Mi Agente Nuevo",
        descripcion_enrutador=(
            "Úsalo cuando el usuario pida X, Y o Z. Sé específico: esta "
            "descripción es lo que el enrutador usa para decidir si este "
            "agente debe atender el mensaje."
        ),
        system_prompt='''Eres ... (tus instrucciones completas aquí) ...''',
    )

Si el agente necesita ejecutar acciones (no solo conversar), agrega
`tool_schemas` (formato tool-use de la API de Anthropic) y `tool_funcs`
(mapa nombre -> función síncrona o async que la implementa) — igual que en
`orchestrator/agents/personal_assistant.py`. Cualquier tool cuyo efecto no
se pueda deshacer debe listarse en `tools_irreversibles`: el loop del
orchestrator pedirá confirmación humana por terminal antes de ejecutarla,
sin excepción.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable
from zoneinfo import ZoneInfo

# Zona horaria del usuario. Fija por ahora (un solo usuario/uso personal);
# si esto se vuelve multiusuario, esto debería venir de la sesión/perfil de
# cada quien en vez de ser una constante global.
ZONA_HORARIA_USUARIO = "America/Toronto"

_DIAS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


@dataclass(frozen=True)
class Agent_0:
    id: str
    nombre: str
    system_prompt: str

    # Frase(s) que le dicen al enrutador CUÁNDO debe elegir este agente
    # para atender un mensaje. Sin esto, el enrutador no puede distinguirlo
    # de los demás — sé concreto sobre qué tipo de tareas o palabras clave
    # lo activan.
    descripcion_enrutador: str = ""

    # Si ningún agente encaja claramente con el mensaje, el enrutador cae
    # en el que tenga es_predeterminado=True. Solo debería haber uno.
    es_predeterminado: bool = False

    tool_schemas: list[dict] = field(default_factory=list)
    tool_funcs: dict[str, Callable[..., Any]] = field(default_factory=dict)
    tools_irreversibles: set[str] = field(default_factory=set)


def system_prompt_con_fecha(agente: Agent_0) -> str:
    """Antepone la fecha/hora actual al system_prompt del agente.

    El modelo no tiene ninguna noción propia de "ahora" — sin esto, no
    puede resolver fechas relativas ('hoy', 'esta semana', 'el viernes')
    ni construir los parámetros ISO 8601 que piden tools como
    listar_eventos_calendario o crear_evento_calendario, y termina
    inventando una fecha o diciendo que no tiene acceso al sistema.

    Se recalcula en CADA turno (nunca al importar el agente, y nunca se
    guarda en Agent_0 — es frozen) para que nunca quede desactualizado,
    ni siquiera en un proceso que lleva días corriendo (ej. Render)."""
    ahora = datetime.now(ZoneInfo(ZONA_HORARIA_USUARIO))
    dia = _DIAS_ES[ahora.weekday()]
    contexto = (
        f"Contexto temporal: hoy es {dia} {ahora.strftime('%Y-%m-%d')}, son las "
        f"{ahora.strftime('%H:%M')} hora de {ZONA_HORARIA_USUARIO} "
        f"(ISO 8601 completo: {ahora.isoformat()}). Usa esto como referencia "
        f"para cualquier fecha u hora relativa ('hoy', 'mañana', 'esta "
        f"semana', 'el viernes que viene') y para construir los parámetros "
        f"de fecha ISO 8601 que piden algunas tools (ej. "
        f"listar_eventos_calendario, crear_evento_calendario) — nunca "
        f"inventes una fecha ni digas que no tienes forma de saber la fecha "
        f"actual."
    )
    return f"{contexto}\n\n{agente.system_prompt}"
