"""Configuración del LLM, la crew de CrewAI, y el retry/medición alrededor de kickoff()."""

import os
import time

import httpx
from crewai import Agent, Task, Crew, Process, LLM
from crewai_tools import SerperDevTool
from google.genai import errors as genai_errors
from google.genai import types as genai_types

from .tools import verificar_grounding

DEFAULT_MODEL = "gemini-3.5-flash-lite"

# Errores de red/servidor que ameritan reintento (además de los códigos HTTP de genai_errors).
# httpx.TimeoutException NO hereda de TimeoutError (son jerarquías separadas) — sin esto,
# un timeout de la llamada a Gemini se escapa del retry en vez de reintentarse.
NETWORK_ERRORS = (ConnectionError, TimeoutError, httpx.TimeoutException)


DEFAULT_TIMEOUT_SEGUNDOS = 60


def build_llm() -> LLM:
    """Configura el LLM (Gemini) que van a compartir los agentes de la crew"""
    api_key = (os.environ.get("GEMINI_API_KEY") or "").strip()
    model = os.environ.get("MODEL", DEFAULT_MODEL)
    timeout_segundos = int(os.environ.get("GEMINI_TIMEOUT_SEGUNDOS", DEFAULT_TIMEOUT_SEGUNDOS))

    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set")

    # El kwarg `timeout` de LLM() solo aplica al path genérico (litellm); el proveedor
    # nativo de Gemini (el que usamos acá) solo lee client_params -> http_options.timeout,
    # en milisegundos. Sin esto, una llamada colgada a la API no corta nunca.
    return LLM(
        model=f"gemini/{model}",
        api_key=api_key,
        temperature=0.7,
        client_params={"http_options": genai_types.HttpOptions(timeout=timeout_segundos * 1000)},
    )


