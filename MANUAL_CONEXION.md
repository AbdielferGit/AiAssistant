# Manual de conexión paso a paso

Sigue el orden. Cada sección indica qué haces en tu **Mac**, qué en tu
**Android**, y qué en la **consola web** de cada servicio.

---

## 0. Requisitos previos

En tu Mac:

```bash
brew install python@3.12 node git
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

En tu Android:
- Instala **Termux** y **Termux:API** desde F-Droid (no uses la versión de
  Play Store, está desactualizada) — https://f-droid.org/packages/com.termux/
- Instala **Tailscale** desde Play Store.

---

## 0.5. Lista blanca de contactos (OBLIGATORIO — hazlo antes de conectar cualquier canal)

Ningún mensaje se envía ni se procesa (en ninguna dirección) si el contacto
no está aquí. Sin este paso, todos los envíos de los pasos 3-6 se
rechazarán automáticamente.

1. Copia la plantilla:
   ```bash
   cp config/contacts.yaml.example config/contacts.yaml
   ```
2. Agrega tus contactos con el CLI (más fácil que editar YAML a mano):
   ```bash
   python scripts/manage_contacts.py agregar \
     --nombre "Juan Pérez" --alias juan \
     --whatsapp "+521234567890" --email "juan@correo.com"
   ```
3. Verifica:
   ```bash
   python scripts/manage_contacts.py listar
   ```
4. Para retirar autorización a alguien sin borrar su historial de estilo:
   ```bash
   python scripts/manage_contacts.py desactivar --alias juan
   ```

`config/contacts.yaml` contiene datos personales reales y **nunca se sube a
git** (ya está en `.gitignore`). Si despliegas en el VPS, cópialo ahí por
`scp`, igual que el `.env`.

---

## 1. Google Cloud (Gmail + Drive)

1. Ve a https://console.cloud.google.com/ y crea un proyecto nuevo, ej.
   "AiAsistant".
2. Menú → **APIs & Services → Library** → activa:
   - Gmail API
   - Google Drive API
3. **APIs & Services → OAuth consent screen**:
   - Tipo: External (o Internal si tienes Google Workspace).
   - Agrega tu propio correo como "test user".
4. **APIs & Services → Credentials → Create Credentials → OAuth client ID**:
   - Tipo de aplicación: "Desktop app".
   - Descarga el JSON y guárdalo como `credentials.json` en la raíz del repo
     (ya está en `.gitignore`, no se sube nunca).
5. Copia el `client_id` y `client_secret` de ese JSON a tu `.env`
   (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`).
6. En Drive, crea una carpeta llamada "AiAsistant-DB", ábrela y copia el ID
   que aparece en la URL (`.../folders/ESTE_ID`) → pégalo en
   `GOOGLE_DRIVE_DB_FOLDER_ID` de tu `.env`.
7. La primera vez que corras el orchestrator te abrirá el navegador para
   autorizar el acceso (OAuth). El token queda guardado en `token.json`
   (también en `.gitignore`).

Guía detallada de referencia: `scripts/setup_google_cloud.md`.

---

## 2. Servidor (VPS) — para no depender de tu Mac

1. Crea una cuenta en Hetzner Cloud o DigitalOcean.
2. Crea un servidor Ubuntu 22.04 (el plan más barato alcanza para el MVP).
3. Instala Docker en el VPS:
   ```bash
   curl -fsSL https://get.docker.com | sh
   ```
4. Instala Tailscale en el VPS:
   ```bash
   curl -fsSL https://tailscale.com/install.sh | sh
   sudo tailscale up
   ```
5. En tu Mac y en tu Android, abre la app de Tailscale e inicia sesión con
   la misma cuenta. Los tres dispositivos (VPS, Mac, Android) ahora comparten
   una red privada — anota la IP `100.x.x.x` que Tailscale le asigna al VPS,
   la vas a usar en `PHONE_BRIDGE_URL` / `WHATSAPP_BRIDGE_URL` en vez de una
   IP pública.
6. Clona el repo en el VPS y copia tu `.env` (nunca lo subas a git; cópialo
   por `scp` o pégalo directo en el servidor):
   ```bash
   git clone <tu-repo> && cd AiAsistant
   docker compose up -d
   ```

---

## 3. WhatsApp

Antes de esto, confirma que ya hiciste el paso 0.5 (lista blanca): tanto la
Cloud API como el puente Baileys rechazan mensajes hacia/desde cualquier
número que no esté ahí.

### 3a. Número de prueba oficial (Cloud API) — recomendado para empezar

Es gratis, no tiene riesgo de baneo, y es el valor por defecto
(`WHATSAPP_PROVIDER=cloud_api`). Limitación a tener presente: solo puede
mandar texto libre a números que **te hayan escrito primero** en las
últimas 24 h, y solo a los "testers" que agregues en el paso 4.

1. Ve a https://developers.facebook.com/apps → **Crear app** → tipo
   "Business" → nombre, ej. "AiAsistant".
2. En el dashboard de la app, agrega el producto **WhatsApp** ("Set up").
3. En **WhatsApp → API Setup** verás automáticamente un **número de
   prueba** (Test number) ya asignado por Meta, junto con:
   - `Temporary access token` → cópialo a `WHATSAPP_CLOUD_API_TOKEN` en tu
     `.env` (dura 24 h; en el paso 7 ves cómo generar uno permanente).
   - `Phone number ID` → cópialo a `WHATSAPP_CLOUD_API_PHONE_NUMBER_ID`.
