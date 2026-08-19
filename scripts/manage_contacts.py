"""
CLI para administrar config/contacts.yaml — la lista blanca que autoriza
comunicación (en ambas direcciones) por WhatsApp, email, Messenger e
iMessage. Ver orchestrator/contacts.py para cómo se aplica.

Uso:
    python scripts/manage_contacts.py listar
    python scripts/manage_contacts.py agregar --nombre "Juan Pérez" --alias juan \\
        --whatsapp "+521234567890" --email juan@correo.com
    python scripts/manage_contacts.py desactivar --alias juan
    python scripts/manage_contacts.py activar --alias juan
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "contacts.yaml"
EXAMPLE_PATH = CONFIG_PATH.with_suffix(".yaml.example")


def _cargar() -> dict:
    if not CONFIG_PATH.exists():
        print(f"No existe {CONFIG_PATH}, creándolo a partir de la plantilla vacía.")
        CONFIG_PATH.write_text("contactos: []\n", encoding="utf-8")
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {"contactos": []}


def _guardar(datos: dict) -> None:
    CONFIG_PATH.write_text(
        yaml.safe_dump(datos, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )


def cmd_listar(_args: argparse.Namespace) -> None:
    datos = _cargar()
    if not datos.get("contactos"):
        print("(sin contactos todavía)")
        return
    for c in datos["contactos"]:
        estado = "activo" if c.get("activo") else "inactivo"
        canales = ", ".join(f"{k}={v}" for k, v in (c.get("canales") or {}).items() if v)
        print(f"- {c.get('nombre')} [{c.get('alias')}] ({estado}) — {canales}")


def cmd_agregar(args: argparse.Namespace) -> None:
    datos = _cargar()
    datos.setdefault("contactos", [])
    if any(c.get("alias") == args.alias for c in datos["contactos"]):
        print(f"Ya existe un contacto con alias '{args.alias}'. Usa otro alias.")
        sys.exit(1)
    datos["contactos"].append(
        {
            "nombre": args.nombre,
            "alias": args.alias,
            "activo": True,
            "canales": {
                "whatsapp": args.whatsapp or "",
                "email": args.email or "",
                "messenger_id": args.messenger_id or "",
                "imessage": args.imessage or "",
            },
        }
    )
    _guardar(datos)
    print(f"Agregado: {args.nombre} [{args.alias}]")


def _cambiar_estado(alias: str, activo: bool) -> None:
    datos = _cargar()
    encontrado = False
    for c in datos.get("contactos", []):
        if c.get("alias") == alias:
            c["activo"] = activo
            encontrado = True
    if not encontrado:
        print(f"No se encontró ningún contacto con alias '{alias}'.")
        sys.exit(1)
    _guardar(datos)
    print(f"{alias}: activo={activo}")


def cmd_desactivar(args: argparse.Namespace) -> None:
    _cambiar_estado(args.alias, False)


def cmd_activar(args: argparse.Namespace) -> None:
    _cambiar_estado(args.alias, True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="comando", required=True)

    sub.add_parser("listar").set_defaults(func=cmd_listar)

    p_agregar = sub.add_parser("agregar")
    p_agregar.add_argument("--nombre", required=True)
    p_agregar.add_argument("--alias", required=True)
    p_agregar.add_argument("--whatsapp", default="")
    p_agregar.add_argument("--email", default="")
    p_agregar.add_argument("--messenger-id", dest="messenger_id", default="")
    p_agregar.add_argument("--imessage", default="")
    p_agregar.set_defaults(func=cmd_agregar)

    p_desactivar = sub.add_parser("desactivar")
    p_desactivar.add_argument("--alias", required=True)
    p_desactivar.set_defaults(func=cmd_desactivar)

    p_activar = sub.add_parser("activar")
    p_activar.add_argument("--alias", required=True)
    p_activar.set_defaults(func=cmd_activar)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    if not EXAMPLE_PATH.exists():
        print(f"Advertencia: no se encontró {EXAMPLE_PATH} (¿corres esto desde la raíz del repo?)")
    main()
