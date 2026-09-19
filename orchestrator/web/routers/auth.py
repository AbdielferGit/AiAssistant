"""Login (Google Sign-In) y la página principal del chat. Separado de
app.py en la modularización de 2026-09-19."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from orchestrator.web import auth as auth_service
from orchestrator.web.deps import sesion_actual
from orchestrator.web.paginas import pagina_protegida

log = logging.getLogger("orchestrator.web")
router = APIRouter()


class LoginPayload(BaseModel):
    credential: str


@router.get("/")
async def index(request: Request):
    return pagina_protegida(request, "index.html")


@router.post("/auth/google")
async def auth_google(payload: LoginPayload):
    try:
        sesion = auth_service.verificar_credential_google(payload.credential)
    except auth_service.LoginRechazado as exc:
        log.warning("Login rechazado: %s", exc)
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Token de Google inválido: {exc}")

    resp = JSONResponse({"status": "ok", "nombre": sesion["nombre"]})
    resp.set_cookie(
        auth_service.COOKIE_NAME,
        auth_service.crear_cookie_sesion(sesion),
        max_age=auth_service.SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=True,
    )
    return resp


@router.post("/auth/logout")
async def logout():
    resp = JSONResponse({"status": "ok"})
    resp.delete_cookie(auth_service.COOKIE_NAME)
    return resp


@router.get("/api/whoami")
async def whoami(request: Request):
    return sesion_actual(request)
