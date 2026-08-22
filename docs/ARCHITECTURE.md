# Arquitectura

```
 [Tú hablas]                                   [Tu celular Android]
      │                                                │
      ▼                                                ▼
 Wake word + STT                              android-bridge/ (Termux)
 (Mac o servidor)                              escucha comandos, ejecuta
      │                                        notificaciones/Tasker/SMS
      ▼                                                ▲
┌─────────────────────────────────────────────────────┴───┐
│           orchestrator/ (Python, SDK oficial de Anthropic)│
│  - main.py: loop del agente, decide qué "tool" llamar     │
│  - tools/: gmail, drive, whatsapp, messenger, macOS        │
│  - memory/: estilo de escritura (RAG) + contexto           │
│  - bridge/server.py: cola de comandos para el celular      │
└───────┬───────────────┬───────────────┬───────────────────┘
        ▼               ▼               ▼
  google_workspace.py  whatsapp.py    macos_actions.py
  (Gmail + Drive,      (llama a       (AppleScript /
   API oficial)         whatsapp-      Shortcuts, corre
                         bridge/ Node)  en tu Mac)
```

## Componentes

| Componente | Dónde corre | Tecnología |
|---|---|---|
| Captura de voz (wake word + STT) | Mac (o servidor si migras) | Porcupine + whisper.cpp |
| Orquestador (el "cerebro") | Servidor / Mac | Python + SDK oficial de Anthropic (`anthropic`), loop de tool-use manual, multi-agente con enrutamiento automático (ver `orchestrator/agents/` y `orchestrator/router.py`) |
| Gmail / Drive | Servidor | Google API oficial (OAuth) |
| WhatsApp | Servidor (proceso Node siempre activo) | Baileys (no oficial — ver advertencia abajo) |
| Messenger | Servidor | Meta Messenger Platform (oficial, solo Páginas — ver `orchestrator/tools/messenger.py`) |
| Acciones en Mac | Mac | AppleScript / Shortcuts CLI |
| Acciones en Android | Celular | Termux + Termux:API, hace polling al `bridge/server.py` |
| Memoria de estilo | Servidor | LanceDB (vectorial) + respaldo periódico a Drive |

## Lista blanca de contactos (autorización en las dos direcciones)

`orchestrator/contacts.py` es la única fuente de verdad de a quién puede
hablarle el asistente y de quién puede aceptar mensajes. Se aplica en dos
puntos, no en uno solo:

- **Salida**: cada tool de canal (`tools/whatsapp.py`, `tools/google_workspace.py`,
  `tools/messenger.py`, `tools/macos_actions.py`) llama a
  `contacts.verificar_autorizado(...)` antes de enviar nada. Si el
  destinatario no está en `config/contacts.yaml` con `activo: true`, el
  envío se rechaza (`status: "rechazado"`) sin tocar la red.
- **Entrada**: `orchestrator/bridge/server.py` expone `/inbound/{canal}`;
  cualquier mensaje entrante de alguien fuera de la lista se descarta ahí
  mismo — nunca se guarda, ni se usa como contexto, ni dispara nada.
  `whatsapp-bridge/index.js` aplica el mismo filtro como segunda capa antes
  de siquiera reenviar el mensaje al orchestrator.

Administra la lista con `python scripts/manage_contacts.py` (ver
`MANUAL_CONEXION.md` sección 0.5). El archivo real (`config/contacts.yaml`)
nunca se sube a git — solo la plantilla `contacts.yaml.example`.

## Flujo de un comando de voz

1. Hablas → wake word lo activa → STT transcribe.
2. El texto llega al `orchestrator`, que arma el prompt con: la instrucción,
   memoria relevante (tools/memory) y ejemplos de tu estilo si vas a redactar
   algo.
3. Claude decide si necesita una tool (`enviar_whatsapp`, `crear_evento`,
   `abrir_app_android`, etc.) y la invoca.
4. **Si la acción es irreversible** (enviar mensaje, publicar, comprar) el
   asistente muestra el borrador y espera tu confirmación explícita antes de
   ejecutar. Esto está reforzado en `orchestrator/main.py` — no lo quites.
5. Para acciones en el celular, el orchestrator encola un comando en
   `bridge/server.py`; `android-bridge/scripts/listener.py` (corriendo en
   Termux) hace polling y lo ejecuta.

## WhatsApp: dos proveedores intercambiables

`orchestrator/tools/whatsapp.py` es un despachador controlado por
`WHATSAPP_PROVIDER` en `.env` — la verificación de lista blanca ocurre ahí
una sola vez, antes de elegir proveedor:

- `cloud_api` (por defecto): WhatsApp Cloud API oficial de Meta, sin QR,
  usando el "número de prueba" gratuito mientras validas el sistema (ver
  MANUAL_CONEXION.md sección 3a). Limitación: solo texto libre dentro de
  una ventana de 24h desde el último mensaje entrante de ese contacto
  (`orchestrator/memory/inbound_tracker.py`), y solo a los hasta 5 números
  "tester" que agregues en el panel de Meta mientras el número siga en
  modo prueba.
- `baileys`: el puente no oficial (`whatsapp-bridge/`) de la sección
  anterior, para cuando decidas actuar desde tu número personal real.

## ⚠️ Advertencia de diseño: WhatsApp y Messenger personales

No existe una API oficial de Meta para automatizar **tu cuenta personal** de
WhatsApp o Messenger actuando exactamente como tú. Las opciones son:

- **No oficiales** (Baileys para WhatsApp, `fca-unofficial` para Messenger):
  funcionan, son las que usa este scaffold, pero violan los Términos de
  Servicio de Meta — riesgo de baneo de tu número/cuenta. Aceptable para tu
  uso personal si lo asumes conscientemente; **no recomendable como base de
  un producto que vendas a terceros** (ver `docs/PRODUCT_ROADMAP.md`).
- **Oficiales**: WhatsApp Business API (via Meta o un BSP como Twilio/360dialog)
  y Meta Messenger Platform — pero identifican al remitente como una
  "empresa/página", no como tú personalmente. Es el camino correcto si esto
  se convierte en un producto para clientes.

Este scaffold usa la vía no oficial para tu prototipo personal, con el
puente aislado en su propio microservicio (`whatsapp-bridge/`) para poder
reemplazarlo por la vía oficial sin tocar el resto del sistema.
