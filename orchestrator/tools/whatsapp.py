"""
Punto único que el orchestrator usa para "enviar_whatsapp" — despacha al
proveedor configurado (WHATSAPP_PROVIDER) sin duplicar la verificación de
lista blanca, que se hace aquí una sola vez para ambos proveedores:

- "cloud_api" (por defecto): WhatsApp Cloud API oficial de Meta — sin QR,
  sin riesgo de baneo, pero con la ventana de 24h de tools/whatsapp_cloud_api.py.
  Recomendado mientras pruebas con el "número de prueba" gratuito.
- "baileys": puente no oficial (whatsapp-bridge/, Node) atado a tu WhatsApp
  personal vía QR. Ver docs/ARCHITECTURE.md para el riesgo antes de activarlo.
"""
from __future__ import annotations

import httpx

from orchestrator import contacts
from orchestrator.config import settings


async def enviar(numero: str, texto: str) -> dict:
    """numero en formato internacional, ej. '+521234567890'."""
    try:
        contacto = contacts.verificar_autorizado("whatsapp", numero)
    except contacts.ContactoNoAutorizado as e:
        return {"status": "rechazado", "motivo": str(e)}

    if settings.whatsapp_provider == "cloud_api":
        from orchestrator.tools import whatsapp_cloud_api

        resultado = await whatsapp_cloud_api.enviar(numero, texto)
    elif settings.whatsapp_provider == "baileys":
        resultado = await _enviar_via_baileys(numero, texto)
    else:
        return {
            "status": "error",
            "detalle": f"WHATSAPP_PROVIDER={settings.whatsapp_provider!r} no reconocido "
            f"(usa 'cloud_api' o 'baileys').",
        }

    return {**resultado, "contacto": contacto.nombre}


async def _enviar_via_baileys(numero: str, texto: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{settings.whatsapp_bridge_url}/send",
            headers={"Authorization": f"Bearer {settings.whatsapp_bridge_token}"},
            json={"numero": numero, "texto": texto},
        )
        resp.raise_for_status()
        return resp.json()


async def estado_conexion() -> dict:
    """Solo aplica al proveedor 'baileys' (whatsapp-bridge expone /status)."""
    if settings.whatsapp_provider != "baileys":
        return {"status": "no_aplica", "proveedor": settings.whatsapp_provider}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{settings.whatsapp_bridge_url}/status",
            headers={"Authorization": f"Bearer {settings.whatsapp_bridge_token}"},
        )
        resp.raise_for_status()
        return resp.json()
