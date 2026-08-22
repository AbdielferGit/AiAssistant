"""
Agente "asistente" — el asistente personal original: redacta con tu
estilo, envía WhatsApp/email/Messenger (con confirmación humana y lista
blanca de contactos), maneja Calendar y acciones en Mac/Android.
"""
from __future__ import annotations

from orchestrator import contacts
from orchestrator.memory.style_profile import buscar_ejemplos_de_estilo
from orchestrator.tools import google_workspace, macos_actions, messenger, whatsapp

SYSTEM_PROMPT = """\
Eres el asistente personal del usuario. Puedes redactar mensajes que suenen
exactamente como él (usa siempre `redactar_borrador` antes de enviar algo) y
ejecutar acciones en su Mac y su Android.

Regla estricta #1 — lista blanca de contactos: SOLO puedes enviar mensajes
(WhatsApp, email, Messenger, iMessage) a personas que estén en la lista
blanca activa. Si tienes duda sobre si alguien está autorizado, llama a
`listar_contactos_autorizados` antes de redactar o enviar nada. Cada tool
de envío ya rechaza por su cuenta a quien no esté en la lista (verás
`status: "rechazado"` en la respuesta) — si eso pasa, informa al usuario en
vez de intentar otra vía para llegar a esa persona.

Regla estricta #2 — confirmación humana: para CUALQUIER acción irreversible
(enviar mensajes, publicar, comprar) primero muestra el borrador/resumen
exacto de lo que vas a hacer. El propio sistema te pedirá confirmación por
terminal antes de ejecutar la tool — nunca asumas que ya se envió algo
hasta ver el resultado real de la tool.
"""


# --- Implementación de cada tool (funciones planas, sync o async) ---------

def _redactar_borrador(destinatario: str, tema: str, canal: str) -> dict:
    try:
        ejemplos = buscar_ejemplos_de_estilo(destinatario=destinatario, canal=canal, k=6)
    except NotImplementedError:
        ejemplos = []
    return {
        "destinatario": destinatario,
        "tema": tema,
        "canal": canal,
        "ejemplos_de_estilo": ejemplos,
        "nota": (
            ""
            if ejemplos
            else "Aún no hay memoria de estilo configurada (falta elegir proveedor "
            "de embeddings en orchestrator/memory/style_profile.py) — usa un tono "
            "neutral y cordial mientras tanto."
        ),
        "instruccion": (
            "Redacta el mensaje usando el tono, largo y vocabulario que reflejan "
            "estos ejemplos. No inventes hechos que no te dieron."
        ),
    }


def _listar_contactos_autorizados() -> dict:
    return {
        "contactos": [
            {"nombre": c.nombre, "alias": c.alias, "activo": c.activo, "canales": list(c.canales)}
            for c in contacts.listar_todos()
        ]
    }


async def _enviar_whatsapp(numero: str, texto: str) -> dict:
    return await whatsapp.enviar(numero=numero, texto=texto)


def _enviar_email(destinatario: str, asunto: str, cuerpo: str) -> dict:
    return google_workspace.enviar_email(destinatario, asunto, cuerpo)


async def _enviar_messenger(destinatario_id: str, texto: str) -> dict:
    return await messenger.enviar(destinatario_id, texto)


def _crear_evento_calendario(titulo: str, inicio_iso: str, fin_iso: str) -> dict:
    return google_workspace.crear_evento(titulo, inicio_iso, fin_iso)


def _abrir_app_o_archivo_mac(nombre: str) -> dict:
    return macos_actions.abrir(nombre)


async def _ejecutar_accion_android(accion: str, parametros: dict | None = None) -> dict:
    from orchestrator.bridge.server import encolar_comando

    return await encolar_comando(accion=accion, parametros=parametros or {})


TOOL_FUNCS = {
    "redactar_borrador": _redactar_borrador,
    "listar_contactos_autorizados": _listar_contactos_autorizados,
    "enviar_whatsapp": _enviar_whatsapp,
    "enviar_email": _enviar_email,
    "enviar_messenger": _enviar_messenger,
    "crear_evento_calendario": _crear_evento_calendario,
    "abrir_app_o_archivo_mac": _abrir_app_o_archivo_mac,
    "ejecutar_accion_android": _ejecutar_accion_android,
}

