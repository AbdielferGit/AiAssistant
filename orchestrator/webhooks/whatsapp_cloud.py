"""
Webhook de la WhatsApp Cloud API (Meta) — mensajes ENTRANTES.

Reemplaza lo que antes vivía en `orchestrator/bridge/server.py` (eliminado
al simplificar el proyecto a solo-local: ya no hay puente de Android ni
WhatsApp no oficial). Esto es lo único de ese archivo que seguía haciendo
falta: Meta necesita un endpoint HTTPS público al que llamar cuando
alguien escribe al número del negocio, tanto para el handshake de
verificación como para avisar de cada mensaje nuevo.

Desde aquí se dispara el loop completo del agente "recepcionista"
(orchestrator/agents/receptionist.py, configurado por config/negocio.yaml):
un mensaje entrante corre el mismo tool-use loop que main.py, y la
respuesta del modelo se manda de vuelta por WhatsApp automáticamente —
sin humano en el medio. Es justo por eso que el agente "recepcionista"
está diseñado sin ninguna tool irreversible (no envía nada a números
arbitrarios, no borra nada) y con la regla estricta de nunca inventar
información fuera de su perfil — no hay nadie confirmando cada respuesta
antes de que salga.

## Por qué este webhook NO usa la lista blanca de contacts.yaml

`contacts.yaml` autoriza a quién le puede escribir/contactar el usuario
PERSONALMENTE (orchestrator/tools/whatsapp.py, usado por el agente
"asistente") — tiene sentido restringirlo ahí porque es la agenda privada
de una persona. El "recepcionista" representa a un NEGOCIO: cualquier
desconocido que le escriba a su número de WhatsApp es exactamente el
caso de uso (un cliente potencial). Exigir lista blanca aquí rompería el
producto — Accueil+ existe para atender gente que el negocio todavía no
conoce. En su lugar, la protección es un límite de mensajes por remitente
por hora (ver _LIMITE_MENSAJES_POR_HORA) contra abuso/spam, no una lista
de aprobados.

## Identificador del remitente: teléfono o LID (nombre de usuario)

WhatsApp permite que alguien oculte su número real detrás de un "nombre
de usuario" — en ese caso Meta no manda `messages[].from` (el número),
sino `messages[].from_user_id` (un identificador opaco, LID). Este código
acepta CUALQUIERA de los dos y lo usa tal cual, de punta a punta (como
clave de conversación, para la ventana de 24h, y como destinatario al
responder) — nunca asume que es un número de teléfono. Es la única forma
de que esto funcione para cualquier cliente real, no solo para quien
tenga desactivado el nombre de usuario.

También registra el mensaje entrante en `inbound_tracker` — de eso depende
la ventana de 24 h que permite mandar texto libre sin plantilla pre-aprobada.

Cómo correrlo: `uvicorn orchestrator.webhooks.whatsapp_cloud:app --port 8090`
y expón ese puerto con HTTPS (ngrok para pruebas) — ver MANUAL_CONEXION.md.
"""
from __future__ import annotations

import inspect
import json
import logging
import time

import anthropic
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, Response

from orchestrator.agents.base import system_prompt_con_fecha
from orchestrator.agents.receptionist import AGENTE as RECEPCIONISTA
from orchestrator.config import settings
from orchestrator.memory.inbound_tracker import registrar_inbound
from orchestrator.tools import whatsapp_cloud_api

log = logging.getLogger("webhooks.whatsapp_cloud")
app = FastAPI(title="AiAssistant — webhook WhatsApp Cloud API")

_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
MAX_TOKENS = 1024

# Historial por remitente — mismo patrón simple que _conversaciones en
# orchestrator/web/app.py (en memoria, sin límite; suficiente para el
# volumen de un piloto). Se pierde si el proceso se reinicia — aceptable
# por ahora, el negocio.yaml no depende de esto para nada crítico.
_conversaciones: dict[str, list[dict]] = {}

# Límite anti-abuso: al no haber lista blanca (ver docstring del módulo),
# cualquiera puede escribir — esto evita que una sola persona (un bug de
# un cliente, un bot, alguien jugando) agote el presupuesto de la API de
# Anthropic. No es una medida de seguridad fina, es un techo razonable.
_LIMITE_MENSAJES_POR_HORA = 20
_mensajes_recientes: dict[str, list[float]] = {}


def _excede_limite(remitente: str) -> bool:
    ahora = time.time()
    marcas = [t for t in _mensajes_recientes.get(remitente, []) if ahora - t < 3600]
    marcas.append(ahora)
    _mensajes_recientes[remitente] = marcas
    return len(marcas) > _LIMITE_MENSAJES_POR_HORA


