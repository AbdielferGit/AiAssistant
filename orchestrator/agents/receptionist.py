"""
Agente "recepcionista" — representa a UN negocio cliente frente a SUS
clientes (no al usuario del proyecto). Es la pieza central de Accueil+:
el mismo motor de orchestrator/ sirve a cualquier negocio con solo
cambiar config/negocio.yaml — nunca hace falta tocar código para
onboardear un cliente nuevo.

Diferencia clave con personal_assistant.py: ese agente actúa EN NOMBRE
del usuario (envía sus correos, agenda SU calendario, le escribe a SUS
contactos). Este agente actúa EN NOMBRE DEL NEGOCIO, hablándole a
desconocidos que le escriben — por diseño tiene MENOS tools, y ninguna
que envíe mensajes salientes a números arbitrarios (nada de
enviar_whatsapp/enviar_email/agregar_contacto): solo responde en la
conversación entrante y, si aplica, agenda o consulta el calendario del
negocio.

Hoy vive en el mismo repo que "asistente"/"ceo" y el enrutador puede
elegirlo (útil para probarlo con --agente receptionist). En un despliegue
real por cliente (fase 1 del roadmap de Accueil+), sería el ÚNICO agente
activo en la instancia de ese cliente — no hace falta enrutador cuando
solo hay un negocio detrás.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import yaml

from orchestrator.agents.base import Agent_0
from orchestrator.tools import google_workspace

log = logging.getLogger("orchestrator.agents.receptionist")

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "negocio.yaml"

_PERFIL_SIN_CONFIGURAR = {
    "nombre": "(negocio no configurado)",
    "tipo": "",
    "tono": "Neutral y profesional.",
    "horario": [],
    "servicios": [],
    "faq": [],
    "derivar_a_humano": "Decir que no hay nadie disponible para atender esto ahora mismo.",
    "usa_calendario": False,
}


def _cargar_perfil() -> dict:
    """Prioridad: config/negocio.yaml en disco > variable de entorno
    NEGOCIO_YAML (mismo patrón que CONTACTS_YAML/INVITED_USERS_YAML para
    hostings sin disco persistente) > perfil placeholder. Nunca lanza —
    si no hay perfil real, el agente sigue existiendo pero deja claro en
    su propio system prompt que no está configurado, en vez de romper el
    arranque de todo el orchestrator."""
    if CONFIG_PATH.exists():
        contenido = CONFIG_PATH.read_text(encoding="utf-8")
    else:
        contenido = os.getenv("NEGOCIO_YAML", "")
    if not contenido:
        log.warning(
            "No existe %s ni está definida NEGOCIO_YAML — el agente "
            "'recepcionista' arranca con un perfil placeholder. Copia "
            "config/negocio.yaml.example a config/negocio.yaml para "
            "configurar un negocio real.",
            CONFIG_PATH,
        )
        return dict(_PERFIL_SIN_CONFIGURAR)
    datos = yaml.safe_load(contenido) or {}
    return {**_PERFIL_SIN_CONFIGURAR, **datos}


PERFIL = _cargar_perfil()


def _construir_system_prompt(perfil: dict) -> str:
    lineas = [
        f"Tu es le préposé à l'accueil de {perfil['nombre']}"
        + (f" ({perfil['tipo']})" if perfil.get("tipo") else "")
        + ". Tu réponds aux messages des clients qui écrivent à ce commerce — "
        "tu ne parles JAMAIS en ton propre nom, toujours au nom du commerce.",
        "",
        f"Ton à adopter : {perfil.get('tono') or 'Neutre et professionnel.'}",
        "",
        "Règle stricte n°1 : ne réponds JAMAIS avec une information qui n'est "
        "pas dans ce profil. Si on te demande quelque chose que tu ne sais "
        "pas, dis-le clairement et propose de faire suivre la demande — "
        "n'invente rien (prix, disponibilité, politique) que tu ne connais pas.",
    ]

    if perfil.get("horario"):
        lineas += ["", "Horaire :"] + [f"- {h}" for h in perfil["horario"]]
    if perfil.get("servicios"):
        lineas += ["", "Services offerts :"] + [f"- {s}" for s in perfil["servicios"]]
    if perfil.get("faq"):
        lineas += ["", "Questions fréquentes (réponds avec ceci mot pour mot si la question correspond) :"]
        for item in perfil["faq"]:
            lineas.append(f"- Q: {item.get('pregunta', '')}\n  R: {item.get('respuesta', '')}")

    if perfil.get("derivar_a_humano"):
        lineas += [
            "",
            f"Si tu ne peux pas résoudre la demande toi-même : {perfil['derivar_a_humano']}",
        ]

    if perfil.get("usa_calendario"):
        lineas += [
            "",
            "Tu peux consulter_disponibilite et agendar_cita directement — "
            "confirme toujours la date/heure en toutes lettres avant de "
            "créer un rendez-vous, jamais en supposant.",
        ]

    return "\n".join(lineas)


SYSTEM_PROMPT = _construir_system_prompt(PERFIL)


def _consultar_disponibilidad(
    desde_iso: str | None = None, hasta_iso: str | None = None, max_resultados: int = 10
) -> dict:
    return google_workspace.listar_eventos(desde_iso, hasta_iso, max_resultados)


def _agendar_cita(titulo: str, inicio_iso: str, fin_iso: str) -> dict:
    return google_workspace.crear_evento(titulo, inicio_iso, fin_iso)


TOOL_FUNCS: dict = {}
TOOL_SCHEMAS: list = []

if PERFIL.get("usa_calendario"):
    TOOL_FUNCS["consultar_disponibilidad"] = _consultar_disponibilidad
    TOOL_FUNCS["agendar_cita"] = _agendar_cita
    TOOL_SCHEMAS += [
        {
            "name": "consultar_disponibilidad",
            "description": "Lit (ne modifie jamais) les prochains rendez-vous du calendrier. Utilise-la pour savoir quand il y a de la place.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "desde_iso": {"type": "string", "description": "Date/heure ISO 8601 de début. Par défaut : maintenant."},
                    "hasta_iso": {"type": "string", "description": "Date/heure ISO 8601 de fin. Optionnel."},
                    "max_resultados": {"type": "integer", "description": "Combien de rendez-vous retourner (défaut 10)."},
                },
                "required": [],
            },
        },
        {
            "name": "agendar_cita",
            "description": "Crée un rendez-vous dans le calendrier du commerce. Confirme toujours la date/heure exacte avec le client avant de l'appeler.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "titulo": {"type": "string", "description": "Ex. 'Réservation — Jean Tremblay, 4 personnes'"},
                    "inicio_iso": {"type": "string", "description": "Date/heure ISO 8601"},
                    "fin_iso": {"type": "string", "description": "Date/heure ISO 8601"},
                },
                "required": ["titulo", "inicio_iso", "fin_iso"],
            },
        },
    ]

# agendar_cita es reversible (se puede borrar el evento después), igual
# que en personal_assistant.py — no pide confirmación humana. Este
# agente, a propósito, no tiene NINGUNA tool irreversible: no envía nada
# a nadie, solo responde en la conversación y toca el calendario del
# propio negocio.
TOOLS_IRREVERSIBLES: set = set()

AGENTE = Agent_0(
    id="recepcionista",
    nombre=f"Recepcionista — {PERFIL['nombre']}",
    descripcion_enrutador=(
        "Úsalo SOLO cuando el mensaje viene claramente de un cliente externo "
        "escribiéndole al negocio (pregunta de horario, reserva, servicios) — "
        "no para tareas personales del usuario del sistema, para eso está "
        "'asistente'."
    ),
    system_prompt=SYSTEM_PROMPT,
    tool_schemas=TOOL_SCHEMAS,
    tool_funcs=TOOL_FUNCS,
    tools_irreversibles=TOOLS_IRREVERSIBLES,
)
