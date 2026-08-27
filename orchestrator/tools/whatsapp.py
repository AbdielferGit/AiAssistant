"""
Punto único que el orchestrator usa para "enviar_whatsapp" — aplica la
lista blanca de contactos una sola vez y delega el envío a
`whatsapp_cloud_api.py` (WhatsApp Cloud API oficial de Meta).

Antes existía también un proveedor no oficial (Baileys, vía
whatsapp-bridge/, un puente Node atado a un WhatsApp personal por QR) —
se quitó al simplificar el proyecto: solo queda la vía oficial de Meta.
"""
from __future__ import annotations

from orchestrator import contacts
from orchestrator.tools import whatsapp_cloud_api


async def enviar(numero: str, texto: str) -> dict:
    """numero en formato internacional, ej. '+521234567890'."""
    try:
        contacto = contacts.verificar_autorizado("whatsapp", numero)
    except contacts.ContactoNoAutorizado as e:
        return {"status": "rechazado", "motivo": str(e)}

    resultado = await whatsapp_cloud_api.enviar(numero, texto)
    return {**resultado, "contacto": contacto.nombre}
