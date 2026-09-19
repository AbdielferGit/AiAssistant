"""Waitlist propia + tracking de leads para Meta (Instagram/Facebook Ads).

DESCONECTADO desde 2026-09-19 — ver el docstring de orchestrator/web/
routers/leads.py. La landing real de TaskDoctor ya no vive en este repo ni
le pega a esto; quedó intacto por si hace falta reactivarlo.

Por qué existe esto: taskdoctor.ai no es nuestro — somos partners del
desarrollador, no tenemos acceso a su código para instalarle el Meta Pixel
ni su Conversions API (ver conversación del 2026-09-19). En vez de eso,
armamos nuestra PROPIA landing page + waitlist (orchestrator/web/static/
lp_taskdoctor.html + las rutas /leads/taskdoctor y /api/leads/* de
orchestrator/web/app.py) que sí controlamos de punta a punta — con eso
tenemos tanto el Pixel del lado del navegador como la Conversions API del
lado del servidor (algo que taskdoctor.ai no podía dar, porque su
formulario manda el email directo del navegador a Supabase, sin pasar por
ningún servidor propio).

Dos capas de tracking, con el MISMO event_id para deduplicar (ver
"Event Deduplication" de Meta — si el mismo evento llega por Pixel Y por
Conversions API con distinto event_id, Meta lo cuenta DOS veces):
  1. Cliente (lp_taskdoctor.html): dispara fbq('track', 'Lead', {}, {eventID}).
  2. Servidor (esta función, vía /api/leads/taskdoctor): reenvía el mismo
     evento con el mismo event_id a la Conversions API — sobrevive
     bloqueadores de anuncios / Safari ITP, y es la señal de mayor calidad
     que puede recibir el Advantage+ Audience de Meta.

Requiere en .env (ambas opcionales — si faltan, se guarda el lead local
igual, simplemente no se manda nada a Meta):
  META_PIXEL_ID           — Events Manager -> tu pixel -> Configuración.
  META_CAPI_ACCESS_TOKEN  — Events Manager -> tu pixel -> Conversions API
                             -> "Generate access token" (token de sistema,
                             no el de usuario — no expira mientras no lo
                             revoques).

Verificado en vivo (2026-09-19): endpoint y versión de la Graph API según
developers.facebook.com — Meta retira versiones viejas ~cada 3-4 meses,
si esto empieza a fallar con 400, subir META_CAPI_VERSION."""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from pathlib import Path

log = logging.getLogger("orchestrator.tools.leads")

REPO_ROOT = Path(__file__).resolve().parents[2]
LEADS_DIR = REPO_ROOT / "data" / "leads"

