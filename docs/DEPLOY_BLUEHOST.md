# Desplegar la versión web en Bluehost

> **Actualización tras el primer intento real (22 ago 2026):** en la
> cuenta "Online Store" concreta que usamos, **Apache rechaza los
> directivos de Passenger** (`.htaccess: Invalid command 'PassengerAppRoot',
> perhaps misspelled or defined by a module not included in the server
> configuration` — visible en cPanel → Metrics → Errors). Es decir:
> `mod_passenger` NO está cargado en este servidor, aunque la propia UI de
> "Application Manager" de Bluehost deje registrar la app y corra `pip
> install` sin quejarse (usa `pip install --user` con el Python del
> sistema, no un virtualenv — otra señal de que esta skin de Bluehost es
> más limitada que un cPanel/WHM estándar con Passenger real). Ver la
> sección "Qué SÍ funcionó" abajo para lo que quedó probado end-to-end, y
> "Alternativas" para las opciones reales de aquí en más.

Guía paso a paso para publicar `orchestrator/web/` (login por invitación +
chat) en el hosting compartido "Online Store" de Bluehost que ya tienes,
usando el dominio `getaiassistant.app` (comprado — ver historial de esta
conversación) y Phusion Passenger (Application Manager de cPanel).

Confirmado previamente por SSH: el hosting ofrece **Python 3.9.25**. Todo
el código de este repo (`from __future__ import annotations` + sintaxis
`X | None`) es compatible con 3.9.

> Nota sobre cPanel Terminal: el acceso a Terminal por SSO va atado a un
> token de sesión de un solo uso (`cpsess...`) embebido en la URL. Si
> pegas una URL de Terminal vieja o la recargas después de navegar fuera,
> te bota al login. Siempre entra de nuevo desde "My Account" → botón
> **cPanel** → navega a Terminal haciendo clic dentro de la página, nunca
> escribiendo una URL a mano.

## 1. Crear la app Python en Application Manager

1. cPanel → **Setup Python App** (Application Manager / Passenger).
2. **Create Application**:
   - Python version: 3.9 (la más alta disponible).
   - Application root: la ruta donde subirás el repo, p. ej. `aiassistant`
     (queda en `~/aiassistant`).
   - Application URL: el dominio `getaiassistant.app` (o un subdominio si
     prefieres probar antes en `staging.getaiassistant.app`).
   - Application startup file: `passenger_wsgi.py`.
   - Application Entry point: `application` (la variable que exporta
     `passenger_wsgi.py` — ya está resuelta en este repo, no la cambies).
3. Al crear la app, cPanel te da un comando tipo
   `source /home/.../virtualenv/aiassistant/3.9/bin/activate` — ese es el
   virtualenv que usa Passenger. Todo lo que instales fuera de esa
   activación NO lo verá la app.

## 2. Subir el código

Dos formas, cualquiera sirve:

- **Git** (recomendado si ya tienes el repo en GitHub/GitLab): cPanel →
  **Git Version Control** → clona el repo dentro de la carpeta que
  registraste como Application root.
- **File Manager / SFTP**: sube el contenido del repo (puedes excluir
  `whatsapp-bridge/node_modules`, `android-bridge/`, `data/`, `.git/`).

## 3. Instalar dependencias en el virtualenv de la app

Desde Terminal (con la sesión fresca, ver nota arriba):

```bash
source /home/TU_USUARIO/virtualenv/aiassistant/3.9/bin/activate
cd ~/aiassistant
pip install -r requirements.txt
```

Si `lancedb` falla en compilar en el hosting compartido (a veces pasa por
falta de toolchain nativo), quítalo de requirements.txt para el despliegue
web — `orchestrator/web/app.py` no lo usa; solo lo necesitan
`orchestrator/memory/vector_store.py`, que la web todavía no invoca.

## 4. Configurar los secretos en el servidor

```bash
cp .env.example .env
nano .env   # o el editor que prefieras
```

Rellena, como mínimo, para que la web funcione:
- `ANTHROPIC_API_KEY`
- `ANTHROPIC_MODEL` (opcional, por defecto `claude-sonnet-5`)
- `GOOGLE_CLIENT_ID` — **debe ser un OAuth client de tipo "Web
  application"** (no el "Desktop app" que ya tienes para Gmail/Drive, ver
  paso 6 abajo), porque Google Identity Services solo acepta ese tipo
  para el flujo de botón "Sign in with Google" del navegador.
- `WEB_SESSION_SECRET` — genera uno con
  `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`
  y pégalo aquí. Sin esto, cada reinicio de Passenger invalida todas las
  sesiones (ver `orchestrator/config.py`).

```bash
cp config/contacts.yaml.example config/contacts.yaml
cp config/invited_users.yaml.example config/invited_users.yaml
nano config/invited_users.yaml   # agrega tu correo y el de quien invites
```

`.env` y ambos YAML reales están en `.gitignore` — nunca los subas a git,
solo existen en el servidor (y en tu Mac).

## 5. Reiniciar la app

