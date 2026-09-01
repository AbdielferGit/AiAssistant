"""
Gmail + Drive + Calendar vía API oficial de Google.

Localmente (terminal, `python -m orchestrator.main`): requiere
credentials.json (OAuth client "Desktop app") en la raíz del repo — la
primera vez abre un navegador para autorizar de forma interactiva y deja
el resultado cacheado en token.json. Ver MANUAL_CONEXION.md sección 1.

En un servidor sin navegador ni disco persistente (ej. orchestrator/web/
desplegado en Render free tier) ese flujo interactivo no se puede correr
ahí. En su lugar: autoriza una vez en tu Mac como siempre, y pega el
CONTENIDO completo de token.json (ya generado) en la variable de entorno
GOOGLE_TOKEN_JSON del hosting — mismo patrón que CONTACTS_YAML /
INVITED_USERS_YAML (ver orchestrator/contacts.py). El `refresh_token`
dentro de ese JSON es lo que permite renovar el acceso sin volver a pasar
por el navegador.

Nota: mientras el proyecto de Google Cloud esté en modo "Testing" (no
publicado), los refresh tokens expiran cada 7 días — si listar_eventos u
otras tools empiezan a fallar, vuelve a autorizar en tu Mac y actualiza
GOOGLE_TOKEN_JSON con el token.json nuevo. Publicar la app en modo "In
production" (OAuth consent screen → Publish app) evita esto para los
scopes no sensibles que usa este repo.
"""
from __future__ import annotations

import base64
import json
import logging
import os
from datetime import datetime, timezone
from email.mime.text import MIMEText
from pathlib import Path

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from orchestrator import contacts

log = logging.getLogger("orchestrator.google_workspace")

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/calendar.events",
]

TOKEN_PATH = Path("token.json")
CREDENTIALS_PATH = Path("credentials.json")


def _cargar_desde_variable_de_entorno() -> Credentials | None:
    contenido = os.getenv("GOOGLE_TOKEN_JSON", "")
    if not contenido:
        return None
    return Credentials.from_authorized_user_info(json.loads(contenido), SCOPES)


