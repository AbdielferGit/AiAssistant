"""
Loop principal del agente.

Usa el Claude Agent SDK para registrar "tools" (acciones) y dejar que el
modelo decida cuándo invocarlas. La pieza no-negociable de este archivo es
`requiere_confirmacion`: cualquier tool marcada como irreversible se
muestra como borrador y espera un "sí" explícito antes de ejecutarse.

NOTA: la API exacta del `claude-agent-sdk` evoluciona — si al instalar la
versión más reciente los nombres de clases/decoradores no coinciden,
ajusta las llamadas de import/registro según la documentación instalada
(`python -c "import claude_agent_sdk; help(claude_agent_sdk)"`). La forma
general del flujo (tools + confirmación humana) se mantiene igual.
"""
from __future__ import annotations

import asyncio
import logging

from claude_agent_sdk import ClaudeAgent, tool  # ver nota arriba si falla el import

from orchestrator import contacts
from orchestrator.config import settings
from orchestrator.memory.style_profile import buscar_ejemplos_de_estilo
from orchestrator.tools import google_workspace, macos_actions, messenger, whatsapp

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("orchestrator")

# Tools cuya ejecución es irreversible: SIEMPRE piden confirmación explícita
# antes de correr, sin excepción. No relajar esta lista sin pensarlo dos veces.
TOOLS_IRREVERSIBLES = {
    "enviar_whatsapp",
    "enviar_email",
    "enviar_messenger",
    "publicar_contenido",
}


@tool(name="redactar_borrador")
async def redactar_borrador(destinatario: str, tema: str, canal: str) -> dict:
    """Genera un borrador de mensaje usando ejemplos reales de cómo el
    usuario le escribe a ese destinatario (o en ese canal)."""
    ejemplos = buscar_ejemplos_de_estilo(destinatario=destinatario, canal=canal, k=6)
    return {
        "destinatario": destinatario,
        "tema": tema,
        "canal": canal,
        "ejemplos_de_estilo": ejemplos,
        "instruccion": (
            "Redacta el mensaje usando el tono, largo y vocabulario que "
            "reflejan estos ejemplos. No inventes hechos que no te dieron."
        ),
    }


@tool(name="enviar_whatsapp")
async def enviar_whatsapp(numero: str, texto: str) -> dict:
    """Envía un mensaje de WhatsApp. IRREVERSIBLE — requiere confirmación
    previa del usuario, gestionada en el loop principal."""
    return await whatsapp.enviar(numero=numero, texto=texto)


@tool(name="enviar_email")
async def enviar_email(destinatario: str, asunto: str, cuerpo: str) -> dict:
    """Envía un correo por Gmail. IRREVERSIBLE."""
    return google_workspace.enviar_email(destinatario, asunto, cuerpo)


@tool(name="enviar_messenger")
async def enviar_messenger(destinatario_id: str, texto: str) -> dict:
    """Envía un mensaje de Messenger. IRREVERSIBLE — ver advertencia en
    orchestrator/tools/messenger.py antes de activar en producción."""
    return await messenger.enviar(destinatario_id, texto)


@tool(name="crear_evento_calendario")
async def crear_evento_calendario(titulo: str, inicio_iso: str, fin_iso: str) -> dict:
    """Crea un evento en Google Calendar. Reversible (se puede borrar)."""
    return google_workspace.crear_evento(titulo, inicio_iso, fin_iso)


@tool(name="abrir_app_o_archivo_mac")
async def abrir_app_o_archivo_mac(nombre: str) -> dict:
    """Abre una aplicación o archivo en la Mac. Reversible."""
    return macos_actions.abrir(nombre)


@tool(name="listar_contactos_autorizados")
async def listar_contactos_autorizados() -> dict:
    """Devuelve los contactos de la lista blanca (config/contacts.yaml).
    Úsala para saber a quién SÍ puedes escribirle antes de intentar
    redactar o enviar algo — no asumas que un nombre que el usuario
    mencionó por voz está autorizado sin confirmarlo aquí."""
    contactos = contacts.listar_todos()
    return {
        "contactos": [
            {"nombre": c.nombre, "alias": c.alias, "activo": c.activo, "canales": list(c.canales)}
            for c in contactos
        ]
    }


@tool(name="ejecutar_accion_android")
async def ejecutar_accion_android(accion: str, parametros: dict) -> dict:
    """Encola una acción para que el bridge de Android la ejecute
    (notificación, disparar un Tasker, leer info local, etc.)."""
    from orchestrator.bridge.server import encolar_comando

    return await encolar_comando(accion=accion, parametros=parametros)


SYSTEM_PROMPT = """\
Eres el asistente personal del usuario. Puedes redactar mensajes que suenen
exactamente como él (usa siempre `redactar_borrador` antes de enviar algo) y
ejecutar acciones en su Mac y su Android.

Regla estricta #1 — lista blanca de contactos: SOLO puedes enviar mensajes
(WhatsApp, email, Messenger, iMessage) a personas que estén en la lista
blanca activa. Si tienes duda sobre si alguien está autorizado, llama a
`listar_contactos_autorizados` antes de redactar o enviar nada. Cada tool
de envío ya rechaza por su cuenta a quien no esté en la lista (verás
`status: "rechazado"` en la respuesta) — si eso pasa, informa al usuario en
vez de intentar otra vía para llegar a esa persona.

Regla estricta #2 — confirmación humana: para CUALQUIER acción irreversible
(enviar mensajes, publicar, comprar) primero muestra el borrador/resumen
exacto de lo que vas a hacer y espera una confirmación explícita del
usuario ("sí", "envíalo", "confirmado"). Nunca asumas confirmación
implícita.
"""


async def run() -> None:
    agent = ClaudeAgent(
        api_key=settings.anthropic_api_key,
        system_prompt=SYSTEM_PROMPT,
        tools=[
            redactar_borrador,
            listar_contactos_autorizados,
            enviar_whatsapp,
            enviar_email,
            enviar_messenger,
            crear_evento_calendario,
            abrir_app_o_archivo_mac,
            ejecutar_accion_android,
        ],
        confirm_before=TOOLS_IRREVERSIBLES,
    )
    log.info("Orchestrator listo. Escribe una instrucción (Ctrl+C para salir).")
    async for turno in agent.chat_loop_stdin():
        log.info("→ %s", turno)


if __name__ == "__main__":
    asyncio.run(run())
