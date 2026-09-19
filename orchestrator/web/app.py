"""
App web de AiAssistant — versión de acceso remoto, solo por invitación.

Sirve cuatro dominios, cada uno en su propio router
(orchestrator/web/routers/) — este archivo solo arma la app FastAPI y los
monta:

  1. `routers/auth.py` — Login (Google Sign-In, restringido a
     `orchestrator/web/invites.py` — ver `orchestrator/web/auth.py`) y la
     página principal del chat.
  2. `routers/chat.py` — El endpoint de chat, que REUTILIZA el mismo
     enrutador y los mismos agentes que `orchestrator/main.py`
     (`orchestrator/router.py`, `orchestrator/agents/`) — agregar un
     agente nuevo sigue sin tocar nada acá, exactamente como en la
     versión de terminal. Incluye el reemplazo web del `input()`
     bloqueante de main.py para acciones irreversibles: en vez de esperar
     en una terminal, el turno se PAUSA y devuelve `confirmacion_pendiente`
     al frontend, que muestra un modal de confirmar/cancelar; la
     conversación continúa cuando el usuario responde vía
     POST /api/chat/confirmar. Este es el único punto donde el flujo
     diverge de main.py — todo lo demás (enrutado, ejecución de tools,
     historial) es el mismo código.
  3. `routers/reels.py` — Generación de reels vía formulario (no pasa por
     el chat).
  4. `routers/leads.py` — Waitlist de TaskDoctor (Meta Pixel + Conversions
     API) — pública, sin login. OJO (2026-09-19): la landing real
     (riveintelligente.ca/taskdoctor) YA NO le pega a esto — se decidió
     que RiveIntelligente y AiAssistant vivan como repos completamente
     separados, sin que uno dependa del despliegue del otro. Esa landing
     ahora usa su propio Apps Script (crm/apps-script-taskdoctor/ en el
     repo RiveIntelligente). Esta ruta/módulo se deja intacta y funcional
     a propósito — no se desarmó, solo quedó desconectada — por si en
     algún momento hace falta un backend real para esto de nuevo.

El estado compartido entre routers (conversaciones, trabajos en curso, el
cliente de Anthropic) vive en `orchestrator/web/state.py`; la verificación
de sesión, en `orchestrator/web/deps.py`.

Para desplegar esto en Bluehost (Phusion Passenger) ver `passenger_wsgi.py`
en la raíz del repo y `docs/DEPLOY_BLUEHOST.md`.

Modularizado el 2026-09-19 (antes: un solo archivo de 556 líneas
mezclando los cuatro dominios de arriba)."""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from orchestrator.web.routers import auth, chat, leads, reels
from orchestrator.web.state import STATIC_DIR

log = logging.getLogger("orchestrator.web")
app = FastAPI(title="AiAssistant web")

# Sin CORSMiddleware a propósito (2026-09-19): existía solo para que
# riveintelligente.ca pudiera llamar a /api/leads/* desde el navegador —
# esa conexión ya no existe (ver nota en routers/leads.py y el docstring
# de arriba). Si en el futuro algo vuelve a necesitar llamar a esta API
# desde otro origen, agregar CORSMiddleware de nuevo scopeado a ese caso
# puntual, no dejarlo abierto "por si acaso".

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.exception_handler(Exception)
async def _manejar_error_no_previsto(request: Request, exc: Exception) -> JSONResponse:
    """Sin esto, cualquier excepción no capturada (ej. RuntimeError de
    google_workspace por falta de credenciales, un timeout de la API de
    Anthropic, lo que sea) hace que FastAPI/Starlette devuelva una
    respuesta de error genérica que NO es JSON — y el frontend, que espera
    poder hacer response.json(), revienta con una excepción propia y
    termina mostrando 'Error de red' sin ninguna pista real de qué pasó.
    Con este handler, el cliente siempre recibe {"detail": "..."} — un
    mensaje que sí se puede leer y mostrar."""
    log.exception("Error no previsto en %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": f"{type(exc).__name__}: {exc}"})


app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(reels.router)
app.include_router(leads.router)