META_CAPI_VERSION = "v25.0"
META_CAPI_URL = "https://graph.facebook.com/{version}/{pixel_id}/events"

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Mismos valores que ofrece el <select> del formulario (lp_taskdoctor.html /
# TaskDoctorLanding.tsx) — cualquier otra cosa se descarta en vez de
# guardarse tal cual, mismo criterio que CRM.statuses en el Apps Script de
# Rive Intelligente (crm/apps-script/Code.gs).
URGENCIAS_VALIDAS = {"early_access", "automate_now", "find_opportunities", "exploring"}

# Ventana de dedup + honeypot: mismo criterio anti-spam que ya probó
# funcionar en crm/apps-script/Code.gs (RiveIntelligente) — acá en memoria
# porque este proceso no tiene una CacheService compartida. Se resetea en
# cada redeploy, es intencional: es para frenar doble-submit/spam en
# ráfaga, no un registro de auditoría (eso es data/leads/*.jsonl).
_VENTANA_DUPLICADO_SEG = 600
_leads_recientes: dict[str, float] = {}


def _limpiar(valor: object, largo_max: int) -> str:
    """Recorta y despoja caracteres de control — mismo criterio que
    `clean_()` en el Apps Script de RiveIntelligente. Nunca confiar en
    texto libre del cliente sin pasar por acá antes de guardarlo o
    reenviarlo a un tercero (Meta)."""
    texto = "" if valor is None else str(valor)
    texto = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", texto)
    return texto.strip()[:largo_max]


def _validar_email(email: str) -> str:
    email = _limpiar(email, 254)
    if not _EMAIL_RE.match(email):
        raise ValueError(f"Email inválido: {email!r}")
    return email


def _es_duplicado_reciente(email: str) -> bool:
    """True si este email ya registró un lead en los últimos 10 minutos —
    evita que un doble-click (o un bot insistente) genere múltiples
    eventos reales hacia la Conversions API de Meta. Purga oportunista de
    entradas vencidas para no crecer sin límite en un proceso long-lived."""
    ahora = time.time()
    for clave, vencimiento in list(_leads_recientes.items()):
        if vencimiento < ahora:
            del _leads_recientes[clave]

    clave = hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()
    if clave in _leads_recientes:
        return True
    _leads_recientes[clave] = ahora + _VENTANA_DUPLICADO_SEG
    return False


def _hash_sha256(valor: str) -> str:
    """Meta exige minúsculas + sin espacios antes de hashear (ver
    "Customer information parameters" de la Conversions API) — el mismo
    email en dos formatos distintos (mayúsculas/espacios) da un hash
    distinto y Meta no lo reconoce como la misma persona."""
    return hashlib.sha256(valor.strip().lower().encode("utf-8")).hexdigest()


def guardar_lead_local(campana: str, datos: dict) -> Path:
    """Guarda el lead en data/leads/{campana}.jsonl (una línea JSON por
    lead, se puede abrir con cualquier visor de JSONL o importar a una
    hoja de cálculo). OJO si esto corre en Render free tier: el disco es
    efímero, un redeploy/reinicio lo borra — para producción real, subir
    también a Google Drive (como ya hacemos con los reels) o a una hoja de
    cálculo, no confiar solo en este archivo local."""
    LEADS_DIR.mkdir(parents=True, exist_ok=True)
    ruta = LEADS_DIR / f"{campana}.jsonl"
    with ruta.open("a", encoding="utf-8") as f:
        f.write(json.dumps(datos, ensure_ascii=False) + "\n")
    return ruta


def enviar_evento_meta_capi(
    *,
    pixel_id: str,
    access_token: str,
    event_id: str,
    email: str,
    event_source_url: str,
    client_ip: str | None = None,
    client_user_agent: str | None = None,
    fbp: str | None = None,
    fbc: str | None = None,
    test_event_code: str | None = None,
) -> dict:
    """Manda un evento "Lead" server-side a la Conversions API de Meta.
    `event_id` DEBE ser el mismo que usó el fbq('track', ...) del lado del
    navegador para esta misma conversión — así Meta deduplica en vez de
    contar el lead dos veces."""
    import httpx

    user_data = {"em": [_hash_sha256(email)]}
    if client_ip:
        user_data["client_ip_address"] = client_ip
    if client_user_agent:
        user_data["client_user_agent"] = client_user_agent
    if fbp:
        user_data["fbp"] = fbp
    if fbc:
        user_data["fbc"] = fbc

    payload = {
        "data": [
            {
                "event_name": "Lead",
                "event_time": int(time.time()),
                "event_id": event_id,
                "event_source_url": event_source_url,
                "action_source": "website",
                "user_data": user_data,
            }
        ],
    }
    if test_event_code:
        # Para probar en Events Manager -> Conversions API -> "Test events"
        # sin que el evento cuente como real en las campañas.
        payload["test_event_code"] = test_event_code

    url = META_CAPI_URL.format(version=META_CAPI_VERSION, pixel_id=pixel_id)
    try:
        resp = httpx.post(url, params={"access_token": access_token}, json=payload, timeout=15)
    except httpx.HTTPError as exc:
        log.warning("Conversions API no respondió: %s", exc)
        return {"status": "error", "detalle": f"No se pudo contactar a Meta: {exc}"}

    if resp.status_code >= 400:
        log.warning("Conversions API devolvió %s: %s", resp.status_code, resp.text)
        return {"status": "error", "detalle": f"Meta devolvió {resp.status_code}: {resp.text[:300]}"}

    return {"status": "enviado", "respuesta": resp.json()}


def registrar_lead_taskdoctor(
    *,
    email: str,
    event_id: str,
    event_source_url: str,
    urgency: str | None = None,
    fuente: str | None = None,
    client_ip: str | None = None,
    client_user_agent: str | None = None,
    fbp: str | None = None,
    fbc: str | None = None,
    pixel_id: str | None = None,
    access_token: str | None = None,
    honeypot: str | None = None,
) -> dict:
    """Orquesta un lead completo de la waitlist propia de TaskDoctor:
    valida el email, lo guarda local, y si hay Pixel/token configurados,
    lo reenvía a la Conversions API. `pixel_id`/`access_token` normalmente
    vienen de settings (ver orchestrator/config.py) — se pasan explícitos
    acá para que esta función no dependa de importar config y sea fácil
    de probar sola.

    `honeypot`: campo señuelo del formulario (ej. name="website") que un
    humano nunca completa pero un bot casi siempre sí — mismo patrón que
    ya prueba funcionar en crm/apps-script/Code.gs de RiveIntelligente.
    Si viene con contenido, se responde éxito SIN guardar nada ni gastar
    la llamada a Meta — no delatarle al bot que lo detectamos."""
    if _limpiar(honeypot, 200):
        log.info("Lead descartado por honeypot (probable bot).")
        return {"status": "guardado", "local": None, "meta_capi": {"status": "omitido", "detalle": "honeypot"}}

    email = _validar_email(email)
    event_id = _limpiar(event_id, 100) or hashlib.sha256(f"{email}{time.time()}".encode()).hexdigest()[:36]
    urgency = urgency if urgency in URGENCIAS_VALIDAS else None

    if _es_duplicado_reciente(email):
        log.info("Lead duplicado (mismo email en los últimos %ss) — no se reenvía.", _VENTANA_DUPLICADO_SEG)
        return {"status": "guardado", "local": None, "duplicado": True, "meta_capi": {"status": "omitido", "detalle": "duplicado reciente"}}

    registro = {
        "email": email,
        "urgency": urgency,
        "fuente": _limpiar(fuente, 80) or "lp_taskdoctor",
        "event_id": event_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "ip": _limpiar(client_ip, 45) or None,  # 45 = largo máximo de una IPv6
    }
    ruta_local = guardar_lead_local("taskdoctor", registro)

    resultado = {"status": "guardado", "local": str(ruta_local.relative_to(REPO_ROOT))}

    if pixel_id and access_token:
        capi = enviar_evento_meta_capi(
            pixel_id=pixel_id,
            access_token=access_token,
            event_id=event_id,
            email=email,
            event_source_url=_limpiar(event_source_url, 600),
            client_ip=_limpiar(client_ip, 45) or None,
            client_user_agent=_limpiar(client_user_agent, 400) or None,
            fbp=_limpiar(fbp, 200) or None,
            fbc=_limpiar(fbc, 200) or None,
        )
        resultado["meta_capi"] = capi
    else:
        resultado["meta_capi"] = {"status": "omitido", "detalle": "META_PIXEL_ID / META_CAPI_ACCESS_TOKEN no configurados en .env"}

    return resultado