def build_crew(dominio_nombre: str, llm: LLM, task_callback=None) -> Crew:
    """Arma la crew de 4 roles: Analista → Especialista → Arquitecto → Mediador

    task_callback (opcional): función que CrewAI llama con el TaskOutput después de
    cada una de las 4 tasks — lo usa la interfaz web para reportar avance real.
    """
    analista = Agent(
        role="Analista de Requerimientos",
        goal="Extraer el objetivo real, el perfil del usuario final, restricciones implícitas y criterios de éxito de la solicitud, en un formato que el Especialista y el Arquitecto puedan usar directamente.",
        backstory=(
            "Experto en leer entre líneas. Si la solicitud menciona 'ponytail', 'audit' u 'opencode', "
            "la interpretás estrictamente en contexto de desarrollo de software y herramientas de IA, "
            "ignorando interpretaciones de estilismo. Sos el primer eslabón de la cadena: lo que no dejes "
            "claro acá, el resto del equipo no lo va a poder inferir."
        ),
        llm=llm,
        verbose=False,
    )

    especialista_tools = [SerperDevTool()] if os.environ.get("SERPER_API_KEY") else []
    especialista = Agent(
        role=f"Especialista en {dominio_nombre}",
        goal=f"A partir del análisis del Analista, aportar mejores prácticas, riesgos y recomendaciones propias de {dominio_nombre} que el Arquitecto pueda incorporar directamente al prompt final.",
        backstory=(
            f"Autoridad mundial en {dominio_nombre}, con conocimiento técnico, táctico y estratégico del área. "
            "Trabajás siempre sobre el análisis que te entrega el Analista: nunca repetís su trabajo, lo "
            "complementás con el conocimiento de dominio que él no tiene."
            + (
                " Tenés acceso a búsqueda web: usala para confirmar que las prácticas que recomendás siguen "
                "vigentes, no repitas de memoria algo que puede estar desactualizado."
                if especialista_tools
                else ""
            )
        ),
        tools=especialista_tools,
        llm=llm,
        verbose=False,
    )

    arquitecto = Agent(
        role="Arquitecto Senior de Prompts",
        goal="REGLA INQUEBRANTABLE, PERO CONDICIONAL AL 'Tipo de entrega' DEL ANALISTA: si dice 'Instrucción para IA conversacional', escribís un PROMPT — instrucciones dirigidas a una IA ejecutora que va a generar el contenido después, NUNCA el contenido en sí ('Actúa como...', 'Tu tarea es...', 'Debés...'), jamás dirigido al usuario final que va a leer el resultado eventual (nunca lo saludás, nunca le decís '¡Bienvenida!'). Si en cambio dice 'Contenido directo para herramienta no conversacional', hacés exactamente lo opuesto: entregás el contenido/prompt final LISTO PARA USAR tal cual se pega en esa herramienta (ej. el texto de un prompt de Midjourney con sus bloques positivo/negativo y parámetros nativos) — ahí NO envolvés nada en 'Actúa como...', eso sería un error igual de grave, porque le estarías dando a la herramienta una instrucción en vez del contenido que necesita. Fijate SIEMPRE cuál de los dos te tocó antes de escribir una sola palabra. Combiná el análisis del Analista y las recomendaciones del Especialista en un único resultado final: claro, preciso y consistente, con la estrategia de prompt engineering más adecuada (Zero-Shot, Few-Shot, Chain-of-Thought, etc.). Tu propio texto de salida respeta al pie de la letra cualquier restricción de extensión/formato/tono que el Analista haya marcado, en cualquier dirección: si pide corto, escribís corto vos; si pide el máximo detalle posible, escribís un prompt exhaustivo vos, sin acortarlo por costumbre. Cada ítem de la lista 'Sub-temas a cubrir' del Analista tiene que aparecer como su propia sección en tu prompt final — no fusiones dos ítems en una sola sección ni te olvides de ninguno. Y cada sección no es solo un título: la desarrollás con 2-3 sub-directivas concretas (qué debe explicar exactamente quien ejecute el prompt, por qué importa, o qué riesgo puntual evitar), apoyándote en los riesgos y recomendaciones del Especialista — un título pelado sin sub-directivas es una sección a medio hacer.",
        backstory=(
            "Nunca asume información no validada. Tu trabajo es de síntesis, no de invención — si el "
            "Analista o el Especialista dejaron algo sin definir, señalalo en el prompt en vez de "
            "inventarlo. El Mediador revisa tu trabajo después: no confíes en que él lo arregle, hacelo bien. "
            "Resolvés la solicitud concreta que te llegó, no armás una plantilla genérica reutilizable: nunca "
            "dejes placeholders tipo [INSERTAR AQUÍ] salvo que el usuario haya pedido explícitamente una "
            "plantilla parametrizable."
        ),
        llm=llm,
        verbose=False,
    )

    mediador = Agent(
        role="Mediador de Consistencia",
        goal="Detectar afirmaciones concretas en el prompt del Arquitecto que no estén respaldadas por el análisis del Analista ni por el conocimiento del Especialista, y corregirlas. Además, verificar que el formato del resultado coincida con el 'Tipo de entrega' que definió el Analista.",
        backstory=(
            "Chequeo obligatorio antes que nada, y depende de 'Tipo de entrega' del Analista: si dice "
            "'Instrucción para IA conversacional', el texto del Arquitecto tiene que ser una instrucción "
            "dirigida a una IA (algo tipo 'Actúa como...', 'Tu tarea es...'), no la respuesta ya desarrollada "
            "dirigida al usuario final (si empieza saludando al lector, con un '¡Bienvenida!' o similar, "
            "falló el formato). Si dice 'Contenido directo para herramienta no conversacional', es AL "
            "REVÉS: el texto tiene que ser el contenido/prompt final tal cual se usa en esa herramienta — "
            "si en este caso el Arquitecto lo envolvió en 'Actúa como...' en vez de entregar el contenido "
            "directo, ESO es lo que falló el formato, no lo contrario. En cualquiera de los dos casos, si "
            "detectás el error de formato correspondiente, tu trabajo es corregirlo vos mismo antes de "
            "devolverlo — esto no es negociable, es la función central del sistema, más importante que el "
            "grounding. Recién después de confirmar el formato correcto para el tipo de entrega que "
            "corresponde, hacé la revisión de grounding.\n"
            "No sos un aprobador: no das un veredicto de sí/no ni pedís una nueva ronda. Tu única función es "
            "comparar el prompt del Arquitecto contra lo que el Analista y el Especialista realmente dijeron. "
            "Si encontrás un dato, restricción, tecnología o afirmación que no tiene relación con nada de lo "
            "dicho en ninguno de los dos análisis previos, es una alucinación: quitala o reformulala como "
            "algo a confirmar, no la dejes como si fuera un hecho. Ojo con el falso positivo más común: que "
            "el Especialista haya planteado algo en general (ej. 'riesgo: cremas que se cortan') no significa "
            "que el Arquitecto esté alucinando si lo desarrolla con más especificidad (ej. explica que se "
            "corta por choque térmico y cómo evitarlo) — eso es elaboración razonable de un punto ya "
            "planteado, no un dato inventado, y no lo tocás. Si el prompt está bien respaldado, lo devolvés "
            "intacto — no cambiás nada "
            "por cambiar. Tenés una tool, verificar_grounding, que te da una lista mecánica de términos "
            "técnicos del prompt que no aparecen en el contexto — usala como punto de partida, no como "
            "verdad absoluta (puede haber falsos positivos: sinónimos, términos genéricos).\n"
            "Ahora también podés preguntarle directamente al Arquitecto Senior de Prompts (tenés una tool de "
            "delegación/pregunta para eso) — pero es el último recurso, no el primero: primero mirá vos si "
            "el término está respaldado en el Análisis o la Especialidad. Preguntale al Arquitecto solo "
            "cuando el grounding sea genuinamente ambiguo (ej. no podés decidir si algo es elaboración "
            "razonable o alucinación) y una respuesta suya resolvería la duda. No le preguntes por costumbre "
            "ni le pidas que reescriba el prompt entero — vos seguís siendo quien decide y corrige al final."
        ),
        tools=[verificar_grounding],
        llm=llm,
        allow_delegation=True,
        max_iter=8,
        verbose=False,
    )

    tarea_analisis = Task(
        description=(
            "Analiza esta solicitud de usuario: '{solicitud}'. Definí el objetivo real, el perfil del "
            "usuario final, las restricciones (separando las dos categorías de la sección de abajo) y los "
            "criterios de éxito. Prestá especial atención a cualquier restricción de extensión, formato o "
            "tono que el usuario haya pedido explícita o implícitamente (ej. 'corto', 'en bullets', 'sin "
            "jerga técnica', 'una sola línea') — son las que más se suelen pasar por alto. Además, listá "
            "cada sub-tema distinto que la solicitud menciona (ej. si pide 'materiales, tiempos, errores y "
            "texturas', son 4 sub-temas separados) — no los agrupes ni los resumas en uno solo, cada mención "
            "temática distinta es su propio ítem. Además, clasificá el tipo de entrega que busca la "
            "solicitud (ver la sección correspondiente abajo) — esto define si el resultado final debe ser "
            "una instrucción para una IA, o el contenido/prompt final en sí."
        ),
        expected_output=(
            "Exactamente estas siete secciones, cada una con contenido concreto extraído de la solicitud "
            "(no genérico):\n"
            "Objetivo: <objetivo real de la solicitud>\n"
            "Usuario: <perfil del usuario final>\n"
            "Tipo de entrega: <'Instrucción para IA conversacional' o 'Contenido directo para herramienta "
            "no conversacional'. Elegí la segunda SOLO si el resultado final se pega directo en una "
            "herramienta que no razona ni ejecuta instrucciones, solo consume el texto tal cual (ej. un "
            "prompt de Midjourney/Stable Diffusion/DALL-E, una query SQL, un fragmento de código, un "
            "archivo de config) — ahí el 'prompt' que pide el usuario ES la entrega final, no una "
            "instrucción para que otra IA la arme. Elegí la primera en cualquier otro caso, incluido "
            "cuando la solicitud pide un prompt para que un chatbot/asistente conversacional (ChatGPT, "
            "Gemini, Claude) haga algo — ahí sí corresponde una instrucción tipo 'Actúa como...'>\n"
            "Restricciones de contenido: <restricciones sobre lo que el prompt debe pedir o prohibir, "
            "dirigidas a quien vaya a usar el prompt>\n"
            "Restricciones del prompt en sí: <límites de extensión, formato o tono que el propio texto del "
            "prompt final debe cumplir, en cualquier dirección — tan breve como 'corto (2-3 líneas)', 'sin "
            "secciones numeradas', o tan extenso como 'lo más detallado posible', 'sin resumir, cubrí todo "
            "en profundidad'. Si no se pidió nada de esto, escribí 'Ninguna'>\n"
            "Sub-temas a cubrir: <lista numerada, un ítem por cada sub-tema distinto mencionado en la "
            "solicitud (ej. '1. Materiales y utensilios. 2. Tiempos de preparación. 3. Errores comunes. "
            "4. Texturas de cremas.'). Cada ítem de esta lista es una sección obligatoria del prompt final>\n"
            "Criterios de éxito: <cómo se sabe que el resultado es bueno>"
        ),
        agent=analista,
    )

    tarea_especialidad = Task(
        description=(
            "Tomá el análisis del Analista (Objetivo, Usuario, Restricciones, Criterios de éxito) y, sin "
            "repetirlo, aportá el conocimiento de dominio que le falta: mejores prácticas, riesgos y "
            "recomendaciones específicas para cumplir ese objetivo en el contexto de la solicitud original: "
            "'{solicitud}'."
        ),
        expected_output=(
            "Exactamente estas tres secciones, específicas a la solicitud (no consejos genéricos del dominio):\n"
            "Mejores prácticas: <lista>\n"
            "Riesgos: <lista>\n"
            "Recomendaciones: <lista>"
        ),
        agent=especialista,
        context=[tarea_analisis],
    )

    tarea_prompt = Task(
        description=(
            "IMPORTANTE antes que nada: revisá 'Tipo de entrega' del Analista. Si dice 'Instrucción para IA "
            "conversacional', tu resultado es un PROMPT (instrucción dirigida a una IA que lo va a ejecutar "
            "después), no la respuesta a la solicitud — ejemplo de lo que NO tenés que hacer ahí: si la "
            "solicitud pide una guía de pastelería, vos NO escribís la guía saludando al lector ('¡Bienvenida "
            "al mundo de la pastelería!') — escribís la instrucción que le pedirías a otra IA para que ELLA "
            "escriba esa guía ('Actúa como una pastelera experta... Tu tarea es redactar una guía...'). Si en "
            "cambio dice 'Contenido directo para herramienta no conversacional', es lo opuesto: entregás el "
            "contenido/prompt final tal cual se usa en esa herramienta, sin ningún 'Actúa como...' — ejemplo: "
            "si piden un prompt de Midjourney, entregás directamente el texto del prompt de imagen (bloque "
            "positivo, negativo, parámetros nativos como --v 6.0 --style raw), no una instrucción pidiéndole "
            "a otra IA que lo arme. Con "
            "el análisis del Analista y las mejores prácticas/riesgos/recomendaciones del Especialista, "
            "construí el prompt final optimizado para la solicitud: '{solicitud}'. Las 'Restricciones de "
            "contenido' del análisis y los riesgos del especialista van dentro del prompt como instrucciones "
            "concretas para quien lo use, no como referencia vaga a 'las buenas prácticas'. Las 'Restricciones "
            "del prompt en sí' del análisis son distintas: son un límite duro sobre TU propio texto de salida, "
            "en cualquier dirección — si el análisis dice 'corto (2-3 líneas)', tu prompt final tiene 2-3 "
            "líneas, no una lista de secciones; si el análisis dice 'lo más detallado posible', tu prompt "
            "final desarrolla cada punto en profundidad (explicaciones, ejemplos, tablas si corresponde), no "
            "lo comprimís por costumbre. Resolvé la solicitud concreta, no generes una plantilla genérica con "
            "placeholders. Usá 'Sub-temas a cubrir' del análisis como checklist obligatorio: tu prompt final "
            "tiene una sección dedicada por cada ítem de esa lista, ni uno menos — si tenés 4 ítems, tu "
            "prompt tiene 4 (o más) secciones correspondientes, no 2 o 3 fusionadas. Ninguna sección es solo "
            "un título: cada una trae 2-3 sub-directivas concretas (qué debe cubrir exactamente, por qué "
            "importa, qué riesgo evitar), no un enunciado suelto tipo 'Sección X: describí Y' sin más — usá "
            "los riesgos/recomendaciones del Especialista como insumo para esas sub-directivas."
        ),
        expected_output=(
            "Un PROMPT: texto en forma de instrucción dirigida a una IA ejecutora (empieza con algo como "
            "'Actúa como...' o equivalente), nunca la respuesta ya desarrollada dirigida al usuario final. "
            "Sin explicaciones ni comentarios meta."
        ),
        agent=arquitecto,
        context=[tarea_analisis, tarea_especialidad],
    )

    tarea_mediacion = Task(
        description=(
            "Primer chequeo, antes que nada: mirá 'Tipo de entrega' del Análisis. Si es 'Instrucción para IA "
            "conversacional', el texto del Arquitecto tiene que ser un PROMPT (instrucción dirigida a una "
            "IA, tipo 'Actúa como...'), no la respuesta directa a la solicitud (contenido dirigido al "
            "usuario final, ej. arranca saludándolo). Si es 'Contenido directo para herramienta no "
            "conversacional', es al revés: el texto tiene que ser el contenido/prompt final tal cual se usa "
            "en esa herramienta — si en cambio el Arquitecto lo envolvió en 'Actúa como...', ESO es el "
            "error de formato acá, no lo opuesto. En cualquiera de los dos casos, si el formato no coincide "
            "con lo que corresponde, corregilo vos mismo antes de seguir — esto es más importante que el "
            "grounding, es la función central del sistema. Recién ahí seguí con lo siguiente: Compará el "
            "prompt del Arquitecto contra el Análisis y la Especialidad. Cualquier afirmación "
            "concreta del prompt (una tecnología, un dato, una restricción, un número) que no tenga relación "
            "con nada de lo dicho en ninguno de los dos, es una alucinación del Arquitecto: quitala del "
            "prompt o reformulala explícitamente como algo a confirmar con el usuario. Esto NO aplica si el "
            "Arquitecto simplemente desarrolla con más especificidad algo que el Especialista ya planteó en "
            "general (ej. el Especialista dice 'riesgo: cremas que se cortan' y el Arquitecto explica la "
            "causa —choque térmico— y cómo evitarla): eso es elaboración razonable, dejalo. Usá la tool "
            "verificar_grounding "
            "pasándole el prompt del Arquitecto y el texto combinado del Análisis + la Especialidad como "
            "punto de partida, pero revisá vos también con criterio (la tool puede marcar falsos positivos). "
            "No agregues contenido nuevo propio, no evalúes estilo ni calidad de redacción — solo grounding "
            "contra el Análisis y la Especialidad. Si no encontrás nada sin respaldo, devolvé el prompt del "
            "Arquitecto sin cambios."
        ),
        expected_output="El prompt final ya verificado, listo para usar, sin explicaciones ni comentarios meta.",
        agent=mediador,
        context=[tarea_analisis, tarea_especialidad, tarea_prompt],
    )

    return Crew(
        agents=[analista, especialista, arquitecto, mediador],
        tasks=[tarea_analisis, tarea_especialidad, tarea_prompt, tarea_mediacion],
        process=Process.sequential,
        verbose=False,
        task_callback=task_callback,
    )


