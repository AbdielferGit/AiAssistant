"""
Registro de agentes — se arma solo, escaneando esta carpeta cada vez que
arranca el orchestrator. No hace falta editar este archivo para agregar un
agente nuevo: basta con crear un `.py` en `orchestrator/agents/` que
instancie `Agent_0` (ver `base.py`) — el escaneo lo encuentra solo.
"""
from __future__ import annotations

import importlib
import logging
import pkgutil

from orchestrator.agents.base import Agent_0

log = logging.getLogger("orchestrator.agents")

_MODULOS_EXCLUIDOS = {"base"}


def _descubrir_agentes() -> dict[str, Agent_0]:
    encontrados: dict[str, Agent_0] = {}
    for info in pkgutil.iter_modules(__path__):
        if info.name in _MODULOS_EXCLUIDOS:
            continue
        modulo = importlib.import_module(f"{__name__}.{info.name}")
        for valor in vars(modulo).values():
            if not isinstance(valor, Agent_0):
                continue
            if valor.id in encontrados:
                log.warning(
                    "Id de agente duplicado %r (definido en %s) — se ignora, "
                    "ya había un agente registrado con ese id.",
                    valor.id, info.name,
                )
                continue
            encontrados[valor.id] = valor
    return encontrados


AGENTES: dict[str, Agent_0] = _descubrir_agentes()


def agente_predeterminado() -> Agent_0:
    """El agente al que cae el enrutador cuando ninguno especializado
    encaja con el mensaje. Se elige por `es_predeterminado=True`; si nadie
    lo marcó, se usa el primero que se haya registrado (y se avisa)."""
    for agente in AGENTES.values():
        if agente.es_predeterminado:
            return agente
    primero = next(iter(AGENTES.values()))
    log.warning(
        "Ningún agente tiene es_predeterminado=True — usando %r como "
        "agente por defecto. Márcalo explícitamente para evitar sorpresas.",
        primero.id,
    )
    return primero
