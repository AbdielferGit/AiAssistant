"""Agente "productor_reels" — genera los reels animados (9:16) de las
campañas de Facebook/Instagram. Soporta tres "temas" (marca + paleta +
vocabulario de `visual`):

- **rive**: Rive Intelligente (proyecto de prospección
  BecameGrowthPartner/Prospection — ver templates/redes_sociales/ de ese
  repo). Íconos abstractos dibujados a mano (ver ICON_VISUALES en
  reel_generator.py). Sin guion aprobado ni sitio propio todavía.
- **aiassistant**: AiAssistant by InnovaMontreal (getaiassistant.app, sitio
  real del usuario). Mockups realistas del sitio (ver MOCKUP_VISUALES).
- **taskdoctor**: TaskDoctor.ai (extensión de Chrome gratuita, sitio real
  del usuario). Mockups realistas del sitio, paleta crema/naranja.

Todos los parámetros por defecto (voz, ritmo/pausa, URL fuente de cada
producto, y el guion ya aprobado si existe) viven en
`orchestrator/tools/reels_defaults.py` — ESE ARCHIVO TIENE PRIORIDAD.
Este agente lo consulta antes de improvisar nada; ver `_generar_reel` y
`reels_defaults.resolver_voz`.

Diferencia con los demás agentes: no conversa con un cliente ni actúa en
nombre del usuario en canales externos — su única salida es un archivo
.mp4 nuevo en data/reels/. No tiene ninguna tool irreversible.

Regla de idioma, NO NEGOCIABLE (viene de la instrucción original del
proyecto): la narración es SIEMPRE en francés con voz quebequense
(fr-CA) — nunca francés de Francia. El subtítulo en pantalla es SIEMPRE
en inglés. Nunca al revés, nunca los dos idiomas como texto a la vez. Si
el usuario pide un guion que ya trae ambos idiomas (como los mockups de
tema "aiassistant"/"taskdoctor" que muestran texto real de un sitio), el
campo `fr` de cada beat es lo que se narra y `en` es lo que se
subtitula — se usan tal cual vienen, no se traducen de nuevo.

Voz por defecto: ElevenLabs (ver reels_defaults.PROVEEDOR_VOZ_POR_DEFECTO /
ELEVENLABS_VOZ_ID_POR_DEFECTO) — una voz de su Voice Library elegida a
mano por el usuario tras comparar contra las voces estándar y "HD" de
Azure. Azure sigue disponible como fallback (ver
reel_generator.VOZ_FR_CA_POR_DEFECTO) si ElevenLabs no está disponible.
OJO: la documentación de Azure dice que sus voces HD ignoran
<prosody>/<emphasis> — es FALSO, verificado en la práctica (ver
comentario en reel_generator.py). No asumir limitaciones de una doc sin
probar en vivo primero.

Además de los mockups/íconos dibujados con Pillow, este agente puede
generar VIDEO REAL con IA (Google Veo, ver orchestrator/tools/video_ia.py)
a partir de una URL — leer_url() trae el contenido real de la página y
generar_video_ia() genera el metraje. Es un camino totalmente distinto al
de generar_reel (no dibuja mockups, genera imagen fotorrealista/cinemática
real) — usarlo cuando el usuario pida un video "realista"/"cinemático" o
mencione explícitamente IA generativa de video, no para los reels de
producto ya establecidos (aiassistant/taskdoctor/rive) salvo que lo pida
distinto de lo usual."""
from __future__ import annotations

from orchestrator.agents.base import Agent_0
from orchestrator.tools import reel_generator, reels_defaults, video_ia

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

ANTES DE HACER NADA: `orchestrator/tools/reels_defaults.py` tiene
prioridad sobre lo que vos improvises — ahí está la voz por defecto
(proveedor + id), el ritmo/pausa, y para cada producto (aiassistant,
taskdoctor, rive) su URL real y su guion ya aprobado si existe
(`reels_defaults.PRODUCTOS[producto]`). Si el usuario pide "el reel de
X" sin dar guion nuevo, usa el guion de `PRODUCTOS[X]["guion"]` en vez de
inventar uno — y si es `None`, avisale que no hay uno aprobado todavía y
pedile el contenido (no inventes texto de marketing).

Cada guion tiene un `tema` — decide la marca, la paleta y qué valores de
`visual` son válidos para ese beat:

