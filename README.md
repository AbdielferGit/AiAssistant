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
├── passenger_wsgi.py         # Punto de entrada para Phusion Passenger (despliegue Bluehost)
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
│   │   └── receptionist.py       # Agente "recepcionista": representa a UN negocio (Accueil+), configurable por config/negocio.yaml
│   ├── tools/                 # "Herramientas" que el LLM puede invocar
│   │   ├── google_workspace.py  # Gmail + Calendar + Drive
│   │   ├── whatsapp.py          # Lista blanca + delega a whatsapp_cloud_api.py
│   │   ├── whatsapp_cloud_api.py # Cliente de la WhatsApp Cloud API (Meta, oficial)
│   │   ├── messenger.py         # Meta Messenger Platform (oficial, solo Páginas)
│   │   └── macos_actions.py     # AppleScript / Shortcuts desde Python
│   ├── memory/                 # Estilo de escritura + memoria vectorial
│   │   ├── vector_store.py
│   │   ├── style_profile.py
│   │   └── inbound_tracker.py    # Último mensaje entrante por remitente (ventana de 24h de WhatsApp)
│   ├── webhooks/                # Mensajes ENTRANTES de Meta (WhatsApp Cloud API)
│   │   └── whatsapp_cloud.py     # FastAPI: webhook del "recepcionista" — público, sin lista blanca, con límite de mensajes/hora (despliegue: Render)
│   └── web/                    # Versión web del "asistente" — acceso remoto solo por invitación (despliegue: Render)
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

## Estado actual

El **recepcionista** ya pasó un piloto real de punta a punta (WhatsApp real,
Meta Cloud API, desplegado en Render) y quedó validado como producto
funcional para un negocio cliente. El resto — Gmail/Calendar, Messenger,
acciones en Mac del **asistente** personal — sigue siendo el andamiaje
inicial: la estructura y los stubs están listos, pero cada integración
necesita que completes credenciales siguiendo `MANUAL_CONEXION.md` antes de
que funcione de punta a punta.
