"""Autoriza (o reautoriza) el acceso a Gmail/Calendar/Drive, sin pasar por
el chat completo del asistente — solo abre el navegador, pedís permiso, y
listo. Escribe/actualiza token.json en la raíz del repo.

Uso:
    python scripts/reautorizar_google.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from orchestrator.tools.google_workspace import _get_credentials


def main() -> None:
    print("Abriendo el navegador para autorizar con Google...")
    creds = _get_credentials()
    if creds and creds.valid:
        print("¡Listo! token.json quedó creado/actualizado en la raíz del repo.")
    else:
        print("Algo no salió bien — no se obtuvieron credenciales válidas.")


if __name__ == "__main__":
    main()