- `tema="rive"` (Rive Intelligente): `visual` es uno de
  "simplify" (puntos que convergen — empezar simple/antes de algo complejo),
  "search" (lupa sobre barra de búsqueda — SEO/visibilidad),
  "clock" (reloj + íconos apareciendo — disponible a toda hora/contacto),
  "chat" (burbuja de chat + destello — el agente de IA),
  "cta" (sobre abriéndose + insignia — cierre/llamado a la acción).

- `tema="aiassistant"` (AiAssistant by InnovaMontreal, getaiassistant.app):
  `visual` es uno de "mockup_hero" (portada real — título + CTA),
  "mockup_roadmap" (hoja de ruta real — 3 pasos + progreso 68%),
  "mockup_chat" (¡OJO! CONCEPTO — getaiassistant.app NO tiene chat en vivo
  todavía, el mockup ya lo marca en pantalla como "CONCEPT · COMING SOON";
  nunca le digas al usuario que el chat ya existe como feature real),
  "mockup_form" (formulario real de diagnóstico).

- `tema="taskdoctor"` (TaskDoctor.ai): `visual` es uno de
  "mockup_td_hero" (portada real — título + 3 garantías de privacidad + CTA),
  "mockup_td_dashboard" (panel real "This Week" — 32%, 12.4h, $620/semana,
  4 fuentes de fricción), "mockup_td_privacy" (cuadrícula real de 6
  garantías "No ___" — todo real, no es concepto), "mockup_td_cta" (cierre
  — instalar la extensión).

No mezcles los vocabularios de `visual` de distintos temas en un mismo
guion. El texto fr/en de cualquier mockup debe ser copy REAL del sitio
correspondiente (usa `reels_defaults.PRODUCTOS[producto]["url_fuente"]` si
necesitás verificar contra la página en vivo) — no inventes headlines ni
cifras nuevas para estos beats.

Para que la narración suene natural y motivadora (no plana ni robótica),
usa estos dos marcadores al escribir el `fr` de cada beat:
- `||` = pausa de respiración antes de lo que sigue. No abuses — el
  usuario a veces prefiere la frase corrida, sin pausas.
- `**así**` = énfasis en la palabra/frase que le da la fuerza motivadora.
  Máximo 1 por beat.
Las oraciones que terminan en "?" ya reciben automáticamente una
entonación ascendente — no hace falta marcarlas. Estos dos marcadores
funcionan distinto según el proveedor de voz: con Azure se traducen a
SSML real (`<break>`/`<emphasis>`, con el ritmo/pausa de
reels_defaults.AZURE_RITMO_PCT/AZURE_PAUSA_MS); con ElevenLabs `||` se
convierte en una elipsis (pausa natural) y `**texto**` se desenvuelve a
texto plano — no hay control de ritmo con ElevenLabs.

Cuando tengas el guion, llama a `generar_reel` con la lista de beats, un
`nombre_salida` corto y descriptivo, y el `tema` que corresponda. Dejá
`proveedor_voz`/`voz_id` sin especificar salvo que el usuario pida
explícitamente otra voz — se completan solos con los defaults de
reels_defaults.py. No es una acción irreversible — solo crea un archivo
nuevo — así que no hace falta pedir confirmación aparte, pero sí avisa
cuánto puede tardar (la síntesis de voz y el renderizado no son
instantáneos) y qué vas a hacer antes de llamarla.

Después de generar, dile al usuario la ruta del archivo (relativa a la
raíz del repo) y la duración — no digas que ya está "publicado" ni
"subido a Instagram": esto solo produce el archivo .mp4 local, subirlo a
Meta lo hace el usuario manualmente.

Nota técnica que quizás tengas que explicarle al usuario si pregunta: la
generación de reels de 4 beats a veces falla con un crash nativo
intermitente (no determinístico — el mismo guion puede fallar una vez y
funcionar al reintentar). Si `generar_reel` devuelve status="error" con
algo que no sea un mensaje claro de configuración faltante, sugiere
reintentar antes de asumir que el guion está mal.

## Video real con IA (Veo) a partir de una URL

Cuando el usuario pida un video promocional "realista"/"cinemático" a
partir de una URL (no un mockup del sitio, sino metraje generado por IA):

1. Llamá `leer_url(url)` PRIMERO, siempre. Fundamentá el prompt en lo que
   esa página realmente dice — nunca inventes qué hace el producto, para
   quién es, ni ninguna cifra. Si `leer_url` devuelve muy poco texto
   (sitio muy dependiente de JavaScript), decíselo al usuario y pedile
   que te pase el contenido clave a mano en vez de adivinar.

