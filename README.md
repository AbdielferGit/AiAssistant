# AiAssistant

Asistente personal — Google (email + calendario), WhatsApp/Messenger
(Meta oficial) y acciones en tu Mac. Se usa desde la terminal, en local.

## Empezar aquí

1. Lee [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) para entender cómo encajan las piezas.
2. Sigue [`MANUAL_CONEXION.md`](MANUAL_CONEXION.md) paso a paso para conectar Google + WhatsApp/Messenger + Mac.
3. Para usarlo desde el navegador (no solo terminal), ve
   [`docs/DEPLOY_BLUEHOST.md`](docs/DEPLOY_BLUEHOST.md) — despliegue en
   Bluehost con login por invitación (`orchestrator/web/`).

## Estructura del repo

```
AiAssistant/
├── MANUAL_CONEXION.md       # Manual paso a paso (Google + WhatsApp/Messenger + Mac)
├── .env.example             # Variables de entorno necesarias
├── passenger_wsgi.py         # Punto de entrada para Phusion Passenger (despliegue Bluehost)
├── config/
│   ├── contacts.yaml.example        # Plantilla de la lista blanca de contactos
│   └── invited_users.yaml.example   # Plantilla de la lista de invitados a la web
├── orchestrator/            # Cerebro del asistente (Python, SDK oficial de Anthropic)
│   ├── main.py               # Loop genérico de tool-use por terminal — no conoce ningún agente en particular
│   ├── router.py              # Antes de responder, elige (con Haiku) qué agente le toca al mensaje
│   ├── config.py              # Carga de configuración/.env
│   ├── contacts.py            # Lista blanca — autoriza envío/recepción en ambas direcciones
│   ├── agents/                 # Agentes — se autodescubren, no hace falta tocar el orchestrator
│   │   ├── base.py               # Clase plantilla Agent_0 — instánciala para crear un agente nuevo
│   │   ├── personal_assistant.py # Agente "asistente" (predeterminado): envía, redacta, agenda
│   │   └── ceo_analyst.py        # Agente "ceo": Analista de CEO, sin tools (puro análisis)
│   ├── tools/                 # "Herramientas" que el LLM puede invocar
│   │   ├── google_workspace.py  # Gmail + Calendar + Drive
│   │   ├── whatsapp.py          # Lista blanca + delega a whatsapp_cloud_api.py
│   │   ├── whatsapp_cloud_api.py # Cliente de la WhatsApp Cloud API (Meta, oficial)
│   │   ├── messenger.py         # Meta Messenger Platform (oficial, solo Páginas)
│   │   └── macos_actions.py     # AppleScript / Shortcuts desde Python
│   ├── memory/                 # Estilo de escritura + memoria vectorial
│   │   ├── vector_store.py
│   │   └── style_profile.py
│   ├── webhooks/                # Mensajes ENTRANTES de Meta (WhatsApp Cloud API)
│   │   └── whatsapp_cloud.py     # FastAPI: webhook de verificación + inbound
│   └── web/                    # Versión web — acceso remoto solo por invitación
│       ├── app.py                # FastAPI: login, chat (mismo router/agentes que main.py), confirmar/cancelar
│       ├── auth.py                # Google Sign-In + cookie de sesión firmada
│       ├── invites.py             # Lista blanca de quién puede iniciar sesión
│       └── static/                # login.html + index.html (frontend mínimo, sin build)
├── mac-bridge/                # AppleScripts para iMessage/Mail/Calendar
├── scripts/                  # Setup de Google Cloud, sync a Drive
└── data/                     # DB local (LanceDB/SQLite) — no se sube a git
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

## Estado actual

Esto es un **andamiaje inicial**: la estructura, el manual de conexión y los
stubs de código están listos. Cada integración (Google, WhatsApp/Messenger)
necesita que completes credenciales siguiendo el manual antes de que
funcione de punta a punta.
