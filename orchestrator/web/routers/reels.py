"""Generación de reels vía formulario — no pasa por el chat/router, la
herramienta en /reels llama esto directo, es más rápido y más simple que
hacer que un LLM elija la tool correcta para algo que ya es un formulario.
`generar_reel` tarda 1-2 minutos (síntesis de voz + render), así que corre
en background (asyncio.to_thread, es código sync/bloqueante) y el
frontend hace polling del resultado.

Separado de app.py en la modularización de 2026-09-19."""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from orchestrator.tools import reel_generator, reels_defaults
from orchestrator.web import state
from orchestrator.web.deps import sesion_actual
from orchestrator.web.paginas import pagina_protegida

log = logging.getLogger("orchestrator.web")
router = APIRouter()


class ReelGenerarPayload(BaseModel):
    producto: str  # clave de reels_defaults.PRODUCTOS: "taskdoctor" | "rive"
    nombre_salida: str
    beats: list[dict] | None = None  # si no viene, usa el guion aprobado del producto
    proveedor_voz: str | None = None  # None = usa el default de reels_defaults
    voz_id: str | None = None


def _ruta_absoluta_reel(ruta_relativa: str) -> Path:
    return reel_generator.REPO_ROOT / ruta_relativa


async def _correr_generacion_reel(job_id: str, payload: ReelGenerarPayload) -> None:
    try:
        info_producto = reels_defaults.PRODUCTOS.get(payload.producto)
        beats = payload.beats or (info_producto or {}).get("guion")
        if not beats:
            state.trabajos_reels[job_id] = {
                "status": "error",
                "detalle": (
                    f"No hay guion aprobado para '{payload.producto}' — "
                    "pasá 'beats' en el pedido o elegí un producto que ya tenga uno."
                ),
            }
            return
        tema = (info_producto or {}).get("tema", payload.producto)
        proveedor_voz, voz_id = reels_defaults.resolver_voz(payload.proveedor_voz, payload.voz_id)

        resultado = await asyncio.to_thread(
            reel_generator.generar_reel,
            beats,
            payload.nombre_salida,
            tema=tema,
            proveedor_voz=proveedor_voz,
            voz_id=voz_id,
        )

        if resultado.get("status") == "generado":
            carpeta_drive = os.getenv("GOOGLE_DRIVE_REELS_FOLDER_ID", "")
            if carpeta_drive:
                try:
                    from orchestrator.tools.google_workspace import subir_a_drive

                    ruta_abs = _ruta_absoluta_reel(resultado["ruta"])
                    resultado["drive"] = await asyncio.to_thread(subir_a_drive, str(ruta_abs), carpeta_drive)
                except Exception as exc:  # nunca tirar el trabajo entero por el paso de Drive
                    log.warning("No se pudo subir el reel a Drive: %s", exc)
                    resultado["drive"] = {"status": "error", "detalle": str(exc)}
            state.trabajos_reels[job_id] = {"status": "listo", "resultado": resultado}
        else:
            state.trabajos_reels[job_id] = {"status": "error", "detalle": resultado.get("detalle", "Error desconocido.")}
    except Exception as exc:
        log.exception("Fallo generando reel (job %s)", job_id)
        state.trabajos_reels[job_id] = {"status": "error", "detalle": str(exc)}


@router.get("/reels")
async def pagina_reels(request: Request):
    """Herramienta dedicada para generar reels (no el chat) — mismo login
    que "/", misma cookie de sesión."""
    return pagina_protegida(request, "reels.html")


@router.post("/api/reels/generar")
async def reels_generar(payload: ReelGenerarPayload, request: Request):
    sesion_actual(request)  # exige sesión — no valida nada del payload en sí
    job_id = str(uuid.uuid4())
    state.trabajos_reels[job_id] = {"status": "en_progreso", "iniciado": datetime.now(timezone.utc).isoformat()}
    asyncio.create_task(_correr_generacion_reel(job_id, payload))
    return {"job_id": job_id}


@router.get("/api/reels/estado/{job_id}")
async def reels_estado(job_id: str, request: Request):
    sesion_actual(request)
    trabajo = state.trabajos_reels.get(job_id)
    if trabajo is None:
        raise HTTPException(status_code=404, detail="job_id desconocido.")
    return trabajo


@router.get("/api/reels/video/{job_id}")
async def reels_video(job_id: str, request: Request):
    sesion_actual(request)
    trabajo = state.trabajos_reels.get(job_id)
    if trabajo is None or trabajo.get("status") != "listo":
        raise HTTPException(status_code=404, detail="Todavía no hay video listo para este job_id.")
    ruta = _ruta_absoluta_reel(trabajo["resultado"]["ruta"])
    if not ruta.exists():
        raise HTTPException(status_code=404, detail="El archivo ya no existe en el servidor.")
    return FileResponse(ruta, media_type="video/mp4", filename=ruta.name)


@router.get("/api/reels/productos")
async def reels_productos(request: Request):
    """Metadata de cada producto (tema, url_fuente, si ya tiene guion
    aprobado) — el frontend la usa para armar el selector sin hardcodear
    nada de reels_defaults.py en el HTML."""
    sesion_actual(request)
    return {
        nombre: {
            "tema": datos["tema"],
            "url_fuente": datos["url_fuente"],
            "tiene_guion": datos["guion"] is not None,
            "beats": datos["guion"],
        }
        for nombre, datos in reels_defaults.PRODUCTOS.items()
    }
