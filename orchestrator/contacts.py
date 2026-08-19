"""
Lista blanca de contactos — única fuente de verdad de autorización.

Ningún tool de canal (whatsapp.py, google_workspace.py, messenger.py,
macos_actions.py) puede enviar un mensaje sin pasar por
`verificar_autorizado()` primero. Lo mismo aplica del lado de recepción:
`orchestrator/bridge/server.py` (endpoint /inbound/{canal}) descarta
cualquier mensaje entrante de alguien que no esté aquí. Es decir: la
autorización se exige en las DOS direcciones, no solo al enviar.

Fuente de datos: config/contacts.yaml (no versionado, contiene PII).
Plantilla: config/contacts.yaml.example.

No se cachea en memoria a propósito: cada verificación relee el archivo,
así que editar config/contacts.yaml (a mano o con scripts/manage_contacts.py)
tiene efecto inmediato sin reiniciar el orchestrator.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "contacts.yaml"

CANALES_VALIDOS = {"whatsapp", "email", "messenger_id", "imessage"}


class ContactoNoAutorizado(Exception):
    """Se intentó enviar o procesar un mensaje con alguien fuera de la lista blanca."""


@dataclass(frozen=True)
class Contacto:
    nombre: str
    alias: str
    activo: bool
    canales: dict[str, str]


def _normalizar(canal: str, identificador: str) -> str:
    identificador = (identificador or "").strip()
    if canal == "email" or canal == "messenger_id":
        return identificador.lower()
    # whatsapp / imessage: solo dígitos y el '+' inicial, para que
    # "+52 123 456 7890" y "+521234567890" se traten como lo mismo.
    return re.sub(r"[^\d+]", "", identificador)


def listar_todos() -> list[Contacto]:
    if not CONFIG_PATH.exists():
        raise RuntimeError(
            f"No existe {CONFIG_PATH}. Copia config/contacts.yaml.example a "
            f"config/contacts.yaml y agrega ahí tus contactos autorizados "
            f"antes de enviar o procesar cualquier mensaje."
        )
    datos = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    contactos = []
    for c in datos.get("contactos", []):
        canal_map = {
            k: v for k, v in (c.get("canales") or {}).items() if k in CANALES_VALIDOS and v
        }
        contactos.append(
            Contacto(
                nombre=c.get("nombre", "(sin nombre)"),
                alias=c.get("alias", ""),
                activo=bool(c.get("activo", False)),
                canales=canal_map,
            )
        )
    return contactos


def _indice_activos() -> dict[tuple[str, str], Contacto]:
    indice: dict[tuple[str, str], Contacto] = {}
    for contacto in listar_todos():
        if not contacto.activo:
            continue
        for canal, identificador in contacto.canales.items():
            indice[(canal, _normalizar(canal, identificador))] = contacto
    return indice


def buscar_contacto(canal: str, identificador: str) -> Contacto | None:
    if canal not in CANALES_VALIDOS:
        return None
    return _indice_activos().get((canal, _normalizar(canal, identificador)))


def verificar_autorizado(canal: str, identificador: str) -> Contacto:
    """Lanza ContactoNoAutorizado si `identificador` no está en la lista
    blanca activa para `canal`. Llama esto ANTES de cualquier envío o de
    procesar un mensaje entrante — no lo trates como opcional."""
    contacto = buscar_contacto(canal, identificador)
    if contacto is None:
        raise ContactoNoAutorizado(
            f"'{identificador}' no está en la lista blanca de contactos "
            f"(canal={canal}). Agrégalo en config/contacts.yaml si es "
            f"legítimo (python scripts/manage_contacts.py agregar ...), o "
            f"trata esto como una señal de que algo intentó comunicarse "
            f"fuera de los contactos permitidos."
        )
    return contacto
