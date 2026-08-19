# android-bridge

Script que corre **en tu celular, dentro de Termux**, y ejecuta las
acciones que el orchestrator le encola vía `orchestrator/bridge/server.py`.

Ver `MANUAL_CONEXION.md` sección 4 para la instalación completa. Resumen:

```bash
pkg update && pkg install python git termux-api
pip install -r requirements.txt
export PHONE_BRIDGE_URL="http://100.x.x.x:8090"   # IP de Tailscale del servidor
export PHONE_BRIDGE_TOKEN="el-mismo-token-del-.env-del-servidor"
python scripts/listener.py
```

## Acciones soportadas hoy

| accion | parámetros | qué hace |
|---|---|---|
| `notificar` | `{"titulo": str, "texto": str}` | Muestra una notificación (`termux-notification`) |
| `leer_bateria` | `{}` | Devuelve nivel de batería (`termux-battery-status`) |
| `disparar_tasker` | `{"tarea": str}` | Ejecuta una tarea de Tasker por nombre vía intent |
| `hablar` | `{"texto": str}` | Lee el texto en voz alta (`termux-tts-speak`) |

Agrega nuevas acciones en `scripts/listener.py` → función `ejecutar_accion`.
Para automatizaciones más complejas (leer SMS, controlar apps de terceros),
combina esto con [Tasker](https://tasker.joaoapps.com/) + el plugin
AutoRemote, disparándolo con `disparar_tasker`.

## Arranque automático al reiniciar el teléfono

1. Instala **Termux:Boot** (F-Droid).
2. Crea `~/.termux/boot/start-listener.sh`:
   ```bash
   #!/data/data/com.termux/files/usr/bin/sh
   cd ~/AiAsistant/android-bridge
   python scripts/listener.py >> listener.log 2>&1
   ```
3. Dale permisos de ejecución: `chmod +x ~/.termux/boot/start-listener.sh`.
