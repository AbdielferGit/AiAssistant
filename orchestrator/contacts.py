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

# Deliberadamente NO hay una lista fija de canales/medios válidos: cada
# contacto define en config/contacts.yaml los medios de comunicación que
# tengan sentido para él (whatsapp, email, messenger_id, imessage, o
# cualquier medio nuevo que agregues después — sms, telegram, slack...) sin
# tener que tocar este archivo ni el resto del código. Un tool de canal
# (orchestrator/tools/*.py) solo sabe actuar sobre los medios para los que
# existe una implementación; los demás quedan guardados en el contacto,
# listos para cuando construyas ese tool.
_PARECE_TELEFONO = re.compile(r"\+?\d{7,15}")


class ContactoNoAutorizado(Exception):
    """Se intentó enviar o procesar un mensaje con alguien fuera de la lista blanca."""


@dataclass(frozen=True)
class Contacto:
    nombre: str
    alias: str
    activo: bool
    canales: dict[str, str]


def _normalizar(canal: str, identificador: str) -> str:
    """Normaliza por FORMA del valor, no por el nombre del canal — así
    cualquier medio nuevo (sms, telegram, lo que sea) se normaliza bien sin
    tener que enseñarle a esta función el nombre de cada canal nuevo."""
    identificador = (identificador or "").strip()
    solo_digitos_y_mas = re.sub(r"[^\d+]", "", identificador)
    if _PARECE_TELEFONO.fullmatch(solo_digitos_y_mas):
        # "+52 123 456 7890" y "+521234567890" se tratan como lo mismo.
        return solo_digitos_y_mas
    # correos, @usuarios, IDs de app, etc.
    return identificador.lower()


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
        # Cualquier clave bajo "canales" cuenta — no hay lista fija, así
        # puedes agregar medios progresivamente sin tocar código.
        canal_map = {k: v for k, v in (c.get("canales") or {}).items() if v}
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
