"""
Lista blanca de contactos — única fuente de verdad de autorización.

Ningún tool de canal (whatsapp.py, google_workspace.py, messenger.py,
macos_actions.py) puede enviar un mensaje sin pasar por
`verificar_autorizado()` primero. Lo mismo aplica del lado de recepción:
`orchestrator/webhooks/whatsapp_cloud.py` descarta cualquier mensaje
entrante de alguien que no esté aquí. Es decir: la
autorización se exige en las DOS direcciones, no solo al enviar.

Fuente de datos, en orden de prioridad (ver _leer_yaml_crudo):
1. config/contacts.yaml en disco (no versionado, contiene PII; plantilla:
   contacts.yaml.example) — la fuente normal en tu Mac.
2. Google Drive (carpeta 'AiAssistant-DB', archivo 'contacts.yaml' —
   buscados/creados por nombre, sin ningún ID que configurar a mano). Es
   la fuente en hostings sin disco persistente (ej. Render free tier)
   cuando agregar_contacto ya se usó desde ahí al menos una vez. Se
   cachea 20s en memoria (ver _CACHE_TTL_SEGUNDOS) para no pegarle a la
   API de Drive en cada mensaje.
3. La variable de entorno CONTACTS_YAML, con el mismo YAML como texto
   plano (se define a mano en el panel del hosting) — patrón anterior,
   sigue funcionando como último respaldo si Drive no está disponible.

El archivo local (opción 1), si existe, NUNCA se cachea: cada
verificación lo relee, así que editarlo a mano (o con
scripts/manage_contacts.py) tiene efecto inmediato sin reiniciar el
orchestrator. Drive sí se cachea porque es una llamada de red.
"""
from __future__ import annotations

import logging
import os
import re
import secrets
import time
from dataclasses import dataclass
from pathlib import Path

import yaml

log = logging.getLogger("orchestrator.contacts")

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


_DRIVE_CARPETA = "AiAssistant-DB"
_DRIVE_ARCHIVO = "contacts.yaml"
_CACHE_TTL_SEGUNDOS = 20  # Drive es una llamada de red; sin esto, cada
# verificar_autorizado() de cada mensaje pegaría a la API en hostings sin
# disco. 20s es corto a propósito: un contacto agregado por chat queda
# usable casi de inmediato (además, agregar_contacto invalida el caché).
_cache_drive: dict = {"contenido": None, "expira": 0.0}


def _leer_yaml_crudo() -> str:
    """Prioridad: archivo local (tu Mac) > Drive (hostings sin disco, con
    caché corto) > variable de entorno CONTACTS_YAML (compatibilidad con
    el patrón anterior, ej. si Drive no está disponible)."""
    if CONFIG_PATH.exists():
        return CONFIG_PATH.read_text(encoding="utf-8")

    if _cache_drive["contenido"] is not None and _cache_drive["expira"] > time.time():
        return _cache_drive["contenido"]

    from orchestrator.tools import google_workspace

    try:
        contenido = google_workspace.leer_texto_drive(_DRIVE_ARCHIVO, _DRIVE_CARPETA)
    except Exception:
        contenido = None
    if contenido is not None:
        _cache_drive["contenido"] = contenido
        _cache_drive["expira"] = time.time() + _CACHE_TTL_SEGUNDOS
        return contenido

    contenido = os.getenv("CONTACTS_YAML", "")
    if contenido:
        return contenido

    raise RuntimeError(
        f"No existe {CONFIG_PATH}, no hay contacts.yaml en Drive todavía "
        f"(carpeta '{_DRIVE_CARPETA}'), y tampoco está definida la variable "
        f"de entorno CONTACTS_YAML. Copia config/contacts.yaml.example a "
        f"config/contacts.yaml, o agrega tu primer contacto por chat "
        f"(agregar_contacto crea el archivo en Drive solo)."
    )


def listar_todos() -> list[Contacto]:
    datos = yaml.safe_load(_leer_yaml_crudo()) or {}
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


def generar_pin_confirmacion() -> str:
    """PIN de 6 dígitos criptográficamente aleatorio para confirmar
    `agregar_contacto`. Lo genera SIEMPRE el código que maneja la
    confirmación de acciones irreversibles (main.py / web/app.py), nunca
    la tool en sí — así el modelo nunca lo ve en un tool_result, solo el
    humano lo ve (impreso en la terminal, o en el modal de la web). Sin
    esta separación el PIN no protegería nada: si el modelo lo viera,
    podría reenviárselo a sí mismo en el siguiente turno sin que ningún
    humano haya confirmado nada de verdad."""
    return f"{secrets.randbelow(1_000_000):06d}"


def agregar_contacto(nombre: str, alias: str, medios: dict[str, str]) -> dict:
    """Agrega un contacto nuevo. SOLO debe llamarse después de que
    main.py/web/app.py ya verificaron el PIN de confirmación (ver
    generar_pin_confirmacion) — esta función en sí no vuelve a pedirlo,
    confía en que el llamador ya lo hizo.

    Dónde queda guardado:
    - Si config/contacts.yaml existe en disco (tu Mac): se escribe ahí
      directo, Y ADEMÁS se sincroniza a Drive (carpeta 'AiAssistant-DB')
      si hay credenciales de Google disponibles, para que la web vea el
      mismo contacto sin pasos manuales. Si esa sincronización falla (sin
      red, sin token, lo que sea) no se considera un error — el contacto
      ya quedó guardado localmente, que es la fuente de verdad en tu Mac.
    - Si NO hay archivo local (ej. Render free tier, sin disco
      persistente): se guarda directo en Drive. Sin Drive disponible ahí,
      no hay dónde persistir — falla con un error claro."""
    datos = yaml.safe_load(_leer_yaml_crudo()) or {}
    datos.setdefault("contactos", [])
    if any(c.get("alias") == alias for c in datos["contactos"]):
        raise ValueError(f"Ya existe un contacto con alias '{alias}'. Usa otro alias.")

    datos["contactos"].append({"nombre": nombre, "alias": alias, "activo": True, "canales": medios})
    nuevo_yaml = yaml.safe_dump(datos, allow_unicode=True, sort_keys=False)

    if CONFIG_PATH.exists():
        CONFIG_PATH.write_text(nuevo_yaml, encoding="utf-8")
        try:
            from orchestrator.tools import google_workspace

            google_workspace.escribir_texto_drive(_DRIVE_ARCHIVO, nuevo_yaml, _DRIVE_CARPETA)
        except Exception as exc:
            log.warning(
                "Se agregó el contacto localmente pero no se pudo sincronizar a Drive "
                "(la web puede tardar en verlo hasta que se sincronice): %s", exc,
            )
    else:
        from orchestrator.tools import google_workspace

        google_workspace.escribir_texto_drive(_DRIVE_ARCHIVO, nuevo_yaml, _DRIVE_CARPETA)

    _cache_drive["contenido"] = nuevo_yaml
    _cache_drive["expira"] = time.time() + _CACHE_TTL_SEGUNDOS
    return {"status": "agregado", "nombre": nombre, "alias": alias, "medios": medios}
