"""
Lista blanca de invitados a la versión web de AiAssistant.

Separada de `orchestrator/contacts.py` a propósito: contacts.py autoriza A
QUIÉN puede el asistente enviarle o recibir mensajes (WhatsApp, email,
Messenger...); este módulo autoriza QUIÉN puede iniciar sesión y usar el
chat web. Son dos listas de control de acceso distintas aunque compartan
el mismo patrón: un YAML no versionado, con plantilla `.example`, releído
en cada verificación (para que agregar/quitar un invitado tenga efecto
inmediato sin reiniciar el servidor).

Fuente: config/invited_users.yaml (no versionado, PII).
Plantilla: config/invited_users.yaml.example.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "invited_users.yaml"


@dataclass(frozen=True)
class Invitado:
    correo: str
    nombre: str
    activo: bool


def _listar() -> list[Invitado]:
    if not CONFIG_PATH.exists():
        raise RuntimeError(
            f"No existe {CONFIG_PATH}. Copia config/invited_users.yaml.example "
            f"a config/invited_users.yaml y agrega ahí los correos autorizados "
            f"a iniciar sesión antes de exponer la web."
        )
    datos = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    return [
        Invitado(
            correo=(i.get("correo") or "").strip().lower(),
            nombre=i.get("nombre", ""),
            activo=bool(i.get("activo", False)),
        )
        for i in datos.get("invitados", [])
    ]


def esta_invitado(correo: str) -> Invitado | None:
    """Devuelve el Invitado si `correo` está activo en la lista; None si no
    está invitado o está desactivado. Nunca lanza por un correo desconocido
    — un login rechazado es el camino normal, no un error del sistema."""
    correo = (correo or "").strip().lower()
    for invitado in _listar():
        if invitado.activo and invitado.correo == correo:
            return invitado
    return None
