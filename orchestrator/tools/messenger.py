"""
Messenger de Facebook — STUB INTENCIONAL.

No hay una API oficial que permita actuar como tu cuenta personal de
Messenger. Las dos rutas posibles:

1. Oficial: Meta Messenger Platform (https://developers.facebook.com/docs/messenger-platform/)
   — pero el remitente aparece como una Página, no como tú. Requiere
   MESSENGER_PAGE_ACCESS_TOKEN en .env. Es la única opción recomendable si
   este proyecto se convierte en producto (ver docs/PRODUCT_ROADMAP.md).

2. No oficial (ej. librerías tipo `fca-unofficial`): actúa como tu cuenta
   personal, pero con el mismo riesgo de baneo que WhatsApp no oficial —
   y sin un microservicio tan maduro/mantenido como Baileys.

Este archivo implementa la vía (1). Si decides la vía (2) para tu prototipo
personal, sigue el mismo patrón que whatsapp-bridge/ (microservicio Node
aislado) para poder reemplazarlo después sin tocar el orchestrator.
"""
from __future__ import annotations

import httpx

from orchestrator import contacts
from orchestrator.config import settings

GRAPH_API_URL = "https://graph.facebook.com/v19.0/me/messages"


async def enviar(destinatario_id: str, texto: str) -> dict:
    try:
        contacts.verificar_autorizado("messenger_id", destinatario_id)
    except contacts.ContactoNoAutorizado as e:
        return {"status": "rechazado", "motivo": str(e)}

    if not settings.messenger_page_access_token:
        return {
            "status": "no_configurado",
            "detalle": (
                "Falta MESSENGER_PAGE_ACCESS_TOKEN en .env. Lee el docstring "
                "de este archivo antes de configurarlo."
            ),
        }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            GRAPH_API_URL,
            params={"access_token": settings.messenger_page_access_token},
            json={"recipient": {"id": destinatario_id}, "message": {"text": texto}},
        )
        resp.raise_for_status()
        return resp.json()