4. En la misma pantalla, sección **"To"**, agrega el número de WhatsApp de
   tu contacto de prueba (puede ser tu propio celular) y verifícalo con el
   código que llega por WhatsApp. Solo los números agregados aquí (máx. 5
   en modo prueba) pueden recibir/enviar mensajes.
5. Agrega ese mismo número también a `config/contacts.yaml` (paso 0.5) —
   ambas listas tienen que coincidir.
6. Configura el webhook para recibir mensajes entrantes (necesario para la
   ventana de 24h y para que el asistente vea lo que te escriben):
   - Corre el orchestrator local: `uvicorn orchestrator.bridge.server:app --port 8090`.
   - En otra terminal, expón el puerto con [ngrok](https://ngrok.com/) (gratis,
     solo para pruebas): `ngrok http 8090`.
   - En Meta: **WhatsApp → Configuration → Webhook → Edit** → URL:
     `https://<tu-subdominio-ngrok>.ngrok-free.app/webhooks/whatsapp_cloud`,
     Verify token: el mismo valor que pusiste en `WHATSAPP_CLOUD_API_VERIFY_TOKEN`.
   - Suscríbete al campo `messages`.
7. Prueba: desde el número tester, escribe "hola" al número de prueba.
   Debe aparecer en `GET /inbound` (con tu `PHONE_BRIDGE_TOKEN` como
   Authorization). A partir de ahí tienes 24 h para que el asistente te
   responda con texto libre.
8. Cuando quieras dejar de depender del token temporal de 24h: **App →
   WhatsApp → API Setup → System users** te deja generar un token
   permanente asociado a un usuario de sistema.

### 3b. WhatsApp personal (Baileys, no oficial) — opcional, más adelante

Solo si decides que quieres actuar desde tu número personal real y aceptas
el riesgo descrito en `docs/ARCHITECTURE.md`. Pon `WHATSAPP_PROVIDER=baileys`
en tu `.env` y:

1. En el VPS (o local para probar primero):
   ```bash
   cd whatsapp-bridge
   npm install
   npm start
   ```
2. La primera vez imprime un **código QR** en la terminal.
3. Abre WhatsApp en tu celular → **Ajustes → Dispositivos vinculados →
   Vincular un dispositivo** → escanea el QR.
4. La sesión queda guardada en `whatsapp-bridge/auth_session/` (no se sube a
   git). Mientras ese proceso siga corriendo en el VPS, la sesión se
   mantiene activa sin que tu celular necesite estar conectado.

---

## 4. Puente con tu Android (android-bridge/)

1. Abre Termux en tu celular y ejecuta:
   ```bash
   pkg update && pkg install python git termux-api
   ```
2. Copia (o clona) la carpeta `android-bridge/` al celular, ej.:
   ```bash
   git clone <tu-repo> AiAsistant
   cd AiAsistant/android-bridge
   pip install -r requirements.txt
   ```
3. Edita `scripts/listener.py` (o exporta variables de entorno) con:
   - `PHONE_BRIDGE_URL` → la IP de Tailscale del VPS + puerto (ej.
     `http://100.x.x.x:8090`)
   - `PHONE_BRIDGE_TOKEN` → el mismo valor que pusiste en el `.env` del
     servidor.
4. Corre el listener:
   ```bash
   python listener.py
   ```
5. Para que seison, instala **Termux:Boot** (F-Droid) y agrega un script en
   `~/.termux/boot/` que lance `listener.py` — así sobrevive a reinicios del
   teléfono. Detalle en `android-bridge/README.md`.

---

## 5. Mac (mac-bridge/) — para iMessage, Mail, Calendar, apps

1. Da permisos de Automatización y Accesibilidad a Terminal (o a tu app):
   **Preferencias del Sistema → Privacidad y Seguridad → Accesibilidad /
   Automatización**.
2. Prueba un script de ejemplo:
   ```bash
   osascript mac-bridge/scripts/applescript/send_imessage.applescript "Hola, esto es una prueba" "+1234567890"
   ```
3. Si quieres que el orchestrator corra en tu Mac (no solo el bridge),
   sigue igual el paso 0 y `docker compose up -d` local en vez de en el VPS.

---

## 6. Messenger (opcional, léelo antes de activarlo)

`orchestrator/tools/messenger.py` está dejado como **stub documentado a
propósito**: no lo actives con una librería no oficial hasta decidir
conscientemente el riesgo (ver `docs/ARCHITECTURE.md`). Si quieres avanzar
por la vía oficial: crea una Página de Facebook, une Meta Business Suite,
y sigue https://developers.facebook.com/docs/messenger-platform/ para
obtener un `MESSENGER_PAGE_ACCESS_TOKEN`.

---

## 7. Primera prueba de punta a punta

```bash
source .venv/bin/activate
python orchestrator/main.py
```

Di (o escribe, si todavía no conectaste el STT): *"Redacta un WhatsApp para
[contacto] confirmando la reunión de mañana"*. El asistente debe:
1. Buscar en tu memoria de estilo (`orchestrator/memory/`) ejemplos de cómo
   le escribes a esa persona.
2. Mostrarte el borrador.
3. Esperar tu confirmación antes de llamar a `tools/whatsapp.py`.

Si el borrador se ve bien y se envía solo tras tu "sí" — el flujo base
funciona. A partir de ahí, sigue `docs/PRODUCT_ROADMAP.md`.
