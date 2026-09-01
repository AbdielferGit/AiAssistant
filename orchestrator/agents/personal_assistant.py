"""
Agente "asistente" — el asistente personal original: redacta con tu
estilo, envía WhatsApp/email/Messenger (con confirmación humana y lista
blanca de contactos), maneja Calendar y acciones en la Mac.
"""
from __future__ import annotations

from orchestrator import contacts
from orchestrator.memory.style_profile import buscar_ejemplos_de_estilo
from orchestrator.tools import google_workspace, macos_actions, messenger, whatsapp

SYSTEM_PROMPT = """\
Eres el asistente personal del usuario. Puedes redactar mensajes que suenen
exactamente como él (usa siempre `redactar_borrador` antes de enviar algo) y
ejecutar acciones en su Mac.

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

Regla estricta #3 — agregar_contacto es más sensible que las demás
irreversibles: modifica la lista blanca misma. Además de la confirmación
normal, el sistema le pide al usuario un PIN de un solo uso que TÚ NUNCA
VES — no lo inventes, no lo asumas, no lo repitas de una respuesta
anterior. Si la tool vuelve con 'cancelado_por_usuario', dile al usuario
que el PIN no coincidió o que canceló — no reintentes solo.
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


def _agregar_contacto(nombre: str, alias: str, medios: dict[str, str] | None = None) -> dict:
    return contacts.agregar_contacto(nombre, alias, medios or {})


async def _enviar_whatsapp(numero: str, texto: str) -> dict:
    return await whatsapp.enviar(numero=numero, texto=texto)


def _enviar_email(destinatario: str, asunto: str, cuerpo: str) -> dict:
    return google_workspace.enviar_email(destinatario, asunto, cuerpo)


def _leer_correos(cantidad: int = 1) -> dict:
    return google_workspace.leer_correos(cantidad)


async def _enviar_messenger(destinatario_id: str, texto: str) -> dict:
    return await messenger.enviar(destinatario_id, texto)


def _crear_evento_calendario(titulo: str, inicio_iso: str, fin_iso: str) -> dict:
    return google_workspace.crear_evento(titulo, inicio_iso, fin_iso)


def _listar_eventos_calendario(
    desde_iso: str | None = None, hasta_iso: str | None = None, max_resultados: int = 10
) -> dict:
    return google_workspace.listar_eventos(desde_iso, hasta_iso, max_resultados)


def _eliminar_evento_calendario(evento_id: str) -> dict:
    return google_workspace.eliminar_evento(evento_id)


def _abrir_app_o_archivo_mac(nombre: str) -> dict:
    return macos_actions.abrir(nombre)


TOOL_FUNCS = {
    "redactar_borrador": _redactar_borrador,
    "listar_contactos_autorizados": _listar_contactos_autorizados,
    "agregar_contacto": _agregar_contacto,
    "enviar_whatsapp": _enviar_whatsapp,
    "enviar_email": _enviar_email,
    "leer_correos": _leer_correos,
    "enviar_messenger": _enviar_messenger,
    "crear_evento_calendario": _crear_evento_calendario,
    "listar_eventos_calendario": _listar_eventos_calendario,
    "eliminar_evento_calendario": _eliminar_evento_calendario,
    "abrir_app_o_archivo_mac": _abrir_app_o_archivo_mac,
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
        "name": "agregar_contacto",
        "description": (
            "Agrega un contacto nuevo a la lista blanca (config/contacts.yaml). "
            "IRREVERSIBLE y de más alto riesgo que las demás tools "
            "irreversibles: modifica la lista blanca misma, así que el "
            "usuario tiene que confirmar con un PIN de un solo uso que se "
            "le muestra a él directamente y que TÚ nunca ves. No inventes "
            "ni asumas un PIN — si la tool devuelve "
            "'cancelado_por_usuario', el PIN no coincidió o el usuario "
            "canceló; dile eso, no lo intentes de nuevo sin que el usuario "
            "lo pida explícitamente."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "nombre": {"type": "string"},
                "alias": {"type": "string", "description": "Identificador corto único, ej. 'juan'."},
                "medios": {
                    "type": "object",
                    "description": (
                        "Mapa medio→valor, ej. "
                        '{"whatsapp": "+521234567890", "email": "juan@correo.com"}. '
                        "Puede ir vacío y agregarse después."
                    ),
                    "additionalProperties": {"type": "string"},
                },
            },
            "required": ["nombre", "alias"],
        },
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
        "name": "leer_correos",
        "description": (
            "Lee (nunca modifica) los correos más recientes de la bandeja "
            "de entrada de Gmail — de, asunto, fecha y cuerpo. Solo "
            "lectura, no requiere confirmación."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "cantidad": {
                    "type": "integer",
                    "description": "Cuántos correos leer, empezando por el más reciente (por defecto 1).",
                },
            },
            "required": [],
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
        "name": "listar_eventos_calendario",
        "description": (
            "Lee (nunca modifica) los próximos eventos del calendario "
            "principal de Google del usuario. Úsala para responder preguntas "
            "como '¿qué tengo hoy?', '¿cuándo es mi próxima reunión?' o "
            "'¿tengo algo el viernes?'. Solo lectura — no requiere "
            "confirmación."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "desde_iso": {
                    "type": "string",
                    "description": "Fecha/hora ISO 8601 desde donde buscar. Si se omite, usa el momento actual.",
                },
                "hasta_iso": {
                    "type": "string",
                    "description": "Fecha/hora ISO 8601 límite superior. Opcional — si se omite, no hay límite.",
                },
                "max_resultados": {
                    "type": "integer",
                    "description": "Cuántos eventos devolver como máximo (por defecto 10).",
                },
            },
            "required": [],
        },
    },
    {
        "name": "eliminar_evento_calendario",
        "description": (
            "Borra un evento del calendario principal por su id (usa "
            "listar_eventos_calendario primero para conseguirlo si no lo "
            "tienes). IRREVERSIBLE."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"evento_id": {"type": "string"}},
            "required": ["evento_id"],
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
]

TOOLS_IRREVERSIBLES = {
    "enviar_whatsapp",
    "enviar_email",
    "enviar_messenger",
    "eliminar_evento_calendario",
    "agregar_contacto",
    "publicar_contenido",
}


from orchestrator.agents.base import Agent_0

AGENTE = Agent_0(
    id="asistente",
    nombre="Asistente personal",
    descripcion_enrutador=(
        "Agente de propósito general. Tareas personales del día a día: "
        "enviar o redactar mensajes de WhatsApp/email/Messenger con el "
        "estilo del usuario, leer correos de Gmail, agendar, consultar o borrar eventos de Calendar, abrir "
        "apps o archivos en la Mac, consultar la lista de "
        "contactos autorizados o agregar un contacto nuevo (con PIN de "
        "confirmación). También es el agente por defecto cuando el "
        "mensaje no encaja claramente con ningún agente especializado."
    ),
    es_predeterminado=True,
    system_prompt=SYSTEM_PROMPT,
    tool_schemas=TOOL_SCHEMAS,
    tool_funcs=TOOL_FUNCS,
    tools_irreversibles=TOOLS_IRREVERSIBLES,
)
