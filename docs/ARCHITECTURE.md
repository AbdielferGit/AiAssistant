# Arquitectura

```
 [Tú escribes]  (terminal o web)
      │
      ▼
┌──────────────────────────────────────────────────────────┐
│           orchestrator/ (Python, SDK oficial de Anthropic)│
│  - main.py / web/app.py: loop del agente, tool-use manual │
│  - router.py: Claude Haiku 4.5 elige qué agente atiende    │
│  - agents/: "asistente" (con tools) y "ceo" (sin tools)     │
│  - tools/: gmail, calendar, drive, whatsapp, messenger, mac│
│  - memory/: estilo de escritura (RAG) + ventana de 24h      │
└───────┬───────────────┬───────────────┬────────────────────┘
        ▼               ▼               ▼
  google_workspace.py  whatsapp.py    macos_actions.py
  (Gmail + Calendar +   messenger.py   (AppleScript /
   Drive, API oficial)  (Meta oficial)  Shortcuts, en tu Mac)
```

## Componentes

| Componente | Dónde corre | Tecnología |
|---|---|---|
| Orquestador (el "cerebro") | Tu Mac, local | Python + SDK oficial de Anthropic (`anthropic`), loop de tool-use manual, multi-agente con enrutamiento automático (ver `orchestrator/agents/` y `orchestrator/router.py`) |
| Gmail / Calendar / Drive | Tu Mac | Google API oficial (OAuth) |
| WhatsApp | Tu Mac | WhatsApp Cloud API (Meta, oficial) |
| Messenger | Tu Mac | Meta Messenger Platform (oficial, solo Páginas — ver `orchestrator/tools/messenger.py`) |
| Acciones en Mac | Tu Mac | AppleScript / Shortcuts CLI (`mac-bridge/`) |
| Memoria de estilo | Tu Mac | LanceDB (vectorial), respaldo opcional a Drive |
| Web (opcional, acceso remoto) | Render / Bluehost | `orchestrator/web/` — mismo cerebro, expuesto por HTTP |

Este proyecto es deliberadamente **solo local**: no hay puente a celular
(se quitó `bridge/` + `android-bridge/`) ni WhatsApp no oficial (se quitó
`whatsapp-bridge/`, el puente Baileys). Todo corre en tu Mac; la versión
web es la única forma de acceso remoto, y es opcional.

## Lista blanca de contactos (autorización en las dos direcciones)

`orchestrator/contacts.py` es la única fuente de verdad de a quién puede
hablarle el asistente y de quién puede aceptar mensajes. Se aplica en dos
puntos, no en uno solo:

- **Salida**: cada tool de canal (`tools/whatsapp.py`, `tools/google_workspace.py`,
  `tools/messenger.py`, `tools/macos_actions.py`) llama a
  `contacts.verificar_autorizado(...)` antes de enviar nada. Si el
  destinatario no está en `config/contacts.yaml` con `activo: true`, el
  envío se rechaza (`status: "rechazado"`) sin tocar la red.
- **Entrada**: `orchestrator/webhooks/whatsapp_cloud.py` (el webhook de
  WhatsApp entrante, opcional — ver `MANUAL_CONEXION.md` sección 2)
  descarta cualquier mensaje de alguien fuera de la lista ahí mismo —
  nunca se guarda, ni se usa como contexto, ni dispara nada.

Administra la lista con `python scripts/manage_contacts.py` (ver
`MANUAL_CONEXION.md` sección 0.5). El archivo real (`config/contacts.yaml`)
nunca se sube a git — solo la plantilla `contacts.yaml.example`.

## Flujo de un mensaje

1. Escribes algo — por terminal (`main.py`) o por la web (`web/app.py`).
2. El enrutador (`router.py`, Claude Haiku 4.5) decide qué agente atiende:
   "asistente" para tareas operativas, "ceo" para análisis puro.
3. El agente arma el prompt con: la instrucción, la fecha/hora actual
   (`agents/base.py`), y memoria de estilo si vas a redactar algo.
4. Claude decide si necesita una tool (`enviar_whatsapp`, `crear_evento_calendario`,
   `abrir_app_o_archivo_mac`, etc.) y la invoca.
5. **Si la acción es irreversible** (enviar WhatsApp/email/Messenger) el
   asistente muestra el borrador y espera tu confirmación explícita antes
   de ejecutar — por `input()` en terminal, por un modal en la web. Esto
   está reforzado en `orchestrator/main.py` / `orchestrator/web/app.py` —
   no lo quites.

## Versión web (acceso remoto, solo por invitación)

`orchestrator/web/` expone el mismo cerebro (agentes + `router.py`) por
HTTP en vez de por terminal, para no quedar atado a tu Mac. Login con
Google restringido a `config/invited_users.yaml` (lista aparte de
`config/contacts.yaml` — una controla quién puede *usar el chat*, la otra
a quién puede el asistente *contactar*). La única diferencia real de
comportamiento frente a `main.py`: cuando una tool es irreversible, el
turno no bloquea en `input()` — se pausa y el frontend muestra un modal
de confirmar/cancelar (`orchestrator/web/app.py` función
`_correr_turno_web`, endpoint `POST /api/chat/confirmar`). Es opcional —
si solo vas a usar la terminal, no hace falta tocar `orchestrator/web/`.

## ⚠️ Advertencia de diseño: WhatsApp y Messenger personales

No existe una API oficial de Meta para automatizar **tu cuenta personal**
de WhatsApp o Messenger actuando exactamente como tú — solo la vía oficial
(WhatsApp Business API / Meta Messenger Platform), que identifica al
remitente como una "empresa/página", no como tú. Este proyecto usa
deliberadamente solo esa vía oficial (`tools/whatsapp_cloud_api.py`,
`tools/messenger.py`) — se descartó la alternativa no oficial (Baileys)
para simplificar y evitar el riesgo de baneo que conlleva.
