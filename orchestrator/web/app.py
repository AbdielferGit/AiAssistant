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

import asyncio
import inspect
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import anthropic
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from orchestrator import contacts
from orchestrator.agents import AGENTES, Agent_0
from orchestrator.agents.base import system_prompt_con_fecha
from orchestrator.config import settings
from orchestrator.router import elegir_agente
from orchestrator.tools import reel_generator, reels_defaults
from orchestrator.web import auth

# Tools irreversibles que, además del modal normal, exigen un PIN de un
# solo uso porque tocan la lista blanca misma (ver
# contacts.generar_pin_confirmacion). El PIN se genera aquí, en el
# servidor, y solo viaja al FRONTEND (para que el humano lo vea en el
# modal) — nunca se pone en un tool_result, así que el modelo no lo ve.
TOOLS_CON_PIN = {"agregar_contacto"}

log = logging.getLogger("orchestrator.web")
app = FastAPI(title="AiAssistant web")

_STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


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

_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

MAX_TOKENS = 1536

# --- Estado en memoria, por invitado -------------------------------------
# Suficiente para el uso personal / por-invitación de hoy (unos pocos
# usuarios a la vez, un proceso). Si esto crece de verdad, la migración es
# de infraestructura (mover a Redis/SQLite), no de diseño: las funciones de
# abajo son el único lugar que tocaría.
_conversaciones: dict[str, list[dict]] = {}
_pendientes: dict[str, dict] = {}

# Trabajos de generación de reels — en memoria, igual que lo de arriba
# (mismo comentario aplica: si esto crece, migrar a algo persistente).
# Un trabajo pasa por "en_progreso" -> "listo" | "error".
_trabajos_reels: dict[str, dict] = {}


class LoginPayload(BaseModel):
    credential: str


class ChatPayload(BaseModel):
    mensaje: str
    agente_id: str | None = None  # None = deja que el enrutador (Haiku) elija, como antes


class ConfirmarPayload(BaseModel):
    pendiente_id: str
    confirmar: bool
    pin: str | None = None


class ReelGenerarPayload(BaseModel):
    producto: str  # clave de reels_defaults.PRODUCTOS: "aiassistant" | "taskdoctor" | "rive"
    nombre_salida: str
    beats: list[dict] | None = None  # si no viene, usa el guion aprobado del producto
    proveedor_voz: str | None = None  # None = usa el default de reels_defaults
    voz_id: str | None = None


def _clave_conversacion(sesion_id: str, agente_id: str) -> str:
    """Cada (invitado, agente) tiene su propio historial — así el panel
    lateral puede tener una conversación por agente sin que se mezclen."""
    return f"{sesion_id}::{agente_id}"


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


@app.get("/reels")
async def pagina_reels(request: Request):
    """Herramienta dedicada para generar reels (no el chat) — mismo login
    que "/", misma cookie de sesión."""
    if auth.leer_sesion(request.cookies.get(auth.COOKIE_NAME)) is None:
        html = (_STATIC_DIR / "login.html").read_text(encoding="utf-8")
        html = html.replace("__GOOGLE_CLIENT_ID__", settings.google_client_id)
        return HTMLResponse(html)
    return FileResponse(_STATIC_DIR / "reels.html")


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


def _cancelar_pendientes_de_sesion(sesion_id: str) -> None:
    """Si el usuario abandona una confirmación pendiente — manda un mensaje
    nuevo en vez de responder al modal, recarga la página, lo que sea — y
    nunca la cerramos, el `tool_use` que quedó a medias en el historial
    hace que CUALQUIER llamada futura a la API de Anthropic falle con 400
    ('tool_use ids were found without tool_result blocks') — visto en
    producción. Esa sesión queda rota hasta que el proceso se reinicia
    (lo único que la 'arreglaba' antes era un redeploy que limpiaba la
    memoria). Se llama al principio de /api/chat para garantizar que el
    historial siempre esté en un estado válido antes de la próxima
    llamada — nunca dejar un tool_use sin su tool_result."""
    ids_de_esta_sesion = [pid for pid, p in _pendientes.items() if p["sesion_id"] == sesion_id]
    for pendiente_id in ids_de_esta_sesion:
        pendiente = _pendientes.pop(pendiente_id)
        resultados = list(pendiente.get("resultados_previos", []))
        resultados.append(
            {
                "type": "tool_result",
                "tool_use_id": pendiente["tool_use_id"],
                "content": json.dumps(
                    {
                        "status": "cancelado_automaticamente",
                        "detalle": (
                            "El usuario envió un mensaje nuevo sin responder "
                            "a la confirmación pendiente."
                        ),
                    },
                    ensure_ascii=False,
                ),
            }
        )
        clave = _clave_conversacion(sesion_id, pendiente["agente_id"])
        _conversaciones.setdefault(clave, []).append({"role": "user", "content": resultados})


