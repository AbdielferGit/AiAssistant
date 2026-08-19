"""Acciones locales en macOS: abrir apps/archivos, correr AppleScripts."""
from __future__ import annotations

import subprocess
from pathlib import Path

from orchestrator import contacts

APPLESCRIPTS_DIR = Path(__file__).resolve().parents[2] / "mac-bridge" / "scripts" / "applescript"


def abrir(nombre: str) -> dict:
    """Abre una app o archivo por nombre, ej. 'Calendar' o '~/Documents/plan.pdf'."""
    resultado = subprocess.run(["open", "-a", nombre], capture_output=True, text=True)
    if resultado.returncode != 0:
        # Puede que "nombre" sea una ruta de archivo, no una app.
        resultado = subprocess.run(["open", nombre], capture_output=True, text=True)
    return {
        "status": "abierto" if resultado.returncode == 0 else "error",
        "detalle": resultado.stderr.strip() or "ok",
    }


def correr_applescript(nombre_archivo: str, *args: str) -> dict:
    """Ejecuta un .applescript de mac-bridge/scripts/applescript/ con osascript."""
    ruta = APPLESCRIPTS_DIR / nombre_archivo
    if not ruta.exists():
        return {"status": "error", "detalle": f"No existe {ruta}"}
    resultado = subprocess.run(["osascript", str(ruta), *args], capture_output=True, text=True)
    return {
        "status": "ok" if resultado.returncode == 0 else "error",
        "salida": resultado.stdout.strip(),
        "error": resultado.stderr.strip(),
    }


def enviar_imessage(numero_o_correo: str, texto: str) -> dict:
    """Rechaza el envío si `numero_o_correo` no está en la lista blanca
    activa (config/contacts.yaml) — ver orchestrator/contacts.py."""
    try:
        contacto = contacts.verificar_autorizado("imessage", numero_o_correo)
    except contacts.ContactoNoAutorizado as e:
        return {"status": "rechazado", "motivo": str(e)}
    resultado = correr_applescript("send_imessage.applescript", texto, numero_o_correo)
    return {**resultado, "contacto": contacto.nombre}
