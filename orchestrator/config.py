"""Carga de configuración desde .env — un solo lugar para todas las variables."""
from __future__ import annotations

import logging
import os
import secrets
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger("orchestrator.config")


def _require(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if not value:
        raise RuntimeError(
            f"Falta la variable de entorno {name!r}. Revisa tu archivo .env "
            f"(copia .env.example si aún no lo has hecho)."
        )
    return value


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str
    anthropic_model: str
    google_client_id: str
    google_client_secret: str
    google_drive_db_folder_id: str
    whatsapp_provider: str  # "cloud_api" (oficial, recomendado para pruebas) | "baileys" (no oficial)
    whatsapp_bridge_url: str
    whatsapp_bridge_token: str
    whatsapp_cloud_api_token: str
    whatsapp_cloud_api_phone_number_id: str
    whatsapp_cloud_api_verify_token: str
    phone_bridge_host: str
    phone_bridge_port: int
    phone_bridge_token: str
    messenger_page_access_token: str
    vector_db_path: str
    inbound_tracker_path: str
    web_session_secret: str

    @classmethod
    def load(cls) -> "Settings":
        web_session_secret = os.getenv("WEB_SESSION_SECRET", "")
        if not web_session_secret:
            # No es fatal: generamos una efímera para que `python -m
            # orchestrator.main` y pruebas locales no se rompan. Pero en
            # producción (orchestrator/web/, passenger_wsgi.py) esto
            # significa que TODAS las sesiones se invalidan cada vez que el
            # proceso reinicia — define WEB_SESSION_SECRET en el .env real
            # antes de exponer la web a nadie más que a ti.
            web_session_secret = secrets.token_urlsafe(32)
            log.warning(
                "WEB_SESSION_SECRET no está definida en .env — usando una "
                "clave aleatoria de un solo uso (las sesiones web no "
                "sobrevivirán a un reinicio). Defínela antes de desplegar."
            )
        return cls(
            anthropic_api_key=_require("ANTHROPIC_API_KEY"),
            anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5"),
            google_client_id=os.getenv("GOOGLE_CLIENT_ID", ""),
            google_client_secret=os.getenv("GOOGLE_CLIENT_SECRET", ""),
            google_drive_db_folder_id=os.getenv("GOOGLE_DRIVE_DB_FOLDER_ID", ""),
            whatsapp_provider=os.getenv("WHATSAPP_PROVIDER", "cloud_api"),
            whatsapp_bridge_url=os.getenv("WHATSAPP_BRIDGE_URL", "http://localhost:4001"),
            whatsapp_bridge_token=os.getenv("WHATSAPP_BRIDGE_TOKEN", ""),
            whatsapp_cloud_api_token=os.getenv("WHATSAPP_CLOUD_API_TOKEN", ""),
            whatsapp_cloud_api_phone_number_id=os.getenv("WHATSAPP_CLOUD_API_PHONE_NUMBER_ID", ""),
            whatsapp_cloud_api_verify_token=os.getenv("WHATSAPP_CLOUD_API_VERIFY_TOKEN", ""),
            phone_bridge_host=os.getenv("PHONE_BRIDGE_HOST", "0.0.0.0"),
            phone_bridge_port=int(os.getenv("PHONE_BRIDGE_PORT", "8090")),
            phone_bridge_token=os.getenv("PHONE_BRIDGE_TOKEN", ""),
            messenger_page_access_token=os.getenv("MESSENGER_PAGE_ACCESS_TOKEN", ""),
            vector_db_path=os.getenv("VECTOR_DB_PATH", "./data/vector_store"),
            inbound_tracker_path=os.getenv("INBOUND_TRACKER_PATH", "./data/whatsapp_last_inbound.json"),
            web_session_secret=web_session_secret,
        )


settings = Settings.load()
