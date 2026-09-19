"""Chat con los agentes — el endpoint reutiliza el mismo enrutador y los
mismos agentes que `orchestrator/main.py` (agregar un agente nuevo sigue
sin tocar nada acá, igual que en la versión de terminal). Única diferencia
real con main.py: cuando un agente pide una tool irreversible, esto NO
bloquea esperando input() por terminal — devuelve de inmediato
`confirmacion_pendiente` y pausa el turno hasta que llegue la respuesta a
POST /api/chat/confirmar.

Separado de app.py en la modularización de 2026-09-19."""
from __future__ import annotations

import inspect
import json
import logging
import uuid

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from orchestrator import contacts
from orchestrator.agents import AGENTES, Agent_0
from orchestrator.agents.base import system_prompt_con_fecha
from orchestrator.config import settings
from orchestrator.router import elegir_agente
from orchestrator.web import state
from orchestrator.web.deps import sesion_actual

log = logging.getLogger("orchestrator.web")
router = APIRouter()


class ChatPayload(BaseModel):
    mensaje: str
    agente_id: str | None = None  # None = deja que el enrutador (Haiku) elija, como antes


class ConfirmarPayload(BaseModel):
    pendiente_id: str
    confirmar: bool
    pin: str | None = None


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
    ids_de_esta_sesion = [pid for pid, p in state.pendientes.items() if p["sesion_id"] == sesion_id]
    for pendiente_id in ids_de_esta_sesion:
        pendiente = state.pendientes.pop(pendiente_id)
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
        clave = state.clave_conversacion(sesion_id, pendiente["agente_id"])
        state.conversaciones.setdefault(clave, []).append({"role": "user", "content": resultados})


@router.get("/api/agentes")
async def listar_agentes(request: Request):
    """Para el panel lateral — el frontend arma la lista de agentes
    seleccionables con esto en vez de tenerlos hardcodeados en el HTML."""
    sesion_actual(request)
    return [
        {"id": a.id, "nombre": a.nombre, "descripcion": a.descripcion_enrutador, "predeterminado": a.es_predeterminado}
        for a in AGENTES.values()
    ]


@router.post("/api/chat")
async def chat(payload: ChatPayload, request: Request):
    sesion = sesion_actual(request)
    sesion_id = sesion["correo"]  # una conversación por invitado (y por agente, ver state.clave_conversacion)

    if payload.agente_id:
        if payload.agente_id not in AGENTES:
            raise HTTPException(status_code=400, detail=f"Agente desconocido: {payload.agente_id!r}")
        agente = AGENTES[payload.agente_id]
    else:
        # Compatibilidad hacia atrás: sin agente_id, se comporta como
        # siempre — el enrutador (Haiku) elige según el mensaje.
        agente = await elegir_agente(payload.mensaje, AGENTES)

    _cancelar_pendientes_de_sesion(sesion_id)
    mensajes = state.conversaciones.setdefault(state.clave_conversacion(sesion_id, agente.id), [])
    mensajes.append({"role": "user", "content": payload.mensaje})

    return await _correr_turno_web(sesion_id, agente, mensajes)


@router.post("/api/chat/confirmar")
async def confirmar(payload: ConfirmarPayload, request: Request):
    sesion = sesion_actual(request)
    pendiente = state.pendientes.pop(payload.pendiente_id, None)
    if pendiente is None or pendiente["sesion_id"] != sesion["correo"]:
        raise HTTPException(status_code=404, detail="No hay ninguna confirmación pendiente con ese id")

    sesion_id = pendiente["sesion_id"]
    agente = AGENTES[pendiente["agente_id"]]
    mensajes = state.conversaciones[state.clave_conversacion(sesion_id, agente.id)]

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
        respuesta = await state.client.messages.create(
            model=settings.anthropic_model,
            max_tokens=state.MAX_TOKENS,
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
            pin_requerido = contacts.generar_pin_confirmacion() if primera.name in state.TOOLS_CON_PIN else None
            state.pendientes[pendiente_id] = {
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
