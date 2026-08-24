"""
Lista blanca de invitados a la versión web de AiAssistant.

Separada de `orchestrator/contacts.py` a propósito: contacts.py autoriza A
QUIÉN puede el asistente enviarle o recibir mensajes (WhatsApp, email,
Messenger...); este módulo autoriza QUIÉN puede iniciar sesión y usar el
chat web. Son dos listas de control de acceso distintas aunque compartan
el mismo patrón: un YAML no versionado, con plantilla `.example`, releído
en cada verificación (para que agregar/quitar un invitado tenga efecto
inmediato sin reiniciar el servidor).

Fuente: config/invited_users.yaml (no versionado, PII). Plantilla:
config/invited_users.yaml.example. En hostings sin disco persistente (ej.
el free tier de Render) no hay forma de "colocar" ese archivo en el
servidor tras el deploy — para esos casos, si el archivo no existe se cae
a la variable de entorno INVITED_USERS_YAML, que debe contener el mismo
YAML como texto plano (se define en el panel del hosting, no en el repo).
"""
from __future__ import annotations

import os
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
    if CONFIG_PATH.exists():
        contenido = CONFIG_PATH.read_text(encoding="utf-8")
    else:
        contenido = os.getenv("INVITED_USERS_YAML", "")
        if not contenido:
            raise RuntimeError(
                f"No existe {CONFIG_PATH} y tampoco está definida la variable "
                f"de entorno INVITED_USERS_YAML. Copia config/invited_users.yaml.example "
                f"a config/invited_users.yaml (o define INVITED_USERS_YAML con el "
                f"mismo contenido en el panel del hosting) antes de exponer la web."
            )
    datos = yaml.safe_load(contenido) or {}
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