# --- Schemas que ve el modelo (formato tool-use de la API de Anthropic) --

TOOL_SCHEMAS = [
    {
        "name": "redactar_borrador",
        "description": (
            "Genera un borrador de mensaje usando ejemplos reales de cómo el "
            "usuario le escribe a ese destinatario. Úsala SIEMPRE antes de "
            "enviar_whatsapp/enviar_email/enviar_messenger."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "destinatario": {"type": "string", "description": "Nombre o alias del contacto"},
                "tema": {"type": "string", "description": "De qué trata el mensaje"},
                "canal": {"type": "string", "enum": ["whatsapp", "email", "messenger", "imessage"]},
            },
            "required": ["destinatario", "tema", "canal"],
        },
    },
    {
        "name": "listar_contactos_autorizados",
        "description": (
            "Devuelve los contactos de la lista blanca (config/contacts.yaml). "
            "Úsala para saber a quién SÍ puedes escribirle antes de intentar "
            "redactar o enviar algo."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "enviar_whatsapp",
        "description": "Envía un mensaje de WhatsApp. IRREVERSIBLE.",
        "input_schema": {
            "type": "object",
            "properties": {
                "numero": {"type": "string", "description": "Formato internacional, ej. '+521234567890'"},
                "texto": {"type": "string"},
            },
            "required": ["numero", "texto"],
        },
    },
    {
        "name": "enviar_email",
        "description": "Envía un correo por Gmail. IRREVERSIBLE.",
        "input_schema": {
            "type": "object",
            "properties": {
                "destinatario": {"type": "string"},
                "asunto": {"type": "string"},
                "cuerpo": {"type": "string"},
            },
            "required": ["destinatario", "asunto", "cuerpo"],
        },
    },
    {
        "name": "enviar_messenger",
        "description": "Envía un mensaje de Messenger. IRREVERSIBLE.",
        "input_schema": {
            "type": "object",
            "properties": {
                "destinatario_id": {"type": "string"},
                "texto": {"type": "string"},
            },
            "required": ["destinatario_id", "texto"],
        },
    },
    {
        "name": "crear_evento_calendario",
        "description": "Crea un evento en Google Calendar. Reversible (se puede borrar).",
        "input_schema": {
            "type": "object",
            "properties": {
                "titulo": {"type": "string"},
                "inicio_iso": {"type": "string", "description": "Fecha/hora ISO 8601"},
                "fin_iso": {"type": "string", "description": "Fecha/hora ISO 8601"},
            },
            "required": ["titulo", "inicio_iso", "fin_iso"],
        },
    },
    {
        "name": "abrir_app_o_archivo_mac",
        "description": "Abre una aplicación o archivo en la Mac. Reversible.",
        "input_schema": {
            "type": "object",
            "properties": {"nombre": {"type": "string"}},
            "required": ["nombre"],
        },
    },
    {
        "name": "ejecutar_accion_android",
        "description": (
            "Encola una acción para que el bridge de Android la ejecute "
            "(notificación, disparar un Tasker, leer batería, etc.)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "accion": {"type": "string", "enum": ["notificar", "leer_bateria", "hablar", "disparar_tasker"]},
                "parametros": {"type": "object"},
            },
            "required": ["accion"],
        },
    },
]

TOOLS_IRREVERSIBLES = {
    "enviar_whatsapp",
    "enviar_email",
    "enviar_messenger",
    "publicar_contenido",
}


from orchestrator.agents.base import Agent_0

AGENTE = Agent_0(
    id="asistente",
    nombre="Asistente personal",
    descripcion_enrutador=(
        "Agente de propósito general. Tareas personales del día a día: "
        "enviar o redactar mensajes de WhatsApp/email/Messenger con el "
        "estilo del usuario, agendar o consultar eventos de Calendar, abrir "
        "apps o archivos en la Mac, ejecutar acciones en el Android "
        "(notificaciones, Tasker, batería), o consultar la lista de "
        "contactos autorizados. También es el agente por defecto cuando el "
        "mensaje no encaja claramente con ningún agente especializado."
    ),
    es_predeterminado=True,
    system_prompt=SYSTEM_PROMPT,
    tool_schemas=TOOL_SCHEMAS,
    tool_funcs=TOOL_FUNCS,
    tools_irreversibles=TOOLS_IRREVERSIBLES,
)
