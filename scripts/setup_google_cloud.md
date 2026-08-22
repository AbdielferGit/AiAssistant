# Setup detallado de Google Cloud (Gmail + Drive + Calendar)

Referencia ampliada de `MANUAL_CONEXION.md` sección 1.

1. https://console.cloud.google.com/projectcreate → nombre "AiAssistant".
2. **APIs & Services → Library** → busca y activa, una por una:
   - Gmail API
   - Google Drive API
   - Google Calendar API
3. **APIs & Services → OAuth consent screen**
   - User type: External.
   - App name: "AiAssistant" (uso interno, no necesita pasar revisión de
     Google mientras solo tú lo uses como "test user").
   - Scopes: agrega `gmail.send`, `drive.file`, `calendar.events` (los
     mismos definidos en `orchestrator/tools/google_workspace.py`).
   - Test users: agrega tu propio correo (abdielfer@gmail.com).
4. **APIs & Services → Credentials → + Create Credentials → OAuth client ID**
   - Application type: Desktop app.
   - Nombre: "AiAssistant CLI".
   - Descarga el JSON → guárdalo como `credentials.json` en la raíz del repo.
5. Primera ejecución: `python -m orchestrator.main` (o cualquier script que
   llame a `google_workspace._get_credentials()`) abrirá el navegador para
   que autorices — el token queda cacheado en `token.json`.

## Notas
- Mientras la app esté en modo "Testing", el token expira cada 7 días y hay
  que re-autorizar. Si te vuelves molesto, puedes publicar la app en modo
  "In production" (no requiere revisión de Google para scopes no
  sensibles como estos) desde la misma pantalla de OAuth consent screen.
- Para el VPS (fase 2), copia `credentials.json` y `token.json` ya
  autorizados desde tu Mac — no repitas el flujo OAuth interactivo en un
  servidor sin navegador.