def ejecutar_con_reintento(
    crew: Crew, inputs: dict, max_retries=5, initial_delay=1, max_delay=60
):
    """Ejecuta crew.kickoff() con reintento y backoff ante rate limits o errores transitorios del servidor"""
    delay = initial_delay
    for intento in range(1, max_retries + 1):
        try:
            return crew.kickoff(inputs=inputs)
        except (genai_errors.ClientError, genai_errors.ServerError) as e:
            code = getattr(e, "code", None)
            if code not in (429, 500, 503) or intento == max_retries:
                raise
            print(
                f"⚠️ Error temporal ({code}). Reintento {intento}/{max_retries} en {delay}s..."
            )
            time.sleep(delay)
            delay = min(delay * 2, max_delay)
        except NETWORK_ERRORS as e:
            if intento == max_retries:
                raise
            print(
                f"⚠️ Error de red ({e}). Reintento {intento}/{max_retries} en {delay}s..."
            )
            time.sleep(delay)
            delay = min(delay * 2, max_delay)


def formatear_uso(resultado) -> str | None:
    """Arma el texto de tokens consumidos por la crew y, si hay precios configurados, el costo estimado"""
    uso = getattr(resultado, "token_usage", None)
    if uso is None:
        return None

    lineas = [
        f"📊 Tokens: {uso.total_tokens} total ({uso.prompt_tokens} prompt + {uso.completion_tokens} completion, "
        f"{uso.successful_requests} llamadas)"
    ]

    precio_input = os.environ.get("GEMINI_PRICE_INPUT_PER_1M")
    precio_output = os.environ.get("GEMINI_PRICE_OUTPUT_PER_1M")
    if precio_input and precio_output:
        costo = (
            uso.prompt_tokens * float(precio_input)
            + uso.completion_tokens * float(precio_output)
        ) / 1_000_000
        lineas.append(
            f"💵 Costo estimado: ${costo:.4f} USD (según GEMINI_PRICE_INPUT_PER_1M/GEMINI_PRICE_OUTPUT_PER_1M)"
        )

    return "\n".join(lineas)