def _get_credentials() -> Credentials:
    origen_es_archivo = TOKEN_PATH.exists()
    creds: Credentials | None = None
    if origen_es_archivo:
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    else:
        creds = _cargar_desde_variable_de_entorno()

    if creds and not creds.valid and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            if origen_es_archivo:
                TOKEN_PATH.write_text(creds.to_json())
            # Si venía de GOOGLE_TOKEN_JSON no hay dónde persistir el
            # access_token renovado (el entorno no es editable en runtime) —
            # no pasa nada, se vuelve a refrescar con el mismo
            # refresh_token en la próxima llamada.
        except RefreshError as exc:
            if not origen_es_archivo:
                raise RuntimeError(
                    "GOOGLE_TOKEN_JSON no se pudo refrescar "
                    f"({exc}) — posiblemente expiró (los refresh tokens de "
                    "apps en modo 'Testing' duran 7 días). Vuelve a "
                    "autorizar en tu Mac (python -m orchestrator.main) y "
                    "actualiza la variable de entorno con el token.json "
                    "nuevo."
                ) from exc
            # En tu Mac SÍ hay navegador a mano: en vez de romper la tool,
            # se descarta el token vencido y se cae al flujo interactivo de
            # abajo (mismo camino que si token.json nunca hubiera existido).
            log.warning("El refresh_token de Google fue rechazado (%s) — pido autorización de nuevo.", exc)
            creds = None

    if not creds or not creds.valid:
        if os.getenv("GOOGLE_TOKEN_JSON") and not origen_es_archivo:
            raise RuntimeError(
                "GOOGLE_TOKEN_JSON no tiene un token válido — vuelve a "
                "autorizar en tu Mac (python -m orchestrator.main) y "
                "actualiza la variable de entorno con el token.json nuevo."
            )
        if not CREDENTIALS_PATH.exists():
            raise RuntimeError(
                "Falta credentials.json — descárgalo desde Google Cloud "
                "Console siguiendo MANUAL_CONEXION.md sección 1."
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
        creds = flow.run_local_server(port=8080)
        TOKEN_PATH.write_text(creds.to_json())
    return creds


def enviar_email(destinatario: str, asunto: str, cuerpo: str) -> dict:
    """Rechaza el envío si `destinatario` no está en la lista blanca activa
    (config/contacts.yaml) — ver orchestrator/contacts.py."""
    try:
        contacto = contacts.verificar_autorizado("email", destinatario)
    except contacts.ContactoNoAutorizado as e:
        return {"status": "rechazado", "motivo": str(e)}

    service = build("gmail", "v1", credentials=_get_credentials())
    mensaje = MIMEText(cuerpo)
    mensaje["to"] = destinatario
    mensaje["subject"] = asunto
    raw = base64.urlsafe_b64encode(mensaje.as_bytes()).decode()
    enviado = service.users().messages().send(userId="me", body={"raw": raw}).execute()
    return {"status": "enviado", "id": enviado.get("id"), "contacto": contacto.nombre}


def _extraer_cuerpo_texto(payload: dict) -> str:
    """Busca la parte text/plain en el payload (posiblemente multipart) de
    un mensaje de Gmail y la decodifica. Si no hay text/plain, se queda
    vacío — el snippet de la API sirve de respaldo (ver leer_correos)."""
    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        datos = payload["body"]["data"]
        relleno = "=" * (-len(datos) % 4)
        return base64.urlsafe_b64decode(datos + relleno).decode("utf-8", errors="replace")
    for parte in payload.get("parts") or []:
        texto = _extraer_cuerpo_texto(parte)
        if texto:
            return texto
    return ""


def leer_correos(cantidad: int = 1) -> dict:
    """Lee (nunca modifica) los correos más recientes de la bandeja de
    entrada. Requiere el scope gmail.readonly — si el token actual solo
    tiene gmail.send (de antes de agregar esta tool), falla con un 403 y
    hay que reautorizar para que Google incluya el scope nuevo."""
    service = build("gmail", "v1", credentials=_get_credentials())
    resultado = service.users().messages().list(userId="me", labelIds=["INBOX"], maxResults=cantidad).execute()
    correos = []
    for m in resultado.get("messages", []):
        detalle = service.users().messages().get(userId="me", id=m["id"], format="full").execute()
        headers = {h["name"].lower(): h["value"] for h in detalle.get("payload", {}).get("headers", [])}
        cuerpo = _extraer_cuerpo_texto(detalle.get("payload", {})) or detalle.get("snippet", "")
        correos.append(
            {
                "id": m["id"],
                "de": headers.get("from", ""),
                "asunto": headers.get("subject", "(sin asunto)"),
                "fecha": headers.get("date", ""),
                "cuerpo": cuerpo[:3000],
            }
        )
    return {"correos": correos}


def crear_evento(titulo: str, inicio_iso: str, fin_iso: str) -> dict:
    service = build("calendar", "v3", credentials=_get_credentials())
    evento = {
        "summary": titulo,
        "start": {"dateTime": inicio_iso},
        "end": {"dateTime": fin_iso},
    }
    creado = service.events().insert(calendarId="primary", body=evento).execute()
    return {"status": "creado", "link": creado.get("htmlLink")}


def listar_eventos(desde_iso: str | None = None, hasta_iso: str | None = None, max_resultados: int = 10) -> dict:
    """Lee (nunca modifica) los próximos eventos del calendario principal.
    Si `desde_iso` no se da, busca desde el momento actual; si `hasta_iso`
    no se da, no hay límite superior (Google devuelve los siguientes
    `max_resultados` eventos en orden cronológico a partir de `desde_iso`).
    Usa el mismo scope `calendar.events` que `crear_evento` — no hace falta
    volver a autorizar nada."""
    service = build("calendar", "v3", credentials=_get_credentials())
    parametros = {
        "calendarId": "primary",
        "timeMin": desde_iso or datetime.now(timezone.utc).isoformat(),
        "maxResults": max_resultados,
        "singleEvents": True,
        "orderBy": "startTime",
    }
    if hasta_iso:
        parametros["timeMax"] = hasta_iso
    resultado = service.events().list(**parametros).execute()
    eventos = [
        {
            "id": e.get("id"),
            "titulo": e.get("summary", "(sin título)"),
            "inicio": e.get("start", {}).get("dateTime") or e.get("start", {}).get("date"),
            "fin": e.get("end", {}).get("dateTime") or e.get("end", {}).get("date"),
            "ubicacion": e.get("location", ""),
            "link": e.get("htmlLink"),
        }
        for e in resultado.get("items", [])
    ]
    return {"eventos": eventos}


def eliminar_evento(evento_id: str) -> dict:
    """Borra un evento del calendario principal por su id (el campo `id`
    que devuelve `listar_eventos`). Usa el mismo scope `calendar.events`
    que crear_evento/listar_eventos."""
    service = build("calendar", "v3", credentials=_get_credentials())
    try:
        service.events().delete(calendarId="primary", eventId=evento_id).execute()
    except HttpError as exc:
        if exc.resp.status == 410:
            # Ya estaba borrado (o nunca existió) — no es un error real.
            return {"status": "ya_no_existia", "evento_id": evento_id}
        raise
    return {"status": "eliminado", "evento_id": evento_id}


def subir_a_drive(ruta_local: str, carpeta_id: str) -> dict:
    """Sube (o actualiza) un archivo local a la carpeta de Drive usada como
    respaldo de la base de datos. Ver docs/PRODUCT_ROADMAP.md sobre los
    límites de usar Drive como almacenamiento de datos."""
    from googleapiclient.http import MediaFileUpload

    service = build("drive", "v3", credentials=_get_credentials())
    nombre = os.path.basename(ruta_local)
    media = MediaFileUpload(ruta_local, resumable=True)

    existentes = (
        service.files()
        .list(q=f"name='{nombre}' and '{carpeta_id}' in parents and trashed=false")
        .execute()
        .get("files", [])
    )
    if existentes:
        archivo = service.files().update(fileId=existentes[0]["id"], media_body=media).execute()
    else:
        metadata = {"name": nombre, "parents": [carpeta_id]}
        archivo = service.files().create(body=metadata, media_body=media).execute()
    return {"status": "sincronizado", "file_id": archivo.get("id")}
