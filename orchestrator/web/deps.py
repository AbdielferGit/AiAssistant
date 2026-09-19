"""Dependencias de FastAPI compartidas entre routers — hoy solo la
verificación de sesión, pero es el lugar donde agregar cualquier otra
(rate limiting, etc.) sin duplicarla en cada router."""
from __future__ import annotations

from fastapi import HTTPException, Request

from orchestrator.web import auth


def sesion_actual(request: Request) -> dict:
    sesion = auth.leer_sesion(request.cookies.get(auth.COOKIE_NAME))
    if sesion is None:
        raise HTTPException(status_code=401, detail="No autenticado")
    return sesion
