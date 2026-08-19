import re

from crewai.tools import tool

# Términos "técnicos": con mayúscula interna (FastAPI), dígitos (GPT-4), o separadores propios
# de nombres de tecnología (Node.js, C#, C++).
_PATRON_TERMINO_TECNICO = re.compile(r"\b[A-Za-zÀ-ÿ][\w.+#-]{2,}\b")

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
    candidatos = {
        c
        for c in _PATRON_TERMINO_TECNICO.findall(prompt_final)
        if re.search(r"[A-Z]", c[1:])
        or re.search(r"\d", c)
        or any(s in c for s in (".", "#", "+"))
    }
    sin_respaldo = sorted(c for c in candidatos if c.lower() not in contexto_lower)
    if not sin_respaldo:
        return "Todos los términos técnicos/nombres del prompt aparecen respaldados en el contexto."
    return (
        "Términos sin respaldo explícito en el Análisis/Especialidad (posibles alucinaciones "
        "a revisar): " + ", ".join(sin_respaldo)
    )
