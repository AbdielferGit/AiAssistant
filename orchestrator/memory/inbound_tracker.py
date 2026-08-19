"""
Rastrea cuándo fue el último mensaje entrante de cada contacto.

La WhatsApp Cloud API (número de prueba oficial de Meta) solo permite texto
libre iniciado por ti dentro de una ventana de 24 h desde que ese contacto
te escribió por última vez; fuera de esa ventana se necesita una plantilla
pre-aprobada. `orchestrator/tools/whatsapp_cloud_api.py` usa este módulo
para decidir si un envío libre es válido o hay que avisarte que falta esa
ventana.

Guardado como JSON simple — es un dato efímero y de bajo volumen, no
necesita LanceDB/Postgres.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from orchestrator.config import settings

VENTANA = timedelta(hours=24)


def _ruta() -> Path:
    ruta = Path(settings.inbound_tracker_path)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    return ruta


def _leer() -> dict[str, str]:
    ruta = _ruta()
    if not ruta.exists():
        return {}
    return json.loads(ruta.read_text(encoding="utf-8") or "{}")


def registrar_inbound(numero: str) -> None:
    datos = _leer()
    datos[numero] = datetime.now(timezone.utc).isoformat()
    _ruta().write_text(json.dumps(datos, indent=2), encoding="utf-8")


def dentro_de_ventana_24h(numero: str) -> bool:
    datos = _leer()
    marca = datos.get(numero)
    if not marca:
        return False
    ultimo = datetime.fromisoformat(marca)
    return datetime.now(timezone.utc) - ultimo < VENTANA
