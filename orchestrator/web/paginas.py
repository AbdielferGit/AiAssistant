"""Sirve una página estática protegida por sesión — mismo patrón repetido
antes en `/` y `/reels` de app.py (login-gate + reemplazo de
__GOOGLE_CLIENT_ID__), ahora en un solo lugar."""
from __future__ import annotations

from fastapi import Request
from fastapi.responses import FileResponse, HTMLResponse

from orchestrator.config import settings
from orchestrator.web import auth
from orchestrator.web.state import STATIC_DIR


def pagina_protegida(request: Request, nombre_archivo: str):
    """Si no hay sesión válida, sirve login.html (con el client id de
    Google inyectado); si la hay, sirve `nombre_archivo` tal cual."""
    if auth.leer_sesion(request.cookies.get(auth.COOKIE_NAME)) is None:
        html = (STATIC_DIR / "login.html").read_text(encoding="utf-8")
        html = html.replace("__GOOGLE_CLIENT_ID__", settings.google_client_id)
        return HTMLResponse(html)
    return FileResponse(STATIC_DIR / nombre_archivo)
