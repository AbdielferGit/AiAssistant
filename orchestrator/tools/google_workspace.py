"""
Gmail + Drive vía API oficial de Google.

Requiere credentials.json (OAuth client "Desktop app") en la raíz del repo
y las variables GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET en .env.
Ver MANUAL_CONEXION.md sección 1.
"""
from __future__ import annotations

import base64
import os
from datetime import datetime, timezone
from email.mime.text import MIMEText
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from orchestrator import contacts

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/calendar.events",
]

TOKEN_PATH = Path("token.json")
CREDENTIALS_PATH = Path("credentials.json")


def _get_credentials() -> Credentials:
    creds: Credentials | None = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
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
