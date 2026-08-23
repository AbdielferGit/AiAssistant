"""
Autenticación de la web — Google Sign-In restringido a la lista de
invitados (`orchestrator/web/invites.py`).

Flujo: el frontend (`orchestrator/web/static/login.html`) usa Google
Identity Services (el botón oficial "Sign in with Google") y nos manda el
`credential` que genera (un ID token JWT) por POST a /auth/google. Aquí lo
verificamos CONTRA GOOGLE (firma + que la audiencia sea nuestro
GOOGLE_CLIENT_ID) y, solo si el correo verificado está en la lista de
invitados activos, abrimos una sesión — una cookie firmada (itsdangerous),
nunca un token que el navegador pudiera falsificar o reutilizar para otra
cuenta.

No hay contraseñas propias ni registro: la identidad la garantiza Google,
la autorización la garantiza `invites.py`.
"""
from __future__ import annotations

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from itsdangerous import BadSignature, URLSafeTimedSerializer

from orchestrator.config import settings
from orchestrator.web import invites

COOKIE_NAME = "aiassistant_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 30  # 30 días

_serializer = URLSafeTimedSerializer(settings.web_session_secret, salt="aiassistant-web-session")


class LoginRechazado(Exception):
    """El token de Google es válido, pero el correo no está invitado (o
    está desactivado). Distinto de un token inválido/falsificado."""


def verificar_credential_google(credential: str) -> dict:
    """Verifica el ID token de Google Identity Services y devuelve
    {"correo", "nombre"} SOLO si el correo está en la lista de invitados
    activos.

    Lanza ValueError si el token no es válido (firma, audiencia o emisor
    incorrectos — típico de un token falsificado o expirado). Lanza
    LoginRechazado si el token es legítimo pero el correo no está
    invitado."""
    datos = id_token.verify_oauth2_token(
        credential, google_requests.Request(), settings.google_client_id
    )
    correo = datos.get("email", "")
    if not datos.get("email_verified"):
        raise ValueError("Correo de Google no verificado")

    invitado = invites.esta_invitado(correo)
    if invitado is None:
        raise LoginRechazado(f"'{correo}' no está en la lista de invitados de AiAssistant.")
    return {"correo": invitado.correo, "nombre": invitado.nombre or datos.get("name", "")}


def crear_cookie_sesion(sesion: dict) -> str:
    return _serializer.dumps(sesion)


def leer_sesion(cookie_valor: str | None) -> dict | None:
    """Nunca lanza: una cookie ausente, corrupta, falsificada o expirada
    simplemente cuenta como "no autenticado", igual que no tener cookie."""
    if not cookie_valor:
        return None
    try:
        return _serializer.loads(cookie_valor, max_age=SESSION_MAX_AGE)
    except BadSignature:
        return None
