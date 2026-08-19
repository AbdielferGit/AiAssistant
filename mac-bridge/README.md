# mac-bridge

AppleScripts invocados desde `orchestrator/tools/macos_actions.py` para
controlar iMessage, Mail, Calendar y apps nativas.

## Permisos necesarios (una sola vez)

**Preferencias del Sistema → Privacidad y Seguridad**:
- **Accesibilidad**: agrega Terminal (o tu IDE/proceso que corre Python).
- **Automatización**: la primera vez que un script controle Mensajes/Mail,
  macOS te pedirá autorizarlo — acepta.

## Probar un script suelto

```bash
osascript scripts/applescript/send_imessage.applescript "Hola, prueba" "+1234567890"
```

## Scripts incluidos

- `send_imessage.applescript` — envía un iMessage/SMS por Mensajes.app.
- `open_app.applescript` — abre una aplicación por nombre.

Agrega más `.applescript` aquí para Mail.app, Calendar.app, etc., y
expónlos como funciones en `orchestrator/tools/macos_actions.py`.
