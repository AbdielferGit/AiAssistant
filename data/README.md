# data/

Aquí vive la base de datos local: el índice vectorial de estilo (LanceDB,
carpeta `vector_store/`) y cualquier SQLite auxiliar. **No se sube a git**
(ver `.gitignore`) porque contiene tus mensajes reales.

## Respaldo a Google Drive

`scripts/sync_to_drive.py` sube el contenido de esta carpeta a la carpeta
de Drive configurada en `GOOGLE_DRIVE_DB_FOLDER_ID` (`.env`). Prográmalo
como tarea periódica en el VPS:

```bash
crontab -e
# Sincroniza cada hora:
0 * * * * cd /ruta/AiAssistant && .venv/bin/python scripts/sync_to_drive.py >> sync.log 2>&1
```

Esto es un **respaldo/export**, no una base de datos multi-escritor. Si en
algún momento corres el orchestrator desde más de un lugar a la vez (Mac +
VPS simultáneamente, por ejemplo), vas a tener conflictos. Para eso —y para
la versión producto multi-cliente— la ruta correcta es migrar a Postgres
gestionado (ver `docs/PRODUCT_ROADMAP.md`).
