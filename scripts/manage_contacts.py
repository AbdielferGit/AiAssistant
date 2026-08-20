"""
CLI para administrar config/contacts.yaml — la lista blanca que autoriza
comunicación (en ambas direcciones) por cualquier medio: WhatsApp, email,
Messenger, iMessage, o cualquier medio nuevo que definas.

Los medios de comunicación son libres: se definen al crear el contacto y
se pueden agregar progresivamente después, sin tocar código — solo un
tool de canal (orchestrator/tools/*.py) necesita existir para que el
asistente pueda realmente USAR ese medio; mientras tanto el dato queda
guardado en el contacto.

Uso:
    python scripts/manage_contacts.py listar

    python scripts/manage_contacts.py agregar --nombre "Juan Pérez" --alias juan \\
        --medio whatsapp=+521234567890 --medio email=juan@correo.com

    # Agregar un medio nuevo a un contacto que ya existe:
    python scripts/manage_contacts.py agregar-medio --alias juan --medio telegram=@juanp

    # Quitar un medio de un contacto:
    python scripts/manage_contacts.py quitar-medio --alias juan --medio telegram

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


def _parsear_medios(pares: list[str] | None) -> dict[str, str]:
    """Convierte ["whatsapp=+521234567890", "email=juan@correo.com"] en un dict.
    Acepta cualquier nombre de medio — no hay lista fija."""
    medios: dict[str, str] = {}
    for par in pares or []:
        if "=" not in par:
            print(f"Formato inválido para --medio: '{par}' (usa medio=valor, ej. whatsapp=+521234567890)")
            sys.exit(1)
        nombre, valor = par.split("=", 1)
        medios[nombre.strip().lower()] = valor.strip()
    return medios


def _buscar_contacto(datos: dict, alias: str) -> dict:
    for c in datos.get("contactos", []):
        if c.get("alias") == alias:
            return c
    print(f"No se encontró ningún contacto con alias '{alias}'.")
    sys.exit(1)


def cmd_listar(_args: argparse.Namespace) -> None:
    datos = _cargar()
    if not datos.get("contactos"):
        print("(sin contactos todavía)")
        return
    for c in datos["contactos"]:
        estado = "activo" if c.get("activo") else "inactivo"
        canales = ", ".join(f"{k}={v}" for k, v in (c.get("canales") or {}).items() if v)
        print(f"- {c.get('nombre')} [{c.get('alias')}] ({estado}) — {canales or '(sin medios todavía)'}")


def cmd_agregar(args: argparse.Namespace) -> None:
    datos = _cargar()
    datos.setdefault("contactos", [])
    if any(c.get("alias") == args.alias for c in datos["contactos"]):
        print(f"Ya existe un contacto con alias '{args.alias}'. Usa otro alias.")
        sys.exit(1)
    medios = _parsear_medios(args.medio)
    if not medios:
        print("Advertencia: creaste el contacto sin ningún medio todavía. "
              "Agrégalos después con 'agregar-medio'.")
    datos["contactos"].append(
        {
            "nombre": args.nombre,
            "alias": args.alias,
            "activo": True,
            "canales": medios,
        }
    )
    _guardar(datos)
    print(f"Agregado: {args.nombre} [{args.alias}] — medios: {', '.join(medios) or '(ninguno)'}")


def cmd_agregar_medio(args: argparse.Namespace) -> None:
    datos = _cargar()
    contacto = _buscar_contacto(datos, args.alias)
    contacto.setdefault("canales", {})
    nuevos = _parsear_medios(args.medio)
    contacto["canales"].update(nuevos)
    _guardar(datos)
    print(f"{args.alias}: agregado(s) medio(s) {', '.join(nuevos)}")


def cmd_quitar_medio(args: argparse.Namespace) -> None:
    datos = _cargar()
    contacto = _buscar_contacto(datos, args.alias)
    canales = contacto.get("canales") or {}
    quitados = [m for m in args.medio if canales.pop(m, None) is not None]
    _guardar(datos)
    if quitados:
        print(f"{args.alias}: quitado(s) medio(s) {', '.join(quitados)}")
    else:
        print(f"{args.alias}: ninguno de esos medios estaba presente.")


def _cambiar_estado(alias: str, activo: bool) -> None:
    datos = _cargar()
    contacto = _buscar_contacto(datos, alias)
    contacto["activo"] = activo
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

    p_agregar = sub.add_parser("agregar", help="Crea un contacto nuevo, con medios opcionales desde ya")
    p_agregar.add_argument("--nombre", required=True)
    p_agregar.add_argument("--alias", required=True)
    p_agregar.add_argument(
        "--medio", action="append", metavar="medio=valor",
        help="Repite por cada medio, ej. --medio whatsapp=+521234567890 --medio email=juan@correo.com",
    )
    p_agregar.set_defaults(func=cmd_agregar)

    p_agregar_medio = sub.add_parser("agregar-medio", help="Agrega un medio nuevo a un contacto existente")
    p_agregar_medio.add_argument("--alias", required=True)
    p_agregar_medio.add_argument("--medio", action="append", required=True, metavar="medio=valor")
    p_agregar_medio.set_defaults(func=cmd_agregar_medio)

    p_quitar_medio = sub.add_parser("quitar-medio", help="Quita uno o más medios de un contacto existente")
    p_quitar_medio.add_argument("--alias", required=True)
    p_quitar_medio.add_argument("--medio", action="append", required=True, metavar="nombre_del_medio")
    p_quitar_medio.set_defaults(func=cmd_quitar_medio)

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
