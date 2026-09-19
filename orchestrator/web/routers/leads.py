"""Waitlist de TaskDoctor (para Meta Ads) — pública, SIN login.

DESCONECTADO desde 2026-09-19: la landing real (riveintelligente.ca/
taskdoctor) usaba esto, pero se decidió que RiveIntelligente y AiAssistant
vivan como repos separados, sin que uno dependa del otro estando
desplegado — ahora esa landing usa su propio Apps Script
(crm/apps-script-taskdoctor/ en el repo RiveIntelligente, mismo patrón que
sus otros 2 formularios). Este router se deja intacto y funcional a
propósito (no se desarmó) por si hace falta un backend real para algo así
de nuevo — ver orchestrator/tools/leads.py para el resto del porqué
(taskdoctor.ai no es nuestro, no podíamos instalarle el Pixel/Conversions
API ahí directamente).

Separado de app.py en la modularización de 2026-09-19."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from orchestrator.config import settings
from orchestrator.tools import leads as leads_service
from orchestrator.web.state import STATIC_DIR

router = APIRouter()


class LeadPayload(BaseModel):
    """Ver orchestrator/tools/leads.py — pública, sin login: la llena
    gente que nunca usó el chat, viniendo de un anuncio."""
    email: str
    event_id: str  # generado en el navegador (lp_taskdoctor.html) — dedup con el fbq() del cliente
    urgency: str | None = None
    fbp: str | None = None  # cookie _fbp que pone el propio Pixel de Meta
    fbc: str | None = None  # cookie _fbc (solo existe si vino de un clic de anuncio con fbclid)
    website: str | None = None  # campo señuelo (honeypot) — un humano lo deja vacío siempre


@router.get("/leads/taskdoctor")
async def lp_taskdoctor():
    return FileResponse(STATIC_DIR / "lp_taskdoctor.html")


@router.get("/api/leads/config")
async def leads_config():
    """Pública a propósito: el Pixel ID de Meta NO es un secreto (viaja
    siempre visible en el JS de cualquier sitio con Meta Pixel) — solo el
    access_token de la Conversions API lo es, y ese nunca sale del
    servidor. Si META_PIXEL_ID no está en .env, el frontend simplemente no
    inicializa el Pixel (no rompe el formulario)."""
    return {"pixel_id": settings.meta_pixel_id or None}


@router.post("/api/leads/taskdoctor")
async def leads_taskdoctor(payload: LeadPayload, request: Request):
    try:
        resultado = leads_service.registrar_lead_taskdoctor(
            email=payload.email,
            event_id=payload.event_id,
            event_source_url=str(request.base_url) + "leads/taskdoctor",
            urgency=payload.urgency,
            client_ip=request.client.host if request.client else None,
            client_user_agent=request.headers.get("user-agent"),
            fbp=payload.fbp,
            fbc=payload.fbc,
            pixel_id=settings.meta_pixel_id or None,
            access_token=settings.meta_capi_access_token or None,
            honeypot=payload.website,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return resultado
