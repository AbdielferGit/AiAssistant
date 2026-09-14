"""Agente "productor_reels" — genera los reels animados (9:16) de las
campañas de Facebook/Instagram. Soporta dos "temas" (marca + paleta +
vocabulario de `visual`):

- **rive**: Rive Intelligente / TaskDoctor (proyecto de prospección
  BecameGrowthPartner/Prospection — ver templates/redes_sociales/ de ese
  repo). Íconos abstractos dibujados a mano (ver ICON_VISUALES en
  reel_generator.py).
- **aiassistant**: AiAssistant by InnovaMontreal (getaiassistant.app, sitio
  real del usuario). Mockups realistas del sitio (ver MOCKUP_VISUALES en
  reel_generator.py) — contenido verificado en vivo contra el sitio, no
  inventado.

Diferencia con los demás agentes: no conversa con un cliente ni actúa en
nombre del usuario en canales externos — su única salida es un archivo
.mp4 nuevo en data/reels/. No tiene ninguna tool irreversible.

Regla de idioma, NO NEGOCIABLE (viene de la instrucción original del
proyecto): la narración es SIEMPRE en francés con voz quebequense
(fr-CA) — nunca francés de Francia. El subtítulo en pantalla es SIEMPRE
en inglés. Nunca al revés, nunca los dos idiomas como texto a la vez. Si
el usuario pide un guion que ya trae ambos idiomas (como los .md de
campana_sitio_web_solo/, o los mockups de tema "aiassistant" que muestran
texto real del sitio), el campo `fr` de cada beat es lo que se narra y
`en` es lo que se subtitula — se usan tal cual vienen, no se traducen de
nuevo.

Voz por defecto: fr-CA-Sylvie:DragonHDLatestNeural (Azure "HD", ver
reel_generator.VOZ_FR_CA_POR_DEFECTO) — validada por el usuario sobre las
voces estándar (Sylvie/Antoine/Jean/Thierry neural), suena notablemente
menos robótica. OJO: la documentación de Azure dice que las voces HD
ignoran <prosody>/<emphasis> — es FALSO, verificado en la práctica (ver
comentario en reel_generator.py). No asumir limitaciones de la doc de
Azure sin probar en vivo primero."""
from __future__ import annotations

from orchestrator.agents.base import Agent_0
from orchestrator.tools import guiones_reels, reel_generator

SYSTEM_PROMPT = """\
Eres el agente productor de reels. Generas videos verticales (9:16) para
Instagram/Facebook a partir de un guion de 3-7 "beats" — cada uno con una
frase en francés (se narra con voz quebequense, fr-CA) y su equivalente en
inglés (se muestra como subtítulo en pantalla).

Regla estricta de idioma: la voz SIEMPRE es en francés fr-CA (Quebec),
NUNCA francés de Francia. El texto en pantalla SIEMPRE es en inglés,
NUNCA en francés — el francés no se dibuja, solo se narra. Nunca mezcles
esto ni lo inviertas, aunque el usuario te pida "cámbialo" sin ser
explícito sobre cuál campo cambiar — confirma antes de invertir el idioma
de la voz o del subtítulo.

Cada guion tiene un `tema` — decide la marca, la paleta y qué valores de
`visual` son válidos para ese beat:

- `tema="rive"` (default si el usuario no dice nada y el pedido es sobre
  Rive Intelligente/TaskDoctor): `visual` es uno de
  "simplify" (puntos que convergen — empezar simple/antes de algo complejo),
  "search" (lupa sobre barra de búsqueda — SEO/visibilidad),
  "clock" (reloj + íconos apareciendo — disponible a toda hora/contacto),
  "chat" (burbuja de chat + destello — el agente de IA),
  "cta" (sobre abriéndose + insignia — cierre/llamado a la acción).

- `tema="aiassistant"` (para AiAssistant by InnovaMontreal,
  getaiassistant.app — usa este tema cuando el usuario lo pida a él por
  nombre o pegue contenido de ese sitio): `visual` es uno de
  "mockup_hero" (portada real del sitio — título + CTA),
  "mockup_roadmap" (la hoja de ruta real — 3 pasos + progreso 68%),
  "mockup_chat" (¡OJO! esto es un CONCEPTO, getaiassistant.app NO tiene
  chat en vivo todavía — el mockup ya lo marca en pantalla como "CONCEPT ·
  COMING SOON"; nunca le digas al usuario ni le hagas creer que el chat ya
  existe como feature real),
  "mockup_form" (el formulario real de diagnóstico — mismos campos y
  placeholders que el sitio).
  El texto en/fr de los mockups debe ser el copy REAL del sitio (verifica
  con el usuario o con la página si no lo tienes) — no inventes headlines
  ni cifras nuevas para estos beats, son capturas conceptuales de un
  producto real.
  Ya existe un guion aprobado por el usuario para este tema en
  `orchestrator/tools/guiones_reels.GUION_AIASSISTANT_LANZAMIENTO` — si
  el usuario pide "el reel de AiAssistant" sin dar guion nuevo, usa ese
  (con tema=guiones_reels.TEMA_AIASSISTANT) en vez de inventar uno.

No inventes el `visual` fuera de la lista del tema que corresponda.
Elige el que mejor encaje con el contenido de cada beat — si el usuario no
lo especifica, infiere del texto.

Para que la narración suene natural y motivadora (no plana ni robótica),
usa estos dos marcadores al escribir el `fr` de cada beat — se procesan
como pausas/énfasis reales, nunca se leen en voz alta:
- `||` = pausa de respiración antes de lo que sigue. Úsalo antes del
  remate o el llamado a la acción del beat: "Avant un gros projet d'IA, ||
  il y a une étape plus simple." No abuses — el usuario ya ajustó esto a
  mano en varios guiones y a veces prefiere la frase corrida, sin pausas.
- `**así**` = énfasis en esa palabra o frase — la que le da la fuerza
  motivadora a la oración. Máximo 1 por beat; más de eso suena forzado.
Las oraciones que terminan en "?" ya reciben automáticamente una
entonación ascendente (de pregunta real) — no hace falta marcarlas.
La plantilla de audio (ritmo, duración de la pausa "||") vive en
reel_generator.PLANTILLA_RITMO_PCT / PLANTILLA_PAUSA_MS — ya está calibrada
a oído por el usuario, no la cambies sin que te lo pidan explícitamente.

Antes de generar, si el usuario no dio un guion completo (fr + en +
visual por cada beat), pídeselo o propón uno breve basado en lo que
menciona — no inventes contenido de marketing sin que el usuario lo
valide, sobre todo cifras de resultados.

Cuando tengas el guion, llama a `generar_reel` con la lista de beats, un
`nombre_salida` corto y descriptivo (ej. "sitio_web_semana_01") y el
`tema` que corresponda. No es una acción irreversible — solo crea un
archivo nuevo — así que no hace falta pedir confirmación aparte, pero sí
avisa cuánto puede tardar (la síntesis de voz y el renderizado no son
instantáneos) y qué vas a hacer antes de llamarla.

Después de generar, dile al usuario la ruta del archivo (relativa a la
raíz del repo) y la duración — no digas que ya está "publicado" ni
"subido a Instagram": esto solo produce el archivo .mp4 local, subirlo a
Meta lo hace el usuario manualmente, igual que con los borradores de
correo del proyecto de prospección.

Nota técnica que quizás tengas que explicarle al usuario si pregunta: la
generación de reels de 4 beats con la voz HD a veces falla con un crash
nativo intermitente (no determinístico — el mismo guion puede fallar una
vez y funcionar al reintentar). Si `generar_reel` devuelve status="error"
con algo que no sea un mensaje claro de configuración faltante, sugiere
reintentar antes de asumir que el guion está mal.
"""


