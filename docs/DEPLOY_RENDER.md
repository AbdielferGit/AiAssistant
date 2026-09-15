# Desplegar la versión web en Render

Guía paso a paso para publicar `orchestrator/web/` (login por invitación,
chat con los 4 agentes por panel lateral, y la herramienta `/reels`) como
un **segundo servicio independiente** en la misma cuenta de Render donde
ya vive el "recepcionista" (`orchestrator/webhooks/whatsapp_cloud.py`) —
mismo repo, misma rama, distinto comando de arranque y sus propias
variables de entorno. Ver `render.yaml` en la raíz del repo.

Bluehost se descartó para esto — ver `docs/DEPLOY_BLUEHOST.md` (Apache
del hosting compartido no soporta Passenger). Render es el camino
confirmado: es donde ya corre el recepcionista en producción.

## 1. Reunir los valores que vas a necesitar

Nada de esto se sube al repo — son secretos, se pegan a mano en el
dashboard de Render. Tenelos a mano antes de empezar:

| Variable | De dónde sale |
|---|---|
| `ANTHROPIC_API_KEY` | tu `.env` local |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | tu `.env` local |
| `WEB_SESSION_SECRET` | tu `.env` local (o generá uno nuevo — no importa que sea distinto al local) |
| `INVITED_USERS_YAML` | `cat config/invited_users.yaml` en tu Mac, pegás el resultado completo |
| `GOOGLE_TOKEN_JSON` | `cat token.json` en tu Mac (si no existe o está vencido, corré primero `python scripts/reautorizar_google.py`) |
| `GOOGLE_DRIVE_REELS_FOLDER_ID` | el ID que ya tenés en tu `.env` |
| `GOOGLE_DRIVE_DB_FOLDER_ID` | tu `.env` (opcional, respaldo de la DB local) |
| `ELEVENLABS_API_KEY` | tu `.env` |
| `AZURE_SPEECH_KEY` / `AZURE_SPEECH_REGION` / `AZURE_SPEECH_VOICE_FR_CA` | tu `.env` |

`GOOGLE_OAUTH_REDIRECT_URI` lo dejás para el paso 4 — depende de la URL
que Render te asigne, que todavía no existe.

## 2. Crear el servicio desde el Blueprint

1. En el dashboard de Render (la misma cuenta donde está el
   recepcionista) → **New** → **Blueprint**.
2. Elegí este repositorio de GitHub y la rama que quieras desplegar.
3. Render detecta `render.yaml` solo y te muestra el servicio
   `aiassistant-web` que define — revisalo y confirmá.
4. Te va a pedir, uno por uno, cada variable marcada `sync: false` en
   `render.yaml` — pegá los valores de la tabla de arriba. Las que son
   opcionales (WhatsApp/Messenger del agente "asistente") las podés dejar
   vacías si no las vas a usar todavía.
5. Confirmá — Render hace el primer deploy solo.

## 3. Confirmar que levantó

Andá a la URL que Render te asignó (algo como
`https://aiassistant-web-xxxx.onrender.com`) — deberías ver la pantalla
de login "Sign in with Google". Si en cambio ves un error 500 o la página
no carga, revisá los **Logs** del servicio en Render — casi siempre es
`ANTHROPIC_API_KEY` faltante (la única variable que hace que el proceso
ni arranque, ver `orchestrator/config.py`).

## 4. El paso que se olvida: actualizar el redirect URI de Google

El login con Google va a fallar (`redirect_uri_mismatch`) hasta que
hagas esto:

1. **Google Cloud Console** → tu proyecto → APIs & Services →
   Credentials → tu OAuth Client ID → agregá la URL real de Render
   (`https://aiassistant-web-xxxx.onrender.com/`) a **Authorized redirect
   URIs** — sin sacar la de `localhost`, dejá las dos.
2. En Render, seteá `GOOGLE_OAUTH_REDIRECT_URI` con esa misma URL nueva.
3. Redeploy (Render → Manual Deploy, o esperá a que el próximo `git push`
   lo dispare solo).

## 5. Costo

`plan: free` en `render.yaml` — $0/mes, pero el servicio se duerme a los
15 minutos sin tráfico (el primer visitante después espera ~1 minuto
mientras arranca). Para que quede siempre despierto sin esa demora,
cambiá `plan: free` a `plan: starter` en `render.yaml` (~$7 USD/mes) y
hacé push — Render aplica el cambio solo, no hace falta recrear el
servicio.

## Después del primer deploy

Cada `git push` a la rama conectada redespliega solo — no hay que volver
a tocar nada de esto salvo que cambien las variables de entorno (ej. si
rotás una API key, hay que actualizarla también en Render, no solo en tu
`.env` local).
