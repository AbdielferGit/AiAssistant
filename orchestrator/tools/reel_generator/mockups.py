"""Punto de unión de los dos vocabularios de "visual": íconos abstractos
(iconos.py, tema "rive") y mockups de sitio real (mockups_aiassistant.py +
mockups_taskdoctor.py). Separado del resto en la modularización de
2026-09-19."""
from __future__ import annotations

from .iconos import ICON_VISUALES
from .mockups_aiassistant import _mockup_chat, _mockup_form, _mockup_hero, _mockup_roadmap
from .mockups_taskdoctor import _mockup_td_cta, _mockup_td_dashboard, _mockup_td_hero, _mockup_td_privacy

MOCKUP_VISUALES = {
    "mockup_hero": _mockup_hero,
    "mockup_roadmap": _mockup_roadmap,
    "mockup_form": _mockup_form,
    "mockup_chat": _mockup_chat,
    "mockup_td_hero": _mockup_td_hero,
    "mockup_td_dashboard": _mockup_td_dashboard,
    "mockup_td_privacy": _mockup_td_privacy,
    "mockup_td_cta": _mockup_td_cta,
}

# Unión de los dos "vocabularios" de visual — sólo para validar la clave
# que llega en cada beat. composicion._componer_frame decide cuál pipeline
# usar según a qué dict pertenece la clave.
VISUALES = {**ICON_VISUALES, **MOCKUP_VISUALES}
