# AiAssistant

Un mismo cerebro (Python, SDK oficial de Anthropic) sirve dos productos
distintos:

- **Asistente** — tu asistente personal: Google (email + calendario),
  WhatsApp/Messenger y acciones en tu Mac. Se usa por terminal o por la
  web privada, y solo habla con contactos que tú autorizaste.
- **Recepcionista (Accueil+)** — un recepcionista de WhatsApp para UN
  negocio cliente, configurable por `config/negocio.yaml`, sin código
  nuevo por cliente. Es público a propósito: le contesta a cualquier
  desconocido que le escriba al negocio (con límite de mensajes por hora
  contra abuso, en vez de lista blanca).

## Empezar aquí

1. Lee [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) para entender cómo encajan las piezas.
2. Sigue [`MANUAL_CONEXION.md`](MANUAL_CONEXION.md) paso a paso para conectar Google + WhatsApp/Messenger + Mac.
3. Para usarlo desde el navegador (no solo terminal), ve
   [`docs/DEPLOY_BLUEHOST.md`](docs/DEPLOY_BLUEHOST.md) — despliegue con
   login por invitación (`orchestrator/web/`). En producción corre en
   Render — ver [Despliegue](#despliegue) más abajo.

## Estructura del repo

```
AiAssistant/
├── MANUAL_CONEXION.md       # Manual paso a paso (Google + WhatsApp/Messenger + Mac)
├── .env.example             # Variables de entorno necesarias
├── passenger_wsgi.py         # Punto de entrada para Phusion Passenger (despliegue Bluehost, descartado — ver docs/DEPLOY_BLUEHOST.md)
├── render.yaml                # Blueprint de Render para el servicio "asistente web" — ver docs/DEPLOY_RENDER.md
├── config/
│   ├── contacts.yaml.example        # Plantilla de la lista blanca de contactos
│   ├── invited_users.yaml.example   # Plantilla de la lista de invitados a la web
│   └── negocio.yaml.example         # Plantilla del perfil de negocio para el agente "recepcionista"
├── orchestrator/            # Cerebro del asistente (Python, SDK oficial de Anthropic)
│   ├── main.py               # Loop genérico de tool-use por terminal — no conoce ningún agente en particular
│   ├── router.py              # Antes de responder, elige (con Haiku) qué agente le toca al mensaje
│   ├── config.py              # Carga de configuración/.env
│   ├── contacts.py            # Lista blanca — autoriza envío/recepción en ambas direcciones
│   ├── agents/                 # Agentes — se autodescubren, no hace falta tocar el orchestrator
│   │   ├── base.py               # Clase plantilla Agent_0 — instánciala para crear un agente nuevo
│   │   ├── personal_assistant.py # Agente "asistente" (predeterminado): envía, redacta, agenda
│   │   ├── ceo_analyst.py        # Agente "ceo": Analista de CEO, sin tools (puro análisis)
│   │   ├── receptionist.py       # Agente "recepcionista": representa a UN negocio (Accueil+), configurable por config/negocio.yaml
│   │   └── reel_producer.py      # Agente "productor_reels": genera los .mp4 de las campañas de FB/IG (narración fr-CA + subtítulo en inglés) — ver orchestrator/tools/reel_generator.py
│   ├── tools/                 # "Herramientas" que el LLM puede invocar
│   │   ├── google_workspace.py  # Gmail + Calendar + Drive
│   │   ├── whatsapp.py          # Lista blanca + delega a whatsapp_cloud_api.py
│   │   ├── whatsapp_cloud_api.py # Cliente de la WhatsApp Cloud API (Meta, oficial)
│   │   ├── messenger.py         # Meta Messenger Platform (oficial, solo Páginas)
│   │   ├── macos_actions.py     # AppleScript / Shortcuts desde Python
│   │   ├── reel_generator.py    # Voz fr-CA (ElevenLabs o Azure Speech) + fondos/íconos/mockups Pillow → .mp4 en data/reels/
│   │   ├── guiones_reels.py     # Guiones de reels ya aprobados (texto fr/en + tema) — evita retipear un guion validado
│   │   └── reels_defaults.py    # Parámetros por defecto (voz, ritmo/pausa, URL/guion de cada producto) — tiene prioridad para productor_reels
│   ├── assets/
│   │   └── fonts/               # Work Sans (OFL) — tipografía usada para el subtítulo de los reels
│   ├── memory/                 # Estilo de escritura + memoria vectorial
│   │   ├── vector_store.py
│   │   ├── style_profile.py
│   │   └── inbound_tracker.py    # Último mensaje entrante por remitente (ventana de 24h de WhatsApp)
│   ├── webhooks/                # Mensajes ENTRANTES de Meta (WhatsApp Cloud API)
│   │   └── whatsapp_cloud.py     # FastAPI: webhook del "recepcionista" — público, sin lista blanca, con límite de mensajes/hora (despliegue: Render)
│   └── web/                    # Versión web del "asistente" — acceso remoto solo por invitación (despliegue: Render)
│       ├── app.py                # FastAPI: login, chat (mismo router/agentes que main.py), confirmar/cancelar, y /reels (herramienta de generación de reels, sube a Drive)
│       ├── auth.py                # Google Sign-In + cookie de sesión firmada
│       ├── invites.py             # Lista blanca de quién puede iniciar sesión
│       └── static/                # login.html + index.html (chat) + reels.html (herramienta de reels) — frontend mínimo, sin build
├── mac-bridge/                # AppleScripts para iMessage/Mail/Calendar
├── scripts/                  # Setup de Google Cloud, sync a Drive, reautorizar_google.py (reautoriza Gmail/Calendar/Drive sin pasar por el chat)
└── data/                     # DB local (LanceDB/SQLite) + data/reels/ (.mp4 generados) — no se sube a git
```

## Agregar un agente nuevo

No se toca `main.py` ni el registro — solo crea un archivo en
`orchestrator/agents/` que instancie `Agent_0` (ver el docstring de
[`orchestrator/agents/base.py`](orchestrator/agents/base.py) para un
ejemplo completo). El paquete lo autodescubre la próxima vez que corras
`python -m orchestrator.main`, y el enrutador ([`orchestrator/router.py`](orchestrator/router.py))
empieza a considerarlo automáticamente para cada mensaje según su
`descripcion_enrutador` — no hace falta seleccionarlo a mano salvo que
quieras fijarlo con `--agente <id>`.

## Despliegue

Dos servicios independientes en Render, cada uno desplegado desde este
mismo repo (`main`) pero con su propio comando de arranque y sus propias
variables de entorno:

| Servicio | Punto de entrada | Variables | Notas |
|---|---|---|---|
| Web del "asistente" | `uvicorn orchestrator.web.app:app` | `.env` propio | Acceso privado, solo invitados (`config/invited_users.yaml`) |
| Webhook del "recepcionista" | `uvicorn orchestrator.webhooks.whatsapp_cloud:app` | Environment Group "Recepcionista" (incluye `NEGOCIO_YAML`, el contenido de `config/negocio.yaml` serializado — para hostings sin disco persistente) | Público, sin login; el webhook de Meta apunta directo aquí |

Para un negocio cliente nuevo del recepcionista: no hace falta tocar
código, solo escribir su `config/negocio.yaml` (o el `NEGOCIO_YAML` del
Environment Group) y actualizar la Callback URL en Meta for Developers →
Casos de uso → Conectar en WhatsApp.

La web del "asistente" (chat con panel lateral para elegir agente +
`/reels`) todavía no está desplegada — `render.yaml` en la raíz del repo
la arma casi sola como Blueprint de Render, ver el paso a paso completo en
[`docs/DEPLOY_RENDER.md`](docs/DEPLOY_RENDER.md).

## Estado actual

El **recepcionista** ya pasó un piloto real de punta a punta (WhatsApp real,
Meta Cloud API, desplegado en Render) y quedó validado como producto
funcional para un negocio cliente. El resto — Gmail/Calendar, Messenger,
acciones en Mac del **asistente** personal — sigue siendo el andamiaje
inicial: la estructura y los stubs están listos, pero cada integración
necesita que completes credenciales siguiendo `MANUAL_CONEXION.md` antes de
que funcione de punta a punta.

El **productor_reels** ya se probó de punta a punta — genera un video
vertical (9:16) real, con narración en francés quebequense y subtítulo en
inglés, sin romper el arranque del orchestrator si faltan credenciales.
Dos proveedores de voz: **ElevenLabs** (una voz elegida a mano por el
usuario en su Voice Library — el default hoy) con fallback a **Azure
Speech** (`fr-CA-Sylvie:DragonHDLatestNeural`, la voz "HD" — validada
contra las voces estándar por sonar notablemente menos robótica).
Animación/mockups con Pillow, render con moviepy → `.mp4` en
`data/reels/`. Soporta tres "temas": `rive` (íconos abstractos, Rive
Intelligente), `aiassistant` (mockups reales de getaiassistant.app) y
`taskdoctor` (mockups reales de taskdoctor.ai) — guiones ya aprobados en
`orchestrator/tools/guiones_reels.py`, y todos los parámetros por defecto
(voz, ritmo/pausa, URL de cada producto) centralizados en
`orchestrator/tools/reels_defaults.py`, que tiene prioridad para el
agente. Sigue el mismo patrón de "nunca romper el arranque si falta
configuración" que el resto del orchestrator — las dependencias pesadas
(Pillow, moviepy, Azure Speech SDK, httpx para ElevenLabs) se importan de
forma perezosa, así que el resto del asistente funciona igual aunque no
estén instaladas.

Además del agente en el chat, hay una **herramienta web dedicada** en
`/reels` (ver `orchestrator/web/app.py` + `static/reels.html`, mismo login
que el chat): elegís producto, generás, y el video aparece en el
navegador con reproductor y descarga. Si `GOOGLE_DRIVE_REELS_FOLDER_ID`
está configurado, cada reel se sube solo a esa carpeta de Drive
(reutiliza `subir_a_drive` de `google_workspace.py`) — probado de punta a
punta contra una carpeta real. Corre en background (no bloquea el
servidor mientras renderiza) con polling desde el frontend.

El chat (`/`) tiene un **panel lateral con los 4 agentes** (`asistente`,
`ceo`, `recepcionista`, `productor_reels` — se arma solo desde
`/api/agentes`, nunca hardcodeado): elegís cuál usar y le hablás directo,
sin depender del enrutador automático. Cada agente tiene su propio
historial de conversación (probado: cambiar de agente y volver no mezcla
nada) — el servidor lo separa por `(invitado, agente)`.

Nota conocida: generar un reel de 4 beats con la voz HD falla de forma
intermitente con un crash nativo (`SIGILL`) — no es determinístico, el
mismo guion puede fallar una vez y funcionar al reintentar. No se encontró
la causa raíz; el workaround es simplemente reintentar.