@app.get("/webhooks/whatsapp_cloud")
async def verificar_webhook(request: Request):
    """Handshake que exige Meta al configurar el webhook (Meta for
    Developers → WhatsApp → Configuration → Webhook). Responde
    hub.challenge tal cual si hub.verify_token coincide con
    WHATSAPP_CLOUD_API_VERIFY_TOKEN."""
    params = request.query_params
    if (
        params.get("hub.mode") == "subscribe"
        and settings.whatsapp_cloud_api_verify_token
        and params.get("hub.verify_token") == settings.whatsapp_cloud_api_verify_token
    ):
        return Response(content=params.get("hub.challenge", ""), media_type="text/plain")
    raise HTTPException(status_code=403, detail="Verificación de webhook fallida")


@app.post("/webhooks/whatsapp_cloud")
async def recibir_webhook(request: Request, background_tasks: BackgroundTasks):
    """Responde 200 a Meta de inmediato y procesa en segundo plano — Meta
    reintenta/descarta el webhook si tarda en contestar, y generar la
    respuesta del agente puede tomar unos segundos."""
    payload = await request.json()
    log.debug("Payload crudo del webhook: %s", json.dumps(payload, ensure_ascii=False))
    for entrada in payload.get("entry", []):
        for cambio in entrada.get("changes", []):
            for mensaje in cambio.get("value", {}).get("messages", []):
                # Puede venir como número de teléfono ("from") o, si el
                # remitente usa nombre de usuario en vez de compartir su
                # número, como identificador opaco ("from_user_id") — ver
                # docstring del módulo. Se usa el que venga, tal cual.
                remitente = mensaje.get("from") or mensaje.get("from_user_id", "")
                texto = mensaje.get("text", {}).get("body", "")
                if remitente and texto:
                    background_tasks.add_task(_procesar_mensaje_entrante, remitente, texto)
    return {"status": "ok"}


async def _procesar_mensaje_entrante(remitente: str, texto: str) -> None:
    if _excede_limite(remitente):
        log.warning("Mensaje descartado por límite de %s/hora: remitente=%s", _LIMITE_MENSAJES_POR_HORA, remitente)
        return

    registrar_inbound(remitente)
    log.info("Mensaje de WhatsApp aceptado de %s: %s", remitente, texto)

    try:
        respuesta = await _correr_recepcionista(remitente, texto)
    except Exception:
        log.exception("El agente recepcionista falló respondiendo a %s", remitente)
        return

    if not respuesta:
        return
    resultado = await whatsapp_cloud_api.enviar(numero=remitente, texto=respuesta)
    if resultado.get("status") not in ("enviado", "ok"):
        log.error("No se pudo enviar la respuesta a %s: %s", remitente, resultado)


async def _ejecutar_tool(nombre: str, args: dict) -> dict:
    """Sin gate de confirmación humana a propósito: recepcionista no tiene
    ninguna tool irreversible (ver receptionist.py) — no hay nada que
    confirmar. Igual que en main.py/web/app.py, cualquier excepción de la
    tool se atrapa aquí y nunca se propaga, para que el historial nunca
    quede con un tool_use sin resolver."""
    func = RECEPCIONISTA.tool_funcs.get(nombre)
    if func is None:
        return {"status": "error", "detalle": f"Tool desconocida: {nombre}"}
    try:
        resultado = func(**args)
        if inspect.isawaitable(resultado):
            resultado = await resultado
        return resultado
    except Exception as exc:
        log.exception("Tool %s(%s) falló", nombre, args)
        return {"status": "error", "detalle": f"{type(exc).__name__}: {exc}"}


async def _correr_recepcionista(remitente: str, texto: str) -> str:
    mensajes = _conversaciones.setdefault(remitente, [])
    mensajes.append({"role": "user", "content": texto})

    while True:
        respuesta = await _client.messages.create(
            model=settings.anthropic_model,
            max_tokens=MAX_TOKENS,
            system=system_prompt_con_fecha(RECEPCIONISTA),
            tools=RECEPCIONISTA.tool_schemas,
            messages=mensajes,
        )
        mensajes.append({"role": "assistant", "content": respuesta.content})
        texto_respuesta = " ".join(b.text for b in respuesta.content if b.type == "text").strip()

        llamadas = [b for b in respuesta.content if b.type == "tool_use"]
        if not llamadas:
            return texto_respuesta

        resultados = []
        for llamada in llamadas:
            resultado = await _ejecutar_tool(llamada.name, llamada.input)
            resultados.append(
                {
                    "type": "tool_result",
                    "tool_use_id": llamada.id,
                    "content": json.dumps(resultado, ensure_ascii=False),
                }
            )
        mensajes.append({"role": "user", "content": resultados})


@app.get("/health")
async def health():
    return {"status": "ok"}
