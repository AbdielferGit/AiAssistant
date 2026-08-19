"""
Almacén vectorial local (LanceDB) para los mensajes históricos del usuario.

Guarda cada mensaje con metadatos (destinatario, canal, fecha) para poder
recuperar ejemplos relevantes de estilo al redactar algo nuevo. El
directorio completo (settings.vector_db_path) se puede respaldar a Drive
con scripts/sync_to_drive.py — ver docs/PRODUCT_ROADMAP.md sobre los
límites de eso para un producto multi-cliente.
"""
from __future__ import annotations

from typing import TypedDict

import lancedb

from orchestrator.config import settings

TABLE_NAME = "mensajes_estilo"


class Mensaje(TypedDict):
    texto: str
    destinatario: str
    canal: str  # "whatsapp" | "email" | "messenger" | "imessage"
    fecha: str  # ISO 8601


def _conectar():
    return lancedb.connect(settings.vector_db_path)


def _tabla(db, vector_dim: int):
    if TABLE_NAME in db.table_names():
        return db.open_table(TABLE_NAME)
    # Esquema mínimo; LanceDB infiere el resto al insertar el primer batch.
    return db.create_table(
        TABLE_NAME,
        schema=None,
        data=[{"texto": "", "destinatario": "", "canal": "", "fecha": "", "vector": [0.0] * vector_dim}],
        mode="overwrite",
    )


def agregar_mensajes(mensajes: list[Mensaje], vectores: list[list[float]]) -> int:
    """Inserta mensajes ya vectorizados (usa un embedder externo, ver
    style_profile.py para el punto donde se generan los vectores)."""
    db = _conectar()
    tabla = _tabla(db, vector_dim=len(vectores[0]))
    filas = [
        {**m, "vector": v}
        for m, v in zip(mensajes, vectores)
    ]
    tabla.add(filas)
    return len(filas)


def buscar_similares(vector_consulta: list[float], destinatario: str | None, canal: str | None, k: int) -> list[dict]:
    db = _conectar()
    if TABLE_NAME not in db.table_names():
        return []
    tabla = db.open_table(TABLE_NAME)
    query = tabla.search(vector_consulta).limit(k)
    resultados = query.to_list()
    if destinatario:
        resultados = [r for r in resultados if r.get("destinatario") == destinatario] or resultados
    if canal:
        resultados = [r for r in resultados if r.get("canal") == canal] or resultados
    return resultados[:k]