@app.get("/api/agentes")
async def listar_agentes(request: Request):
    """Para el panel lateral — el frontend arma la lista de agentes
    seleccionables con esto en vez de tenerlos hardcodeados en el HTML."""
    _sesion_actual(request)
    return [
        {"id": a.id, "nombre": a.nombre, "descripcion": a.descripcion_enrutador, "predeterminado": a.es_predeterminado}
        for a in AGENTES.values()
    ]


@app.post("/api/chat")
async def chat(payload: ChatPayload, request: Request):
    sesion = _sesion_actual(request)
    sesion_id = sesion["correo"]  # una conversación por invitado (y por agente, ver _clave_conversacion)

    if payload.agente_id:
        if payload.agente_id not in AGENTES:
            raise HTTPException(status_code=400, detail=f"Agente desconocido: {payload.agente_id!r}")
        agente = AGENTES[payload.agente_id]
    else:
        # Compatibilidad hacia atrás: sin agente_id, se comporta como
        # siempre — el enrutador (Haiku) elige según el mensaje.
        agente = await elegir_agente(payload.mensaje, AGENTES)

    _cancelar_pendientes_de_sesion(sesion_id)
    mensajes = _conversaciones.setdefault(_clave_conversacion(sesion_id, agente.id), [])
    mensajes.append({"role": "user", "content": payload.mensaje})

    return await _correr_turno_web(sesion_id, agente, mensajes)


@app.post("/api/chat/confirmar")
async def confirmar(payload: ConfirmarPayload, request: Request):
    sesion = _sesion_actual(request)
    pendiente = _pendientes.pop(payload.pendiente_id, None)
    if pendiente is None or pendiente["sesion_id"] != sesion["correo"]:
        raise HTTPException(status_code=404, detail="No hay ninguna confirmación pendiente con ese id")

    sesion_id = pendiente["sesion_id"]
    agente = AGENTES[pendiente["agente_id"]]
    mensajes = _conversaciones[_clave_conversacion(sesion_id, agente.id)]

    confirmar = payload.confirmar
    if confirmar and pendiente.get("pin_requerido") and payload.pin != pendiente["pin_requerido"]:
        # PIN incorrecto (o no lo mandó) — se trata igual que un "no", nunca
        # se ejecuta la tool. No distinguimos el motivo en la respuesta para
        # no darle a un atacante pistas de si el PIN estuvo cerca.
        confirmar = False

    if confirmar:
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
    """Nunca lanza. Una tool que revienta (credenciales rotas, timeout de
    red, lo que sea) DEBE volver como un dict {"status": "error", ...} en
    vez de propagar la excepción: si se propaga, el tool_use del asistente
    ya quedó guardado en el historial persistido (se agregó ANTES de
    ejecutar la tool) y esta función nunca llega a agregar su tool_result
    — la sesión queda con un tool_use sin resolver para siempre (hasta el
    próximo reinicio del proceso), y CUALQUIER mensaje futuro de esa
    sesión falla con el mismo 400 de la API de Anthropic. Visto en
    producción con crear_evento_calendario mientras GOOGLE_TOKEN_JSON
    tenía un valor inválido."""
    func = agente.tool_funcs.get(nombre)
    if func is None:
        return {"status": "error", "detalle": f"Tool desconocida: {nombre}"}
    try:
        resultado = func(**args)
        if inspect.isawaitable(resultado):
            resultado = await resultado
        return resultado
    except Exception as exc:
        log.exception("Tool %s(%s) falló", nombre, args)
        return {"status": "error", "detalle": f"{type(exc).__name__}: {exc}"}


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
            pin_requerido = contacts.generar_pin_confirmacion() if primera.name in TOOLS_CON_PIN else None
            _pendientes[pendiente_id] = {
                "sesion_id": sesion_id,
                "agente_id": agente.id,
                "nombre": primera.name,
                "args": primera.input,
                "tool_use_id": primera.id,
                "resultados_previos": resultados,
                "pin_requerido": pin_requerido,
            }
            confirmacion_pendiente = {
                "pendiente_id": pendiente_id,
                "tool": primera.name,
                "args": primera.input,
                "pin_requerido": pin_requerido,
            }
            return {"agente": agente.nombre, "texto": texto, "confirmacion_pendiente": confirmacion_pendiente}

        mensajes.append({"role": "user", "content": resultados})


