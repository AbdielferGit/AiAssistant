# AiAsistant

Asistente personal por voz, entrenable, capaz de ejecutar acciones en tu Mac
y en tu celular Android, y de redactar mensajes con tu propio estilo.

## Empezar aquí

1. Lee [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) para entender cómo encajan las piezas.
2. Sigue [`MANUAL_CONEXION.md`](MANUAL_CONEXION.md) paso a paso para conectar Mac + Android + Google + WhatsApp.
3. Revisa [`docs/PRODUCT_ROADMAP.md`](docs/PRODUCT_ROADMAP.md) para la ruta de hosting y de convertir esto en producto vendible.

## Estructura del repo

```
AiAsistant/
├── MANUAL_CONEXION.md       # Manual paso a paso (Mac + Android + APIs)
├── docker-compose.yml       # Levanta orchestrator + puente de WhatsApp
├── .env.example             # Variables de entorno necesarias
├── config/
│   └── contacts.yaml.example # Plantilla de la lista blanca de contactos
├── orchestrator/            # Cerebro del asistente (Python, Claude Agent SDK)
│   ├── main.py               # Loop principal del agente
│   ├── config.py              # Carga de configuración/.env
│   ├── contacts.py            # Lista blanca — autoriza envío/recepción en ambas direcciones
│   ├── tools/                 # "Herramientas" que el LLM puede invocar
│   │   ├── google_workspace.py  # Gmail + Drive
│   │   ├── whatsapp.py          # Llama al puente de WhatsApp (Node/Baileys)
│   │   ├── messenger.py         # Stub documentado (ver advertencia de riesgo)
│   │   └── macos_actions.py     # AppleScript / Shortcuts desde Python
│   ├── memory/                 # Estilo de escritura + memoria vectorial
│   │   ├── vector_store.py
│   │   └── style_profile.py
│   └── bridge/                 # Bus de comandos hacia el celular
│       └── server.py            # FastAPI: cola de comandos para Android
├── whatsapp-bridge/          # Microservicio Node.js (Baileys) para WhatsApp
├── android-bridge/           # Instrucciones + script Termux para el celular
├── mac-bridge/                # AppleScripts para iMessage/Mail/Calendar
├── scripts/                  # Setup de Google Cloud, sync a Drive
└── data/                     # DB local (LanceDB/SQLite) — no se sube a git
```

## Estado actual

Esto es un **andamiaje inicial**: la estructura, el manual de conexión y los
stubs de código están listos. Cada integración (Google, WhatsApp, Android)
necesita que completes credenciales/pairing siguiendo el manual antes de
que funcione de punta a punta.
