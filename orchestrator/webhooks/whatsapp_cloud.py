"""
Webhook de la WhatsApp Cloud API (Meta) — mensajes ENTRANTES.

Reemplaza lo que antes vivía en `orchestrator/bridge/server.py` (eliminado
al simplificar el proyecto a solo-local: ya no hay puente de Android ni
WhatsApp no oficial). Esto es lo único de ese archivo que seguía haciendo
falta: Meta necesita un endpoint HTTPS público al que llamar cuando
alguien te escribe, tanto para el handshake de verificación como para
avisar de cada mensaje nuevo.

Aplica la misma lista blanca que `orchestrator/tools/whatsapp_cloud_api.py`
usa en la dirección de salida: un mensaje de alguien fuera de
`config/contacts.yaml` se descarta aquí mismo, nunca llega a procesarse.

También registra el mensaje entrante en `inbound_tracker` — de eso depende
la ventana de 24 h que le permite a `enviar_whatsapp` mandar texto libre
sin plantilla pre-aprobada (ver `orchestrator/tools/whatsapp_cloud_api.py`).

Cómo correrlo: `uvicorn orchestrator.webhooks.whatsapp_cloud:app --port 8090`
y expón ese puerto con HTTPS (ngrok para pruebas) — ver MANUAL_CONEXION.md.
Si no vas a recibir WhatsApp entrante todavía, no hace falta correr esto:
`enviar_whatsapp` funciona sin este webhook, solo pierdes la ventana de 24h.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request, Response

from orchestrator import contacts
from orchestrator.config import settings
from orchestrator.memory.inbound_tracker import registrar_inbound

log = logging.getLogger("webhooks.whatsapp_cloud")
app = FastAPI(title="AiAssistant — webhook WhatsApp Cloud API")


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
async def recibir_webhook(request: Request):
    payload = await request.json()
    for entrada in payload.get("entry", []):
        for cambio in entrada.get("changes", []):
            for mensaje in cambio.get("value", {}).get("messages", []):
                remitente = mensaje.get("from", "")
                texto = mensaje.get("text", {}).get("body", "")
                if remitente and texto:
                    _procesar_mensaje_entrante(remitente, texto)
    return {"status": "ok"}


def _procesar_mensaje_entrante(remitente: str, texto: str) -> None:
    try:
        contacto = contacts.verificar_autorizado("whatsapp", remitente)
    except contacts.ContactoNoAutorizado:
        log.warning("Mensaje de WhatsApp descartado (fuera de lista blanca): remitente=%s", remitente)
        return
    registrar_inbound(remitente.lstrip("+"))
    log.info("Mensaje de WhatsApp aceptado de %s: %s", contacto.nombre, texto)


@app.get("/health")
async def health():
    return {"status": "ok"}
