# Manual de conexión paso a paso

Sigue el orden. Todo esto corre **en tu Mac, en local** — no hay VPS ni
celular Android involucrados.

---

## 0. Requisitos previos

```bash
brew install python@3.12 git
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 0.5. Lista blanca de contactos (OBLIGATORIO — hazlo antes de conectar cualquier canal)

Ningún mensaje se envía ni se procesa (en ninguna dirección) si el contacto
no está aquí. Sin este paso, todos los envíos de los pasos 3-6 se
rechazarán automáticamente.

1. Copia la plantilla:
   ```bash
   cp config/contacts.yaml.example config/contacts.yaml
   ```
2. Agrega tus contactos con el CLI (más fácil que editar YAML a mano). Los
   medios (`--medio nombre=valor`) son libres — pon solo los que tengas a
   mano ahora:
   ```bash
   python scripts/manage_contacts.py agregar \
     --nombre "Juan Pérez" --alias juan \
     --medio whatsapp=+521234567890 --medio email=juan@correo.com
   ```
3. Verifica:
   ```bash
   python scripts/manage_contacts.py listar
   ```
4. Agrega medios nuevos más adelante, progresivamente, sin recrear el
   contacto:
   ```bash
   python scripts/manage_contacts.py agregar-medio --alias juan --medio imessage=+521234567890
   ```
5. Para retirar autorización a alguien sin borrar su historial de estilo:
   ```bash
   python scripts/manage_contacts.py desactivar --alias juan
   ```

`config/contacts.yaml` contiene datos personales reales y **nunca se sube a
git** (ya está en `.gitignore`).

---

## 1. Google Cloud (Gmail + Calendar + Drive)

1. Ve a https://console.cloud.google.com/ y crea un proyecto nuevo, ej.
   "AiAssistant".
2. Menú → **APIs & Services → Library** → activa:
   - Gmail API
   - Google Calendar API
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
6. En Drive, crea una carpeta llamada "AiAssistant-DB", ábrela y copia el ID
   que aparece en la URL (`.../folders/ESTE_ID`) → pégalo en
   `GOOGLE_DRIVE_DB_FOLDER_ID` de tu `.env`.
7. La primera vez que corras el orchestrator te abrirá el navegador para
   autorizar el acceso (OAuth). El token queda guardado en `token.json`
   (también en `.gitignore`).

Guía detallada de referencia: `scripts/setup_google_cloud.md`.

---

## 2. WhatsApp (Meta, oficial — número de prueba)

Antes de esto, confirma que ya hiciste el paso 0.5 (lista blanca): la
Cloud API rechaza mensajes hacia/desde cualquier número que no esté ahí.

Es gratis, no tiene riesgo de baneo (a diferencia de un puente no oficial,
que este proyecto ya no usa). Limitación a tener presente: solo puede
mandar texto libre a números que **te hayan escrito primero** en las
últimas 24 h, y solo a los "testers" que agregues en el paso 4.

1. Ve a https://developers.facebook.com/apps → **Crear app** → tipo
   "Business" → nombre, ej. "AiAssistant".
2. En el dashboard de la app, agrega el producto **WhatsApp** ("Set up").
3. En **WhatsApp → API Setup** verás automáticamente un **número de
   prueba** (Test number) ya asignado por Meta, junto con:
   - `Temporary access token` → cópialo a `WHATSAPP_CLOUD_API_TOKEN` en tu
     `.env` (dura 24 h; el paso 8 muestra cómo generar uno permanente).
   - `Phone number ID` → cópialo a `WHATSAPP_CLOUD_API_PHONE_NUMBER_ID`.
4. En la misma pantalla, sección **"To"**, agrega el número de WhatsApp de
   tu contacto de prueba (puede ser tu propio celular) y verifícalo con el
   código que llega por WhatsApp. Solo los números agregados aquí (máx. 5
   en modo prueba) pueden recibir/enviar mensajes.
5. Agrega ese mismo número también a `config/contacts.yaml` (paso 0.5) —
   ambas listas tienen que coincidir.
6. (Opcional) Para recibir WhatsApp entrante y habilitar la ventana de 24h:
   - Corre el webhook local: `uvicorn orchestrator.webhooks.whatsapp_cloud:app --port 8090`.
   - En otra terminal, expón el puerto con [ngrok](https://ngrok.com/) (gratis,
     solo para pruebas): `ngrok http 8090`.
   - En Meta: **WhatsApp → Configuration → Webhook → Edit** → URL:
     `https://<tu-subdominio-ngrok>.ngrok-free.app/webhooks/whatsapp_cloud`,
     Verify token: el mismo valor que pusiste en `WHATSAPP_CLOUD_API_VERIFY_TOKEN`.
   - Suscríbete al campo `messages`.
   - Prueba: desde el número tester, escribe "hola" al número de prueba —
     debe aparecer en los logs del proceso (`INFO ... Mensaje de WhatsApp
     aceptado de ...`). A partir de ahí tienes 24 h para que el asistente
     te responda con texto libre.
7. Sin el webhook del paso 6, `enviar_whatsapp` funciona igual — solo
   pierdes la ventana de 24h para texto libre no solicitado.
8. Cuando quieras dejar de depender del token temporal de 24h: **App →
   WhatsApp → API Setup → System users** te deja generar un token
   permanente asociado a un usuario de sistema.

---

## 3. Mac (mac-bridge/) — para iMessage, Mail, Calendar, apps

1. Da permisos de Automatización y Accesibilidad a Terminal (o a tu app):
   **Preferencias del Sistema → Privacidad y Seguridad → Accesibilidad /
   Automatización**.
2. Prueba un script de ejemplo:
   ```bash
   osascript mac-bridge/scripts/applescript/send_imessage.applescript "Hola, esto es una prueba" "+1234567890"
   ```

---

## 4. Messenger (opcional, léelo antes de activarlo)

`orchestrator/tools/messenger.py` está dejado como **stub documentado a
propósito**: no lo actives con una librería no oficial. Vía oficial: crea
una Página de Facebook, únela a Meta Business Suite, y sigue
https://developers.facebook.com/docs/messenger-platform/ para obtener un
`MESSENGER_PAGE_ACCESS_TOKEN`.

---

## 5. Primera prueba de punta a punta

```bash
source .venv/bin/activate
python -m orchestrator.main
```

(Corre siempre como módulo con `-m`, no como script suelto — así Python
agrega la raíz del repo a `sys.path` y los imports `orchestrator.*`
funcionan. Para el Analista de CEO: `python -m orchestrator.main --agente ceo`.)

Escribe algo como: *"Redacta un WhatsApp para [contacto] confirmando la
reunión de mañana"*. El asistente debe:
1. Buscar en tu memoria de estilo (`orchestrator/memory/`) ejemplos de cómo
   le escribes a esa persona.
2. Mostrarte el borrador.
3. Esperar tu confirmación antes de llamar a `tools/whatsapp.py`.

Si el borrador se ve bien y se envía solo tras tu "sí" — el flujo base
funciona.