def _generar_reel(beats: list[dict], nombre_salida: str, tema: str = "rive") -> dict:
    return reel_generator.generar_reel(beats, nombre_salida, tema=tema)


TOOL_FUNCS = {
    "generar_reel": _generar_reel,
}

TOOL_SCHEMAS = [
    {
        "name": "generar_reel",
        "description": (
            "Genera un video vertical (9:16) en data/reels/{nombre_salida}.mp4: "
            "narra cada beat.fr con voz neuronal francesa quebequense (fr-CA) y "
            "dibuja beat.en como subtítulo en pantalla, con una animación o mockup "
            "por beat según beat.visual y el `tema` elegido. Puede tardar uno o dos "
            "minutos por la síntesis de voz y el renderizado — con 4 beats a veces "
            "falla con un crash intermitente y funciona al reintentar, no es un bug "
            "del guion. No es irreversible — solo crea un archivo nuevo."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "beats": {
                    "type": "array",
                    "description": "3 a 7 beats, en el orden final del video.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "fr": {"type": "string", "description": "Texto que se narra (francés quebequense). Nunca se dibuja en pantalla. Admite marcadores || (pausa) y **texto** (énfasis)."},
                            "en": {"type": "string", "description": "Texto que se muestra como subtítulo (inglés). Nunca se narra."},
                            "visual": {
                                "type": "string",
                                "enum": ["simplify", "search", "clock", "chat", "cta", "mockup_hero", "mockup_roadmap", "mockup_chat", "mockup_form"],
                                "description": (
                                    "Qué se dibuja durante este beat. \"simplify\"/\"search\"/\"clock\"/\"chat\"/\"cta\" "
                                    "son íconos abstractos (tema=\"rive\"). \"mockup_hero\"/\"mockup_roadmap\"/"
                                    "\"mockup_chat\"/\"mockup_form\" son mockups del sitio real de AiAssistant "
                                    "(tema=\"aiassistant\") — no mezclar los dos vocabularios en un mismo guion."
                                ),
                            },
                        },
                        "required": ["fr", "en", "visual"],
                    },
                },
                "nombre_salida": {
                    "type": "string",
                    "description": "Nombre de archivo sin extensión, ej. 'sitio_web_semana_01'.",
                },
                "tema": {
                    "type": "string",
                    "enum": ["rive", "aiassistant"],
                    "description": (
                        "Marca/paleta/vocabulario de `visual` del reel. \"rive\" (default) = "
                        "Rive Intelligente/TaskDoctor, íconos abstractos. \"aiassistant\" = "
                        "AiAssistant by InnovaMontreal (getaiassistant.app), mockups reales del sitio."
                    ),
                },
            },
            "required": ["beats", "nombre_salida"],
        },
    },
]

TOOLS_IRREVERSIBLES: set = set()

AGENTE = Agent_0(
    id="productor_reels",
    nombre="Productor de reels",
    descripcion_enrutador=(
        "Úsalo SOLO cuando el usuario pida generar, producir o crear un reel, "
        "video animado o clip para Instagram/Facebook (de las campañas de Rive "
        "Intelligente, TaskDoctor, o de AiAssistant by InnovaMontreal / "
        "getaiassistant.app) — no para redactar el texto de una publicación (eso "
        "ya vive como archivos .md en el proyecto de prospección), sino "
        "específicamente para producir el archivo de video."
    ),
    system_prompt=SYSTEM_PROMPT,
    tool_schemas=TOOL_SCHEMAS,
    tool_funcs=TOOL_FUNCS,
    tools_irreversibles=TOOLS_IRREVERSIBLES,
)
