"""
Ingesta del historial de mensajes del usuario y búsqueda de ejemplos de
estilo para redactar borradores.

Flujo de ingesta (manual, una vez, y luego incremental):
1. Exportas tu chat de WhatsApp (Chat → ⋮ → Más → Exportar chat, sin medios)
   o tu carpeta "Enviados" de Gmail.
2. Corres `python -m orchestrator.memory.style_profile ingerir <archivo>`.
3. Cada mensaje se vectoriza y se guarda en LanceDB (vector_store.py).

La "capacidad de entrenamiento" de este asistente vive aquí: cada mensaje
nuevo que apruebas se puede volver a ingerir para que el estilo mejore con
el tiempo, sin reentrenar ningún modelo.
"""
from __future__ import annotations

import sys
from pathlib import Path

import anthropic

from orchestrator.config import settings
from orchestrator.memory.vector_store import Mensaje, agregar_mensajes, buscar_similares

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)


def _embed(textos: list[str]) -> list[list[float]]:
    """Genera embeddings para una lista de textos.

    NOTA: usa aquí el proveedor de embeddings que prefieras (Voyage AI es la
    integración recomendada por Anthropic, o un modelo local tipo
    sentence-transformers si quieres mantener todo 100% local/privado).
    Este stub asume una función `embed_batch` ya resuelta — reemplázala
    según el proveedor que elijas antes de la primera ingesta real.
    """
    raise NotImplementedError(
        "Configura tu proveedor de embeddings (ej. Voyage AI o "
        "sentence-transformers local) aquí antes de ingerir mensajes."
    )


def ingerir_export_whatsapp(ruta_archivo: str, destinatario: str) -> int:
    """Parsea un export de texto plano de WhatsApp (formato
    '[fecha, hora] Nombre: mensaje') y lo agrega al índice de estilo."""
    lineas = Path(ruta_archivo).read_text(encoding="utf-8").splitlines()
    mensajes: list[Mensaje] = []
    for linea in lineas:
        if ": " not in linea:
            continue
        _, texto = linea.split(": ", 1)
        texto = texto.strip()
        if not texto or texto.startswith("<Multimedia"):
            continue
        mensajes.append(
            Mensaje(texto=texto, destinatario=destinatario, canal="whatsapp", fecha="")
        )
    if not mensajes:
        return 0
    vectores = _embed([m["texto"] for m in mensajes])
    return agregar_mensajes(mensajes, vectores)


def buscar_ejemplos_de_estilo(destinatario: str, canal: str, k: int = 6) -> list[str]:
    """Usado por orchestrator/main.py (tool `redactar_borrador`) para traer
    ejemplos reales antes de generar un mensaje nuevo."""
    try:
        vector_consulta = _embed([f"mensaje para {destinatario} por {canal}"])[0]
    except NotImplementedError:
        return []
    resultados = buscar_similares(vector_consulta, destinatario=destinatario, canal=canal, k=k)
    return [r["texto"] for r in resultados]


if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[1] != "ingerir":
        print("Uso: python -m orchestrator.memory.style_profile ingerir <archivo.txt> <destinatario>")
        raise SystemExit(1)
    n = ingerir_export_whatsapp(sys.argv[2], sys.argv[3])
    print(f"Ingeridos {n} mensajes.")
