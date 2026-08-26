"""
Chatbot local — loop principal por terminal, agnóstico al agente.

Usa el SDK oficial de Anthropic (`anthropic`) con un loop de tool-use
manual, en vez del Claude Agent SDK (ese depende de tener instalado el CLI
de Claude Code como subproceso — no queremos esa dependencia en un
contenedor corriendo en un VPS).

Este archivo no sabe nada de un agente en particular. Por defecto, ANTES
de responder cada mensaje consulta al enrutador (`orchestrator/router.py`)
para decidir cuál de los agentes registrados en `orchestrator/agents/`
debe atenderlo — y solo cae en el agente genérico (el marcado como
predeterminado) cuando ninguno especializado encaja. Agregar un agente
nuevo no requiere tocar este archivo: ver `orchestrator/agents/base.py`.

Uso (siempre como módulo, desde la raíz del repo — `python orchestrator/main.py`
directo NO funciona: Python no agrega la raíz del repo a sys.path cuando
corres un script suelto, solo la carpeta que lo contiene):
    python -m orchestrator.main                  # enruta cada turno automáticamente
    python -m orchestrator.main --agente ceo      # fija un agente para toda la sesión (sin enrutar)
    python -m orchestrator.main --listar-agentes
"""
from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import logging

import anthropic

from orchestrator.agents import AGENTES, Agent_0
from orchestrator.agents.base import system_prompt_con_fecha
from orchestrator.config import settings
from orchestrator.router import elegir_agente

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("orchestrator")

MAX_TOKENS = 1536


async def _ejecutar_tool(agente: Agent_0, nombre: str, args: dict) -> dict:
    if nombre in agente.tools_irreversibles:
        print(f"\n⚠️  El agente quiere ejecutar una acción IRREVERSIBLE:")
        print(f"    {nombre}({json.dumps(args, ensure_ascii=False, indent=2)})")
        respuesta = await asyncio.to_thread(input, "¿Confirmas? (sí/no): ")
        if respuesta.strip().lower() not in ("si", "sí", "s", "yes", "y"):
            return {"status": "cancelado_por_usuario"}

    func = agente.tool_funcs.get(nombre)
    if func is None:
        return {"status": "error", "detalle": f"Tool desconocida: {nombre}"}

    try:
        resultado = func(**args)
        if inspect.isawaitable(resultado):
            resultado = await resultado
        return resultado
    except Exception as exc:
        # Igual que en orchestrator/web/app.py: si esto propaga, el
        # tool_use ya quedado en `mensajes` se queda sin su tool_result y
        # revienta cada turno futuro de esta sesión de terminal.
        log.exception("Tool %s(%s) falló", nombre, args)
        return {"status": "error", "detalle": f"{type(exc).__name__}: {exc}"}


async def _correr_turno(client: anthropic.AsyncAnthropic, agente: Agent_0, mensajes: list[dict]) -> None:
    """Corre el loop de tool-use de UN turno con el agente elegido, hasta
    que responda solo con texto (sin más tool_use pendientes). Modifica
    `mensajes` in-place para que el historial se comparta entre agentes."""
    while True:
        respuesta = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=MAX_TOKENS,
            system=system_prompt_con_fecha(agente),
            tools=agente.tool_schemas,
            messages=mensajes,
        )
        mensajes.append({"role": "assistant", "content": respuesta.content})

        texto = " ".join(b.text for b in respuesta.content if b.type == "text").strip()
        if texto:
            print(f"\n{agente.nombre}: {texto}\n")

        llamadas = [b for b in respuesta.content if b.type == "tool_use"]
        if not llamadas:
            return

        resultados = []
        for llamada in llamadas:
            log.info("Ejecutando tool %s(%s)", llamada.name, llamada.input)
            resultado = await _ejecutar_tool(agente, llamada.name, llamada.input)
            resultados.append(
                {
                    "type": "tool_result",
                    "tool_use_id": llamada.id,
                    "content": json.dumps(resultado, ensure_ascii=False),
                }
            )
        mensajes.append({"role": "user", "content": resultados})


async def run(agente_fijo: Agent_0 | None) -> None:
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    mensajes: list[dict] = []

    if agente_fijo:
        print(f"[{agente_fijo.nombre}] listo (fijo, sin enrutar). Ctrl+C para salir.\n")
    else:
        print(
            f"Listo — enruto cada mensaje al agente que le toque "
            f"({', '.join(a.nombre for a in AGENTES.values())}). Ctrl+C para salir.\n"
        )

    while True:
        try:
            texto_usuario = await asyncio.to_thread(input, "Tú: ")
        except (EOFError, KeyboardInterrupt):
            print("\nHasta luego.")
            return
        texto_usuario = texto_usuario.strip()
        if not texto_usuario:
            continue

        mensajes.append({"role": "user", "content": texto_usuario})

        if agente_fijo:
            agente = agente_fijo
        else:
            agente = await elegir_agente(texto_usuario, AGENTES)
            print(f"[enrutado a: {agente.nombre}]")

        await _correr_turno(client, agente, mensajes)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--agente", default=None, choices=sorted(AGENTES),
        help="Fija un agente para toda la sesión (se salta el enrutador). Por defecto: enruta cada mensaje.",
    )
    parser.add_argument(
        "--listar-agentes", action="store_true",
        help="Muestra los agentes disponibles y sale.",
    )
    args = parser.parse_args()

    if args.listar_agentes:
        for id_, agente in AGENTES.items():
            predeterminado = " (predeterminado)" if agente.es_predeterminado else ""
            print(f"{id_}: {agente.nombre}{predeterminado}")
        return

    agente_fijo = AGENTES[args.agente] if args.agente else None
    asyncio.run(run(agente_fijo))


if __name__ == "__main__":
    main()