# --- generación de reels ----------------------------------------------------
# No pasa por el chat/router — la herramienta en /reels llama esto directo,
# es más rápido y más simple que hacer que un LLM elija la tool correcta
# para algo que ya es un formulario. `generar_reel` tarda 1-2 minutos
# (síntesis de voz + render), así que corre en background (asyncio.to_thread,
# es código sync/bloqueante) y el frontend hace polling del resultado.

def _ruta_absoluta_reel(ruta_relativa: str) -> Path:
    return reel_generator.REPO_ROOT / ruta_relativa


async def _correr_generacion_reel(job_id: str, payload: ReelGenerarPayload) -> None:
    try:
        info_producto = reels_defaults.PRODUCTOS.get(payload.producto)
        beats = payload.beats or (info_producto or {}).get("guion")
        if not beats:
            _trabajos_reels[job_id] = {
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
            _trabajos_reels[job_id] = {"status": "listo", "resultado": resultado}
        else:
            _trabajos_reels[job_id] = {"status": "error", "detalle": resultado.get("detalle", "Error desconocido.")}
    except Exception as exc:
        log.exception("Fallo generando reel (job %s)", job_id)
        _trabajos_reels[job_id] = {"status": "error", "detalle": str(exc)}


@app.post("/api/reels/generar")
async def reels_generar(payload: ReelGenerarPayload, request: Request):
    _sesion_actual(request)  # exige sesión — no valida nada del payload en sí
    job_id = str(uuid.uuid4())
    _trabajos_reels[job_id] = {"status": "en_progreso", "iniciado": datetime.now(timezone.utc).isoformat()}
    asyncio.create_task(_correr_generacion_reel(job_id, payload))
    return {"job_id": job_id}


@app.get("/api/reels/estado/{job_id}")
async def reels_estado(job_id: str, request: Request):
    _sesion_actual(request)
    trabajo = _trabajos_reels.get(job_id)
    if trabajo is None:
        raise HTTPException(status_code=404, detail="job_id desconocido.")
    return trabajo


@app.get("/api/reels/video/{job_id}")
async def reels_video(job_id: str, request: Request):
    _sesion_actual(request)
    trabajo = _trabajos_reels.get(job_id)
    if trabajo is None or trabajo.get("status") != "listo":
        raise HTTPException(status_code=404, detail="Todavía no hay video listo para este job_id.")
    ruta = _ruta_absoluta_reel(trabajo["resultado"]["ruta"])
    if not ruta.exists():
        raise HTTPException(status_code=404, detail="El archivo ya no existe en el servidor.")
    return FileResponse(ruta, media_type="video/mp4", filename=ruta.name)


@app.get("/api/reels/productos")
async def reels_productos(request: Request):
    """Metadata de cada producto (tema, url_fuente, si ya tiene guion
    aprobado) — el frontend la usa para armar el selector sin hardcodear
    nada de reels_defaults.py en el HTML."""
    _sesion_actual(request)
    return {
        nombre: {
            "tema": datos["tema"],
            "url_fuente": datos["url_fuente"],
            "tiene_guion": datos["guion"] is not None,
            "beats": datos["guion"],
        }
        for nombre, datos in reels_defaults.PRODUCTOS.items()
    }
