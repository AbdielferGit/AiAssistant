"""
Bus de comandos entre el orchestrator y el celular Android.

El orchestrator ENCOLA comandos aquí; android-bridge/scripts/listener.py
(corriendo en Termux) hace polling de /commands/next y reporta el
resultado. Se comunican solo dentro de la red privada de Tailscale (ver
MANUAL_CONEXION.md sección 2) — nunca expongas este puerto a internet
abierto sin autenticación adicional.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request, Response
from pydantic import BaseModel

from orchestrator import contacts
from orchestrator.config import settings
from orchestrator.memory.inbound_tracker import registrar_inbound

log = logging.getLogger("bridge.server")
app = FastAPI(title="AiAsistant phone bridge")

_cola: asyncio.Queue[dict] = asyncio.Queue()
_resultados: dict[str, asyncio.Future] = {}

# Cola simple de mensajes entrantes ya autorizados, pendientes de que el
# loop del agente los procese. Es un placeholder deliberado: hoy solo
# demuestra que el filtro de lista blanca corre ANTES de aceptar nada;
# cuando conectes un loop de agente reactivo (no solo por voz), reemplaza
# esto por algo persistente y dispara el procesamiento real aquí.
_inbox: list[dict] = []


def _verificar_token(authorization: str | None) -> None:
    esperado = f"Bearer {settings.phone_bridge_token}"
    if not settings.phone_bridge_token or authorization != esperado:
        raise HTTPException(status_code=401, detail="Token inválido")


class ComandoEntrante(BaseModel):
    accion: str
    parametros: dict[str, Any] = {}


class ResultadoComando(BaseModel):
    comando_id: str
    resultado: dict[str, Any]


class MensajeEntrante(BaseModel):
    remitente: str
    texto: str


async def encolar_comando(accion: str, parametros: dict) -> dict:
    """Llamado desde orchestrator/tools vía la tool `ejecutar_accion_android`."""
    comando_id = str(uuid.uuid4())
    futuro: asyncio.Future = asyncio.get_event_loop().create_future()
    _resultados[comando_id] = futuro
    await _cola.put({"id": comando_id, "accion": accion, "parametros": parametros})
    try:
        return await asyncio.wait_for(futuro, timeout=30)
    except asyncio.TimeoutError:
        return {"status": "timeout", "detalle": "El celular no respondió a tiempo"}
    finally:
        _resultados.pop(comando_id, None)


@app.get("/commands/next")
async def siguiente_comando(authorization: str | None = Header(default=None)):
    _verificar_token(authorization)
    try:
        comando = _cola.get_nowait()
    except asyncio.QueueEmpty:
        return {"comando": None}
    return {"comando": comando}


@app.post("/commands/result")
async def reportar_resultado(payload: ResultadoComando, authorization: str | None = Header(default=None)):
    _verificar_token(authorization)
    futuro = _resultados.get(payload.comando_id)
    if futuro and not futuro.done():
        futuro.set_result(payload.resultado)
    return {"status": "recibido"}


@app.post("/inbound/{canal}")
async def mensaje_entrante(
    canal: str, payload: MensajeEntrante, authorization: str | None = Header(default=None)
):
    """Los puentes de cada canal (whatsapp-bridge/index.js, futuros
    equivalentes de Messenger/email) llaman aquí cuando llega un mensaje.

    Autorización en la dirección de ENTRADA: si `payload.remitente` no está
    en la lista blanca activa, el mensaje se descarta y NUNCA llega a
    procesarse — ni se guarda, ni dispara nada, ni se usa como contexto.
    Esto es tan obligatorio como la verificación de salida en
    orchestrator/tools/*.py.
    """
    _verificar_token(authorization)
    return _procesar_mensaje_entrante(canal, payload.remitente, payload.texto)


def _procesar_mensaje_entrante(canal: str, remitente: str, texto: str) -> dict:
    try:
        contacto = contacts.verificar_autorizado(canal, remitente)
    except contacts.ContactoNoAutorizado:
        log.warning("Mensaje entrante descartado (fuera de lista blanca): canal=%s remitente=%s", canal, remitente)
        return {"status": "ignorado"}

    if canal == "whatsapp":
        # Habilita la ventana de 24h para texto libre (ver
        # orchestrator/tools/whatsapp_cloud_api.py) solo para remitentes ya
        # autorizados — nunca se registra a alguien fuera de la lista blanca.
        registrar_inbound(remitente.lstrip("+"))

    _inbox.append({"contacto": contacto.nombre, "canal": canal, "texto": texto})
    log.info("Mensaje entrante aceptado de %s (%s)", contacto.nombre, canal)
    return {"status": "aceptado", "contacto": contacto.nombre}


@app.get("/inbound")
async def ver_inbox(authorization: str | None = Header(default=None)):
    """Solo para depuración mientras no exista un loop de agente reactivo."""
    _verificar_token(authorization)
    return {"pendientes": _inbox}


@app.get("/webhooks/whatsapp_cloud")
async def verificar_webhook_whatsapp_cloud(request: Request):
    """Handshake de verificación que exige Meta al configurar el webhook del
    número de prueba (Meta for Developers → WhatsApp → Configuration →
    Webhook). Debe responder el valor de hub.challenge tal cual si
    hub.verify_token coincide con WHATSAPP_CLOUD_API_VERIFY_TOKEN."""
    params = request.query_params
    if (
        params.get("hub.mode") == "subscribe"
        and params.get("hub.verify_token") == settings.whatsapp_cloud_api_verify_token
        and settings.whatsapp_cloud_api_verify_token
    ):
        return Response(content=params.get("hub.challenge", ""), media_type="text/plain")
    raise HTTPException(status_code=403, detail="Verificación de webhook fallida")


@app.post("/webhooks/whatsapp_cloud")
async def recibir_webhook_whatsapp_cloud(request: Request):
    """Mensajes entrantes al número de prueba/producción de la Cloud API.
    Aplica la misma lista blanca que /inbound/{canal} antes de aceptar nada
    — ver _procesar_mensaje_entrante."""
    payload = await request.json()
    for entrada in payload.get("entry", []):
        for cambio in entrada.get("changes", []):
            for mensaje in cambio.get("value", {}).get("messages", []):
                remitente = mensaje.get("from", "")
                texto = mensaje.get("text", {}).get("body", "")
                if remitente and texto:
                    _procesar_mensaje_entrante("whatsapp", remitente, texto)
    return {"status": "ok"}


@app.get("/health")
async def health():
    return {"status": "ok"}
