import re

try:
    from crewai.tools import tool
except ImportError:
    def tool(name=None):
        return lambda f: f

# Captura tecnologías con símbolos (C++, C#, .NET), nombres propios y términos técnicos.
_PATRON_TERMINO_TECNICO = re.compile(
    r"(?<!\w)(?:C\+\+|C#|\.NET)(?!\w)|(?:\b[A-Za-zÀ-ÿ][\w.-]*\b)"
)

# Palabras funcionales y comunes en español a ignorar como candidatos técnicos.
_PALABRAS_COMUNES = {
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "al", "en", "para", "por",
    "con", "sin", "sobre", "entre", "tras", "durante", "hasta", "hacia", "según", "segun",
    "actúa", "actua", "como", "tu", "tarea", "es", "debes", "debe", "crea", "genera", "incluye",
    "usa", "utiliza", "este", "esta", "estos", "estas", "cada", "no", "si", "y", "o", "pero",
    "además", "ademas", "ejemplo", "sección", "seccion", "guía", "guia", "objetivo", "formato",
    "salida", "paso", "pasos", "instrucción", "instruccion", "prompt", "final", "muy", "más", "mas",
    "que", "qué", "cual", "cuál", "cómo", "como", "cuando", "cuándo", "donde", "dónde", "todo", "toda",
    "todos", "todas", "otro", "otra", "otros", "otras", "mismo", "misma", "tanto", "tanta",
    "experto", "experta", "clave", "nivel", "sistema", "usuario", "perfil", "resultado",
}

# Aperturas típicas de una respuesta directa al usuario final (saludo, título de guía) en vez
# de una instrucción dirigida a una IA ejecutora — señal de que el Arquitecto/Mediador
# contestaron la solicitud en lugar de generar el prompt.
_PATRONES_RESPUESTA_DIRECTA = re.compile(
    r"^\s*(¡?hola\b|¡?bienvenid|claro[,.!]|aquí\s+ten[ée]s|aquí\s+est[áa]|#{1,3}\s)",
    re.IGNORECASE,
)


def parece_instruccion(texto: str) -> bool:
    """Heurística determinística (sin LLM): False si el texto arranca como si ya fuera la
    respuesta directa al usuario final (saludo, título de guía en markdown, etc.) en vez de
    una instrucción dirigida a una IA ejecutora ('Actúa como...'). No es una prueba
    exhaustiva — solo atrapa los patrones de arranque más comunes de esta falla."""
    return not _PATRONES_RESPUESTA_DIRECTA.match(texto)


@tool("verificar_grounding")
def verificar_grounding(prompt_final: str, contexto: str) -> str:
    """Extrae términos técnicos y nombres propios del prompt_final (tecnologías, versiones,
    herramientas) y devuelve cuáles NO aparecen en el contexto (Análisis + Especialidad
    combinados), como pista de posibles alucinaciones a revisar."""
    contexto_lower = contexto.lower()
    inicios_oracion = set(re.findall(r"(?:^|[.!?\n]\s*)([A-Za-zÀ-ÿ]+)", prompt_final))
    candidatos = {
        c
        for c in _PATRON_TERMINO_TECNICO.findall(prompt_final)
        if c.lower() not in _PALABRAS_COMUNES
        and (
            c in ("C++", "C#", ".NET")
            or bool(re.search(r"\d", c))
            or bool(re.search(r"[A-Z]{2,}", c))
            or bool(re.search(r"[A-Z]", c[1:]))
            or (bool(re.search(r"^[A-Z]", c)) and c not in inicios_oracion and len(c) >= 3)
            or any(s in c for s in (".", "+", "#"))
        )
    }

    sin_respaldo = sorted(
        c
        for c in candidatos
        if not re.search(r"(?<!\w)" + re.escape(c.lower()) + r"(?!\w)", contexto_lower)
    )

    if not sin_respaldo:
        return "Todos los términos técnicos/nombres del prompt aparecen respaldados en el contexto."
    return (
        "Términos sin respaldo explícito en el Análisis/Especialidad (posibles alucinaciones "
        "a revisar): " + ", ".join(sin_respaldo)
    )
