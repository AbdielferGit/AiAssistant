"""
Cliente de la WhatsApp Cloud API (Meta, oficial) — usado cuando
WHATSAPP_PROVIDER=cloud_api (valor por defecto, recomendado mientras
pruebas con el "número de prueba" gratuito de Meta for Developers).

A diferencia de whatsapp-bridge/ (Baileys), aquí no hay QR ni sesión que
mantener: es una API REST normal con un token de acceso. Ver
MANUAL_CONEXION.md sección 3 para cómo obtener WHATSAPP_CLOUD_API_TOKEN y
WHATSAPP_CLOUD_API_PHONE_NUMBER_ID desde el panel de Meta.

Limitación importante mientras el número esté en modo prueba: solo puedes
enviar texto libre a un contacto si te escribió en las últimas 24 h (ver
orchestrator/memory/inbound_tracker.py). Fuera de esa ventana, Meta exige
una plantilla pre-aprobada — este cliente no las implementa todavía
(deliberado: no las necesitas para validar el flujo de pruebas, solo pide
que tu contacto de prueba te escriba primero).
"""
from __future__ import annotations

import httpx

from orchestrator.config import settings
from orchestrator.memory.inbound_tracker import dentro_de_ventana_24h

GRAPH_API_BASE = "https://graph.facebook.com/v20.0"


async def enviar(numero: str, texto: str) -> dict:
    if not settings.whatsapp_cloud_api_token or not settings.whatsapp_cloud_api_phone_number_id:
        return {
            "status": "no_configurado",
            "detalle": (
                "Faltan WHATSAPP_CLOUD_API_TOKEN / WHATSAPP_CLOUD_API_PHONE_NUMBER_ID "
                "en .env. Sigue MANUAL_CONEXION.md sección 3 para obtener el "
                "número de prueba desde developers.facebook.com."
            ),
        }

    numero_limpio = numero.lstrip("+")

    if not dentro_de_ventana_24h(numero_limpio):
        return {
            "status": "rechazado",
            "motivo": (
                f"'{numero}' no te ha escrito en las últimas 24 h — el número "
                f"de prueba de Meta no permite texto libre iniciado por ti "
                f"fuera de esa ventana. Pide que te escriba primero (ej. "
                f"'hola') al número de prueba, o configura una plantilla "
                f"pre-aprobada si necesitas iniciar la conversación tú."
            ),
        }

    url = f"{GRAPH_API_BASE}/{settings.whatsapp_cloud_api_phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": numero_limpio,
        "type": "text",
        "text": {"body": texto},
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            url,
            headers={"Authorization": f"Bearer {settings.whatsapp_cloud_api_token}"},
            json=payload,
        )
        if resp.status_code >= 400:
            return {"status": "error", "detalle": resp.text}
        return {"status": "enviado", "respuesta": resp.json()}
