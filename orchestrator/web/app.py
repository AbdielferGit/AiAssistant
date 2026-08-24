"""
App web de AiAssistant — versión de acceso remoto, solo por invitación.

Sirve tres cosas:
  1. Login (Google Sign-In) restringido a `orchestrator/web/invites.py` —
     ver `orchestrator/web/auth.py`.
  2. Un endpoint de chat que REUTILIZA el mismo enrutador y los mismos
     agentes que `orchestrator/main.py` (`orchestrator/router.py`,
     `orchestrator/agents/`) — agregar un agente nuevo sigue sin tocar
     nada aquí, exactamente como en la versión de terminal.
  3. El reemplazo web del `input()` bloqueante de main.py para acciones
     irreversibles: en vez de esperar en una terminal, el turno se PAUSA
     y devuelve `confirmacion_pendiente` al frontend, que muestra un
     modal de confirmar/cancelar; la conversación continúa cuando el
     usuario responde vía POST /api/chat/confirmar. Este es el único
     punto donde el flujo diverge de main.py — todo lo demás (enrutado,
     ejecución de tools, historial) es el mismo código.

Para desplegar esto en Bluehost (Phusion Passenger) ver `passenger_wsgi.py`
en la raíz del repo y `docs/DEPLOY_BLUEHOST.md`.
"""
from __future__ import annotations

import inspect
import json
import logging
import uuid
from pathlib import Path

import anthropic
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from orchestrator.agents import AGENTES, Agent_0
from orchestrator.agents.base import system_prompt_con_fecha
from orchestrator.config import settings
from orchestrator.router import elegir_agente
from orchestrator.web import auth

log = logging.getLogger("orchestrator.web")
app = FastAPI(title="AiAssistant web")

_STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

MAX_TOKENS = 1536

# --- Estado en memoria, por invitado -------------------------------------
# Suficiente para el uso personal / por-invitación de hoy (unos pocos
# usuarios a la vez, un proceso). Si esto crece de verdad, la migración es
# de infraestructura (mover a Redis/SQLite), no de diseño: las funciones de
# abajo son el único lugar que tocaría.
_conversaciones: dict[str, list[dict]] = {}
_pendientes: dict[str, dict] = {}


class LoginPayload(BaseModel):
    credential: str


class ChatPayload(BaseModel):
    mensaje: str


class ConfirmarPayload(BaseModel):
    pendiente_id: str
    confirmar: bool


def _sesion_actual(request: Request) -> dict:
    sesion = auth.leer_sesion(request.cookies.get(auth.COOKIE_NAME))
    if sesion is None:
        raise HTTPException(status_code=401, detail="No autenticado")
    return sesion


@app.get("/")
async def index(request: Request):
    if auth.leer_sesion(request.cookies.get(auth.COOKIE_NAME)) is None:
        html = (_STATIC_DIR / "login.html").read_text(encoding="utf-8")
        html = html.replace("__GOOGLE_CLIENT_ID__", settings.google_client_id)
        return HTMLResponse(html)
    return FileResponse(_STATIC_DIR / "index.html")


@app.post("/auth/google")
async def auth_google(payload: LoginPayload):
    try:
        sesion = auth.verificar_credential_google(payload.credential)
    except auth.LoginRechazado as exc:
        log.warning("Login rechazado: %s", exc)
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Token de Google inválido: {exc}")

    resp = JSONResponse({"status": "ok", "nombre": sesion["nombre"]})
    resp.set_cookie(
        auth.COOKIE_NAME,
        auth.crear_cookie_sesion(sesion),
        max_age=auth.SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=True,
    )
    return resp


@app.post("/auth/logout")
async def logout():
    resp = JSONResponse({"status": "ok"})
    resp.delete_cookie(auth.COOKIE_NAME)
    return resp


@app.get("/api/whoami")
async def whoami(request: Request):
    return _sesion_actual(request)


@app.post("/api/chat")
async def chat(payload: ChatPayload, request: Request):
    sesion = _sesion_actual(request)
    sesion_id = sesion["correo"]  # una conversación por invitado — simple y suficiente hoy
    mensajes = _conversaciones.setdefault(sesion_id, [])
    mensajes.append({"role": "user", "content": payload.mensaje})

    agente = await elegir_agente(payload.mensaje, AGENTES)
    return await _correr_turno_web(sesion_id, agente, mensajes)


