"""Guiones de reels ya escritos y aprobados — para no tener que retipear el
texto cada vez que se regenera un reel ya validado (ej. después de tocar la
plantilla de audio en reel_generator.py, o para republicar el mismo reel
con un `nombre_salida` distinto).

Cada guion es una lista de beats en el formato que espera
`reel_generator.generar_reel(beats, nombre_salida, tema=...)` — ver el
docstring de esa función y de `orchestrator/agents/reel_producer.py` para
el formato de cada beat (fr/en/visual) y los marcadores `||` y `**texto**`.

No inventar guiones nuevos acá sin que el usuario los valide primero — esto
es un archivo de guiones YA aprobados, no un borrador."""
from __future__ import annotations

# --- AiAssistant by InnovaMontreal (getaiassistant.app) ---------------------
# Aprobado por el usuario el 2026-09-14 tras varias iteraciones de visual,
# voz (fr-CA-Sylvie:DragonHDLatestNeural) y plantilla de audio (ritmo -1%,
# pausa 120ms — ver reel_generator.PLANTILLA_RITMO_PCT/PLANTILLA_PAUSA_MS).
# Contenido real verificado en vivo en getaiassistant.app (versión FR y EN)
# el mismo día — no hay cifras ni afirmaciones inventadas. El beat 3
# (mockup_chat) es un CONCEPTO, no una función que ya existe en el sitio —
# el mockup lo marca en pantalla como "CONCEPT · COMING SOON", no cambiar
# eso sin confirmar con el usuario que el chat ya es real.
TEMA_AIASSISTANT = "aiassistant"

GUION_AIASSISTANT_LANZAMIENTO = [
    {
        "fr": "On veut faire travailler l'IA aux côtés de votre équipe.",
        "en": "We want AI working alongside your team.",
        "visual": "mockup_hero",
    },
    {
        "fr": "Avec **un vrai plan** || Diagnostic, || mise en œuvre, || adoption, toujours accompagné.",
        "en": "A real plan: assessment, implementation, adoption — always supported.",
        "visual": "mockup_roadmap",
    },
    {
        "fr": "On peut créer des agents qui parlent comme vous.",
        "en": "We can build agents that sound like you.",
        "visual": "mockup_chat",
    },
    {
        "fr": "Parlez-nous de vous et réservez votre diagnostic.",
        "en": "Tell us about you. Book your assessment.",
        "visual": "mockup_form",
    },
]

# --- TaskDoctor.ai -----------------------------------------------------------
# Aprobado por el usuario el 2026-09-14. Contenido real verificado en vivo
# en taskdoctor.ai (colores por getComputedStyle, copy y cifras tal cual el
# sitio) — el 32%/12.4h/$620 por semana y las 4 fuentes de fricción son el
# propio ejemplo que muestra el sitio, no inventados. Nada acá es concepto,
# todo el contenido (incluida la cuadrícula de privacidad) ya es real y
# público en el sitio.
TEMA_TASKDOCTOR = "taskdoctor"

GUION_TASKDOCTOR_LANZAMIENTO = [
    {
        "fr": "On trouve le travail répétitif dans votre navigateur, || sans jamais surveiller vos employés.",
        "en": "Find browser work worth automating. Without monitoring employees.",
        "visual": "mockup_td_hero",
    },
    {
        "fr": "**32 %** d'opportunités d'automatisation || 12,4 heures retrouvées, 620 dollars par semaine.",
        "en": "32% automation opportunities. 12.4 hours found.",
        "visual": "mockup_td_dashboard",
    },
    {
        "fr": "**Jamais de captures d'écran.** || Jamais de surveillance des employés.",
        "en": "Built for business efficiency, not employee monitoring.",
        "visual": "mockup_td_privacy",
    },
    {
        "fr": "**Installez l'extension**, gratuitement || ça prend moins d'une minute.",
        "en": "Install free. Works on Chrome.",
        "visual": "mockup_td_cta",
    },
]