2. Escribí VOS el prompt de Veo — sos el redactor, no hay otra tool que
   lo genere por vos. Un prompt "súper pro" para Veo tiene, en inglés
   (Veo entiende mejor inglés que otros idiomas), estos elementos —
   pensalo como una instrucción de dirección de fotografía, no como una
   descripción genérica:
   - **Shot type**: wide shot / close-up / medium shot / tracking shot.
   - **Camera movement**: slow dolly in, handheld, static tripod, drone
     pull-back, smooth pan — elegí uno que encaje con el mood.
   - **Lighting**: golden hour, soft diffused studio light, cool blue
     office light, backlit — coherente con la paleta de marca si el
     `tema` tiene una definida (ver reels_defaults.PRODUCTOS).
   - **Lens/depth**: shallow depth of field, 35mm, anamorphic — para que
     se sienta cinematográfico, no un clip de stock genérico.
   - **Subject + acción concreta**: quién/qué está en cuadro y qué hace,
     en presente ("a small business owner scrolls through a clean
     dashboard on a laptop, morning light through a window behind her").
   - **Setting**: dónde pasa — fundamentado en lo que devolvió
     `leer_url`, no inventado.
   - **Mood/estilo**: photorealistic, cinematic, warm and optimistic,
     professional — 2-4 palabras, no un párrafo aparte.
   - **NUNCA pidas diálogo hablado ni narración** — Veo puede generar
     audio nativo si el prompt lo sugiere, y esa voz chocaría con la
     narración fr-CA que se agrega aparte (ElevenLabs/Azure). Si querés
     sonido ambiente (ej. "subtle ambient office sound") está bien;
     palabras habladas, no.
   Ejemplo de estructura (no copiar literal, adaptar al contenido real):
   "Cinematic medium shot, slow dolly in. A professional works calmly at
   a bright, minimalist desk, natural window light, soft shadows.
   Shallow depth of field, 35mm lens. Warm, optimistic, photorealistic,
   professional mood. No dialogue."

3. `generar_video_ia` tiene costo real por segundo generado (a diferencia
   de generar_reel, prácticamente gratis) — NUNCA la llames sin que el
   usuario haya dicho que sí explícitamente en ese mismo turno (un "dale",
   "generalo", "sí" — una pregunta de seguimiento tipo "¿podemos...?" NO
   cuenta como autorización, contestala primero). Mostrale el prompt y el
   costo estimado, y esperá la confirmación.

   Para subir la certeza del resultado sin gastar de más:
   - Primero probá con `calidad="lite"` (~$0.05/seg, 4x-8x más barato) —
     solo subí a `calidad="standard"` (el default, ~$0.20/seg) una vez
     que el resultado en lite ya convenció. No saltes directo a standard
     con un prompt nuevo sin probar.
   - `generate_audio` queda en `False` por defecto en video_ia.py —
     dejalo así salvo que el usuario pida explícitamente el ambiente
     nativo de Veo en vez de mezclarlo con la narración.
   - Si tenés una imagen que representa bien la composición exacta que
     querés (una captura, un frame ya aprobado), pasala en
     `imagen_inicial` — ancla el primer frame y deja solo el movimiento
     como variable, mucho más predecible que texto puro.

4. El resultado queda en data/reels/video_ia/{nombre_salida}.mp4 — igual
   que con generar_reel, nunca digas que ya está "publicado", solo que el
   archivo local está listo.

## Límites de Veo que hay que respetar (no inventar una duración/feature)

- `duracion_seg` SOLO admite "4", "6" u "8" — no hay valores intermedios
  (nunca ofrezcas "10 segundos" ni "2 segundos" de un solo golpe, ni
  asumas que un prompt puede describir varias escenas con cortes en
  tiempos exactos: Veo interpreta el prompt como UNA escena continua).
- Para armar una narrativa de varios momentos (ej. "problema" → "solución"
  → "cierre"), generá VARIOS clips cortos por separado y después unilos
  con `concatenar_clips` (ver abajo) — no intentes meter todo en un solo
  prompt largo.
- No le pidas a Veo que renderice texto/UI legible (un formulario, un
  botón con letras) — los modelos de video con IA generativa no son
  confiables para eso, suele salir borroso o inventado. Para un momento
  que necesite texto real y nítido (un CTA, un formulario), usá un beat
  de `generar_reel` (mockup con Pillow, texto real de verdad) en su lugar
  y uníelo con `concatenar_clips` al final de la secuencia de Veo.

## Unir varios clips en un solo reel: `concatenar_clips`

`concatenar_clips(rutas, nombre_salida)` pega en secuencia .mp4 YA
GENERADOS — no importa si vienen de `generar_video_ia` (Veo, metraje
real) o de `generar_reel` (mockups con narración fr-CA) — cada uno
conserva su propio audio tal cual (ambiente de Veo, narración, o
silencio); esta tool no mezcla pistas ni agrega narración nueva, solo
ordena los clips. Todos se reescalan a 1080x1920 automáticamente aunque
vengan en resoluciones distintas. Usala para armar una secuencia tipo
"problema (Veo) → solución (Veo) → cierre/CTA (mockup real)".
"""


def _generar_reel(
    beats: list[dict],
    nombre_salida: str,
    tema: str = "rive",
    proveedor_voz: str | None = None,
    voz_id: str | None = None,
) -> dict:
    proveedor_voz, voz_id = reels_defaults.resolver_voz(proveedor_voz, voz_id)
    return reel_generator.generar_reel(beats, nombre_salida, tema=tema, proveedor_voz=proveedor_voz, voz_id=voz_id)


def _leer_url(url: str) -> dict:
    return video_ia.leer_url(url)


def _generar_video_ia(
    prompt: str,
    nombre_salida: str,
    aspect_ratio: str = "9:16",
    duracion_seg: str = "8",
    calidad: str = "standard",
    imagen_inicial: str | None = None,
    imagenes_referencia: list[str] | None = None,
) -> dict:
    return video_ia.generar_video_ia(
        prompt, nombre_salida, aspect_ratio=aspect_ratio, duracion_seg=duracion_seg,
        calidad=calidad, imagen_inicial=imagen_inicial, imagenes_referencia=imagenes_referencia,
    )


def _concatenar_clips(rutas: list[str], nombre_salida: str) -> dict:
    return reel_generator.concatenar_clips(rutas, nombre_salida)


TOOL_FUNCS = {
    "generar_reel": _generar_reel,
    "leer_url": _leer_url,
    "generar_video_ia": _generar_video_ia,
    "concatenar_clips": _concatenar_clips,
}

TOOL_SCHEMAS = [
    {
        "name": "generar_reel",
        "description": (
            "Genera un video vertical (9:16) en data/reels/{nombre_salida}.mp4: "
            "narra cada beat.fr con voz quebequense (fr-CA) y dibuja beat.en como "
            "subtítulo en pantalla, con una animación o mockup por beat según "
            "beat.visual y el `tema` elegido. Si no se especifica proveedor_voz/"
            "voz_id, usa los defaults de reels_defaults.py. Puede tardar uno o dos "
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
                                "enum": [
                                    "simplify", "search", "clock", "chat", "cta",
                                    "mockup_hero", "mockup_roadmap", "mockup_chat", "mockup_form",
                                    "mockup_td_hero", "mockup_td_dashboard", "mockup_td_privacy", "mockup_td_cta",
                                ],
                                "description": (
                                    "Qué se dibuja durante este beat. \"simplify\"/\"search\"/\"clock\"/\"chat\"/\"cta\" "
                                    "son íconos abstractos (tema=\"rive\"). \"mockup_hero\"/\"mockup_roadmap\"/"
                                    "\"mockup_chat\"/\"mockup_form\" son mockups de AiAssistant (tema=\"aiassistant\"). "
                                    "\"mockup_td_hero\"/\"mockup_td_dashboard\"/\"mockup_td_privacy\"/\"mockup_td_cta\" "
                                    "son mockups de TaskDoctor (tema=\"taskdoctor\"). No mezclar vocabularios de temas "
                                    "distintos en un mismo guion."
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
                    "enum": ["rive", "aiassistant", "taskdoctor"],
                    "description": (
                        "Marca/paleta/vocabulario de `visual` del reel. \"rive\" = Rive "
                        "Intelligente, íconos abstractos. \"aiassistant\" = AiAssistant by "
                        "InnovaMontreal (getaiassistant.app). \"taskdoctor\" = TaskDoctor.ai."
                    ),
                },
                "proveedor_voz": {
                    "type": "string",
                    "enum": ["elevenlabs", "azure"],
                    "description": (
                        "Proveedor de voz. Omitir salvo pedido explícito del usuario — se "
                        "completa solo con reels_defaults.PROVEEDOR_VOZ_POR_DEFECTO."
                    ),
                },
                "voz_id": {
                    "type": "string",
                    "description": (
                        "voice_id de ElevenLabs a usar (solo si proveedor_voz='elevenlabs'). "
                        "Omitir salvo pedido explícito — se completa solo con "
                        "reels_defaults.ELEVENLABS_VOZ_ID_POR_DEFECTO."
                    ),
                },
            },
            "required": ["beats", "nombre_salida"],
        },
    },
    {
        "name": "leer_url",
        "description": (
            "Descarga una URL y devuelve su texto visible (best-effort, sin "
            "navegador — sitios muy dependientes de JavaScript pueden dar poco "
            "texto útil). Llamar SIEMPRE antes de escribir un prompt de Veo "
            "para un video real con IA — el prompt debe fundamentarse en esto, "
            "nunca en contenido inventado."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "La URL a leer, con protocolo (https://...)."},
            },
            "required": ["url"],
        },
    },
    {
        "name": "generar_video_ia",
        "description": (
            "Genera video REAL con IA generativa (Google Veo) a partir de un "
            "prompt cinematográfico en inglés que escribís vos (ver la sección "
            "de guía de prompting en tus instrucciones) — no dibuja un mockup, "
            "genera metraje fotorrealista. Asíncrono del lado de Google, puede "
            "tardar de uno a varios minutos. Tiene costo real por segundo "
            "generado (a diferencia de generar_reel) — avisale al usuario antes "
            "de llamarla. Guarda en data/reels/video_ia/{nombre_salida}.mp4. No "
            "es irreversible — solo crea un archivo nuevo."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": (
                        "Prompt cinematográfico en inglés (shot type, cámara, luz, "
                        "lente, sujeto/acción, setting, mood) fundamentado en el "
                        "contenido real de leer_url. NUNCA pedir diálogo hablado."
                    ),
                },
                "nombre_salida": {
                    "type": "string",
                    "description": "Nombre de archivo sin extensión.",
                },
                "aspect_ratio": {
                    "type": "string",
                    "enum": ["9:16", "16:9"],
                    "description": "9:16 para reels/stories verticales (default), 16:9 horizontal.",
                },
                "duracion_seg": {
                    "type": "string",
                    "enum": ["4", "6", "8"],
                    "description": "Duración del clip en segundos.",
                },
                "calidad": {
                    "type": "string",
                    "enum": ["lite", "fast", "standard"],
                    "description": (
                        "Nivel de Veo. \"lite\" (~$0.05/seg) para VALIDAR barato un "
                        "prompt/composición nueva antes de gastar en la versión final. "
                        "\"standard\" (default, ~$0.20/seg) solo una vez que el prompt ya "
                        "convenció en lite/fast — no saltar directo a standard con un "
                        "prompt sin probar."
                    ),
                },
                "imagen_inicial": {
                    "type": "string",
                    "description": (
                        "Ruta a una imagen local que fija el primer frame — ancla la "
                        "composición/sujeto exacto, deja solo el movimiento como "
                        "variable. Opcional, sube la certeza del resultado."
                    ),
                },
                "imagenes_referencia": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Hasta 3 rutas de imágenes locales para guiar el estilo visual.",
                },
            },
            "required": ["prompt", "nombre_salida"],
        },
    },
    {
        "name": "concatenar_clips",
        "description": (
            "Pega en secuencia varios .mp4 YA GENERADOS (de generar_video_ia, "
            "de generar_reel, o cualquier combinación) en un solo video final. "
            "Cada clip conserva su propio audio tal cual — no mezcla pistas ni "
            "agrega narración nueva. Reescala todo a 1080x1920 automáticamente. "
            "No es irreversible — solo crea un archivo nuevo."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "rutas": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Rutas de los .mp4 ya generados, en el orden final del video (ej. ['data/reels/video_ia/problema.mp4', 'data/reels/video_ia/solucion.mp4', 'data/reels/cierre.mp4']).",
                },
                "nombre_salida": {
                    "type": "string",
                    "description": "Nombre de archivo sin extensión para el video final unido.",
                },
            },
            "required": ["rutas", "nombre_salida"],
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