@app.post("/api/chat/confirmar")
async def confirmar(payload: ConfirmarPayload, request: Request):
    sesion = _sesion_actual(request)
    pendiente = _pendientes.pop(payload.pendiente_id, None)
    if pendiente is None or pendiente["sesion_id"] != sesion["correo"]:
        raise HTTPException(status_code=404, detail="No hay ninguna confirmación pendiente con ese id")

    sesion_id = pendiente["sesion_id"]
    mensajes = _conversaciones[sesion_id]
    agente = AGENTES[pendiente["agente_id"]]

    if payload.confirmar:
        resultado = await _ejecutar_tool_web(agente, pendiente["nombre"], pendiente["args"])
    else:
        resultado = {"status": "cancelado_por_usuario"}

    resultados = list(pendiente.get("resultados_previos", []))
    resultados.append(
        {
            "type": "tool_result",
            "tool_use_id": pendiente["tool_use_id"],
            "content": json.dumps(resultado, ensure_ascii=False),
        }
    )
    mensajes.append({"role": "user", "content": resultados})
    return await _correr_turno_web(sesion_id, agente, mensajes)


async def _ejecutar_tool_web(agente: Agent_0, nombre: str, args: dict) -> dict:
    func = agente.tool_funcs.get(nombre)
    if func is None:
        return {"status": "error", "detalle": f"Tool desconocida: {nombre}"}
    resultado = func(**args)
    if inspect.isawaitable(resultado):
        resultado = await resultado
    return resultado


async def _correr_turno_web(sesion_id: str, agente: Agent_0, mensajes: list[dict]) -> dict:
    """Equivalente web de `_correr_turno` en orchestrator/main.py. Única
    diferencia real: cuando el agente pide una tool irreversible, esta
    función NO bloquea esperando input() por terminal — devuelve de
    inmediato `confirmacion_pendiente` y pausa el turno hasta que llegue la
    respuesta a POST /api/chat/confirmar."""
    while True:
        respuesta = await _client.messages.create(
            model=settings.anthropic_model,
            max_tokens=MAX_TOKENS,
            system=system_prompt_con_fecha(agente),
            tools=agente.tool_schemas,
            messages=mensajes,
        )
        mensajes.append({"role": "assistant", "content": respuesta.content})
        texto = " ".join(b.text for b in respuesta.content if b.type == "text").strip()

        llamadas = [b for b in respuesta.content if b.type == "tool_use"]
        if not llamadas:
            return {"agente": agente.nombre, "texto": texto, "confirmacion_pendiente": None}

        resultados = []
        irreversibles_pendientes = []
        for llamada in llamadas:
            if llamada.name in agente.tools_irreversibles:
                irreversibles_pendientes.append(llamada)
                continue
            resultado = await _ejecutar_tool_web(agente, llamada.name, llamada.input)
            resultados.append(
                {
                    "type": "tool_result",
                    "tool_use_id": llamada.id,
                    "content": json.dumps(resultado, ensure_ascii=False),
                }
            )

        if irreversibles_pendientes:
            # Solo pausamos en UNA acción irreversible a la vez. Si el
            # agente pidiera dos en el mismo turno (raro en la práctica),
            # la Messages API igual exige un tool_result para cada
            # tool_use del bloque, así que las demás se cancelan
            # explícitamente aquí en vez de quedar sin resolver.
            primera, *resto = irreversibles_pendientes
            for extra in resto:
                resultados.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": extra.id,
                        "content": json.dumps(
                            {
                                "status": "cancelado_automaticamente",
                                "detalle": "Solo se puede confirmar una acción irreversible a la vez.",
                            },
                            ensure_ascii=False,
                        ),
                    }
                )

            pendiente_id = str(uuid.uuid4())
            _pendientes[pendiente_id] = {
                "sesion_id": sesion_id,
                "agente_id": agente.id,
                "nombre": primera.name,
                "args": primera.input,
                "tool_use_id": primera.id,
                "resultados_previos": resultados,
            }
            confirmacion_pendiente = {
                "pendiente_id": pendiente_id,
                "tool": primera.name,
                "args": primera.input,
            }
            return {"agente": agente.nombre, "texto": texto, "confirmacion_pendiente": confirmacion_pendiente}

        mensajes.append({"role": "user", "content": resultados})
