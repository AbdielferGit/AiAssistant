"""
Respalda la carpeta local de datos (LanceDB + cualquier SQLite) a la
carpeta de Google Drive configurada en GOOGLE_DRIVE_DB_FOLDER_ID.

Uso:
    python scripts/sync_to_drive.py

Pensado para correr como cron/systemd timer periódico en el VPS (ej. cada
hora). Ver docs/PRODUCT_ROADMAP.md sobre por qué esto es respaldo, no la
base de datos "en vivo", del sistema.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from orchestrator.config import settings
from orchestrator.tools.google_workspace import subir_a_drive


def main() -> None:
    if not settings.google_drive_db_folder_id:
        raise SystemExit("Falta GOOGLE_DRIVE_DB_FOLDER_ID en .env")

    carpeta_datos = Path(settings.vector_db_path).parent
    if not carpeta_datos.exists():
        raise SystemExit(f"No existe {carpeta_datos} todavía — corre el orchestrator primero.")

    archivos = [p for p in carpeta_datos.rglob("*") if p.is_file()]
    for archivo in archivos:
        resultado = subir_a_drive(str(archivo), settings.google_drive_db_folder_id)
        print(f"{archivo.name}: {resultado}")


if __name__ == "__main__":
    main()
