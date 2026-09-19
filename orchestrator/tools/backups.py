"""Backup de un repo a Google Drive — un .zip fechado del código fuente,
sin dependencias instaladas ni artefactos de build, subido a una carpeta
de Drive fija ("Backups de código").

Por qué esto existe además de GitHub: GitHub ya es la fuente de verdad y
el historial completo — esto es una copia adicional, legible por
cualquiera con acceso a la carpeta de Drive (no todos tienen o necesitan
una cuenta de GitHub), y sobrevive un incidente en la cuenta de GitHub
misma. No reemplaza a `git`, lo complementa."""
from __future__ import annotations

import fnmatch
import logging
import tempfile
import time
import zipfile
from pathlib import Path

log = logging.getLogger("orchestrator.tools.backups")

# Directorios/patrones que nunca deben ir en un backup de CÓDIGO FUENTE —
# o porque son reconstruibles (node_modules, .next, dependencias) o porque
# son secretos que jamás deben salir del repo local (.env real, token.json).
# El .git se excluye a propósito: GitHub ya es el historial completo, este
# zip es una instantánea del árbol de trabajo, no un segundo remoto de git.
EXCLUIR_SIEMPRE = {
    ".git", "node_modules", ".next", ".vinext", ".wrangler", ".venv",
    "__pycache__", ".pytest_cache", "dist", "build", ".turbo",
}
EXCLUIR_PATRONES = ("*.pyc", ".DS_Store", "*.env", ".env.*", "!*.env.example", "*.tsbuildinfo")


def _debe_excluirse(ruta_relativa: Path) -> bool:
    partes = ruta_relativa.parts
    if any(parte in EXCLUIR_SIEMPRE for parte in partes):
        return True
    nombre = ruta_relativa.name
    if nombre == ".env.example":
        return False  # es plantilla pública, sin secretos — sí se respalda
    for patron in EXCLUIR_PATRONES:
        if patron.startswith("!"):
            continue
        if fnmatch.fnmatch(nombre, patron):
            return True
    return False


def crear_zip_repo(ruta_repo: str, incluir_out: bool = True) -> Path:
    """Arma un .zip del árbol de trabajo actual (no del historial de git)
    de `ruta_repo` en un archivo temporal, listo para subir. `incluir_out`
    controla si se incluye una carpeta `out/` (build estático ya generado,
    como en RiveIntelligente) — por defecto sí, porque para un sitio
    desplegado vía "Deploy HEAD Commit" de cPanel esa carpeta ES parte de
    lo que está realmente en producción, no un artefacto descartable."""
    repo = Path(ruta_repo).resolve()
    if not repo.is_dir():
        raise RuntimeError(f"No existe el directorio: {repo}")

    exclusiones = set(EXCLUIR_SIEMPRE)
    if not incluir_out:
        exclusiones.add("out")

    nombre_zip = f"{repo.name}_{time.strftime('%Y%m%d_%H%M%S')}.zip"
    destino = Path(tempfile.gettempdir()) / nombre_zip

    archivos_incluidos = 0
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as zf:
        for ruta in repo.rglob("*"):
            if ruta.is_dir():
                continue
            relativa = ruta.relative_to(repo)
            if any(parte in exclusiones for parte in relativa.parts):
                continue
            if _debe_excluirse(relativa):
                log.warning("Excluido del backup (posible secreto/artefacto): %s", relativa)
                continue
            zf.write(ruta, arcname=str(Path(repo.name) / relativa))
            archivos_incluidos += 1

    log.info("Backup armado: %s (%d archivos)", destino, archivos_incluidos)
    return destino


def respaldar_repo_a_drive(ruta_repo: str, carpeta_drive: str = "Backups de código", incluir_out: bool = True) -> dict:
    """Arma el .zip (ver crear_zip_repo) y lo sube a Drive, en una carpeta
    que se busca o crea por nombre — no hace falta pegar ningún folder id
    a mano. Devuelve el resultado de la subida + cuántos archivos entraron."""
    from orchestrator.tools import google_workspace

    zip_path = crear_zip_repo(ruta_repo, incluir_out=incluir_out)
    try:
        carpeta_id = google_workspace.carpeta_drive_por_nombre(carpeta_drive)
        resultado = google_workspace.subir_a_drive(str(zip_path), carpeta_id)
    finally:
        zip_path.unlink(missing_ok=True)  # no dejamos el zip tirado en /tmp

    resultado["nombre_archivo"] = zip_path.name
    resultado["carpeta"] = carpeta_drive
    return resultado
