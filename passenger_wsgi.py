"""
Punto de entrada para Phusion Passenger (Application Manager de Bluehost).

Passenger detecta automáticamente si `application` es una app WSGI o ASGI
(Passenger >= 6 soporta ASGI de forma nativa) — no hace falta ningún
adaptador manual, basta con exponer la app de FastAPI como `application`.

Antes de activar esto en el panel de Bluehost, ver docs/DEPLOY_BLUEHOST.md
para la lista completa de pasos. Resumen:

  1. Crea la app Python en Application Manager, apuntando a la raíz de
     este repo, y deja que instale requirements.txt en su virtualenv.
  2. Copia .env.example a .env en el servidor y rellena los valores reales
     (nunca subas el .env real a git — ya está en .gitignore).
  3. Copia config/contacts.yaml.example -> config/contacts.yaml y
     config/invited_users.yaml.example -> config/invited_users.yaml, y
     agrega ahí los contactos/invitados reales.
  4. Define WEB_SESSION_SECRET en el .env del servidor (una cadena
     aleatoria larga) — si no lo defines, las sesiones se invalidan cada
     vez que Passenger reinicie el proceso (ver orchestrator/config.py).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator.web.app import app as application  # noqa: E402