Application Manager → tu app → **Restart**. Luego visita
`https://getaiassistant.app` — deberías ver la pantalla de login.

## 6. Crear el OAuth client "Web application" en Google Cloud

En el proyecto `AiAssistant` (ya renombrado) de Google Cloud Console:

1. **APIs & Services → Credentials → + Create Credentials → OAuth client ID**
2. Application type: **Web application**.
3. Nombre: "AiAssistant Web".
4. **Authorized JavaScript origins**: agrega `https://getaiassistant.app`
   (y `http://localhost:8000` si vas a probar la web en local antes).
5. No hace falta "Authorized redirect URIs" — Google Identity Services
   (el botón que usa `orchestrator/web/static/login.html`) no redirige,
   solo postea un token vía JS.
6. Copia el **Client ID** resultante a `GOOGLE_CLIENT_ID` en el `.env` del
   servidor (paso 4). La "Client secret" de este client no se usa — GIS en
   modo botón es público (client-side), la seguridad real la da
   `orchestrator/web/auth.py` verificando el token contra Google y contra
   `config/invited_users.yaml`.

## 7. Apuntar el dominio al hosting

Si compraste `getaiassistant.app` en Bluehost y el hosting también está en
Bluehost, esto normalmente ya está conectado (mismo panel). Si no:
- Bluehost → **Domains** → `getaiassistant.app` → apunta los nameservers
  o el registro A/CNAME al hosting donde vive la Application Manager.

## 8. Verificación final

- `https://getaiassistant.app` → botón de Google → inicia sesión con un
  correo de `config/invited_users.yaml` → debería mostrar el chat.
- Prueba un mensaje que dispare una tool **irreversible** (p. ej. pedirle
  que envíe un WhatsApp) — debe aparecer el modal de confirmar/cancelar en
  vez de bloquear nada.
- Prueba con un correo de Google que NO esté invitado → debe rechazar el
  login con 403.

## Qué SÍ quedó probado (22 ago 2026)

- El dominio `getaiassistant.app` está conectado a este hosting como sitio
  propio ("AiAssistant" en Websites), con document root
  `~/public_html/website_87943c0c`.
- Todo `requirements.txt` instala limpio con `pip3.9 install --user` en el
  Python 3.9.25 del servidor (incluyendo `lancedb`).
- Hubo que fijar `oauthlib>=3.2.0` explícitamente (ya está en
  requirements.txt) — el `oauthlib` del sistema (3.1.1) no expone
  `SIGNATURE_RSA`, rompe la cadena `google-auth-oauthlib`.
- Se encontró y corrigió un bug real: `orchestrator/memory/vector_store.py`
  importaba `lancedb` a nivel de módulo, y `lancedb` arranca un hilo en
  background al importarse — en este hosting eso revienta con
  `RuntimeError: can't start new thread` (límite de hilos/procesos de
  CageFS). Ya está resuelto con un import perezoso dentro de `_conectar()`.
- Con todo lo anterior, `python3.9 -m uvicorn orchestrator.web.app:app`
  corriendo standalone en el propio servidor responde `HTTP 200`
  correctamente — **el código en sí funciona en este hosting**. El único
  bloqueador es que Apache no tiene `mod_passenger` para exponerlo por
  `https://getaiassistant.app`.
- El `.env`, `config/contacts.yaml` y `config/invited_users.yaml` reales ya
  quedaron creados en el servidor (con datos mínimos: solo tu correo/tu
  contacto). Falta rellenar `GOOGLE_CLIENT_ID` cuando se cree el OAuth
  client "Web application" (paso 6 de esta guía).

## Alternativas ahora que Passenger no está disponible aquí

1. **Pedir a soporte de Bluehost que habilite Passenger** para esta cuenta
   (mencionar el error exacto de arriba). Si lo activan, el resto de esta
   guía (pasos 1–8) debería funcionar tal cual, ya con el código validado.
2. **Mover solo el backend Python a un host que sí lo soporte de fábrica**
   (Render, Railway, Fly.io — capas gratuitas o casi gratuitas) y dejar que
   `getaiassistant.app` (o un subdominio `api.getaiassistant.app`) apunte
   ahí por DNS/CNAME. Bluehost seguiría sirviendo el dominio; el cómputo
   viviría afuera.
3. **CGI/FastCGI puro** en vez de Passenger, si este servidor lo soporta
   (`mod_fcgid` suele venir activado incluso donde Passenger no) — exigiría
   adaptar `passenger_wsgi.py` a un wrapper `.fcgi`, más trabajo y menos
   estándar que las otras dos opciones.

## Pendiente después de esto

- HTTPS: Bluehost normalmente da SSL gratis (Let's Encrypt) por dominio —
  actívalo en cPanel → SSL/TLS Status si `https://` no carga solo.
- Si el tráfico crece más allá de "tú + unos invitados", migrar
  `_conversaciones` / `_pendientes` (hoy en memoria del proceso, ver
  `orchestrator/web/app.py`) a algo persistente — es un cambio aislado a
  ese archivo, no toca el resto del sistema.
