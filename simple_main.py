"""
Fábrica de Prompts - CrewAI

Usa Gemini vía litellm (GEMINI_API_KEY, sin pasar por el endpoint OpenAI-compatible).

Arquitectura:
Usuario → Crew (Analista → Especialista → Arquitecto) → Prompt Final
"""

import sys
import os
import time
from dotenv import load_dotenv

# Cargar variables de entorno desde archivo .env
load_dotenv()

from dominio import detectar_dominio, obtener_nombre_dominio
from crewai import Agent, Task, Crew, Process, LLM
from google.genai import errors as genai_errors

DEFAULT_MODEL = "gemini-3.5-flash-lite"

# Errores de red/servidor que ameritan reintento (además de los códigos HTTP de genai_errors)
NETWORK_ERRORS = (ConnectionError, TimeoutError)


def build_llm() -> LLM:
    """Configura el LLM (Gemini) que van a compartir los agentes de la crew"""
    api_key = (os.environ.get("GEMINI_API_KEY") or "").strip()
    model = os.environ.get("MODEL", DEFAULT_MODEL)

    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set")

    return LLM(model=f"gemini/{model}", api_key=api_key, temperature=0.7)


def build_crew(dominio_nombre: str, llm: LLM) -> Crew:
    """Arma la crew de 3 roles: Analista → Especialista → Arquitecto"""
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

    especialista = Agent(
        role=f"Especialista en {dominio_nombre}",
        goal=f"A partir del análisis del Analista, aportar mejores prácticas, riesgos y recomendaciones propias de {dominio_nombre} que el Arquitecto pueda incorporar directamente al prompt final.",
        backstory=(
            f"Autoridad mundial en {dominio_nombre}, con conocimiento técnico, táctico y estratégico del área. "
            "Trabajás siempre sobre el análisis que te entrega el Analista: nunca repetís su trabajo, lo "
            "complementás con el conocimiento de dominio que él no tiene."
        ),
        llm=llm,
        verbose=False,
    )

    arquitecto = Agent(
        role="Arquitecto Senior de Prompts",
        goal="Combinar el análisis del Analista y las recomendaciones del Especialista en un único prompt final: claro, preciso, reproducible y consistente, con la estrategia de prompt engineering más adecuada (Zero-Shot, Few-Shot, Chain-of-Thought, etc.).",
        backstory=(
            "Nunca asume información no validada. Sos el último eslabón de la cadena: tu trabajo es de "
            "síntesis, no de invención — si el Analista o el Especialista dejaron algo sin definir, señalalo "
            "en el prompt final en vez de inventarlo."
        ),
        llm=llm,
        verbose=False,
    )

    tarea_analisis = Task(
        description="Analiza esta solicitud de usuario: '{solicitud}'. Definí el objetivo real, el perfil del usuario final, las restricciones implícitas y los criterios de éxito.",
        expected_output=(
            "Exactamente estas cuatro secciones, cada una con contenido concreto extraído de la solicitud "
            "(no genérico):\n"
            "Objetivo: <objetivo real de la solicitud>\n"
            "Usuario: <perfil del usuario final>\n"
            "Restricciones: <restricciones implícitas o explícitas>\n"
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
            "Con el análisis del Analista y las mejores prácticas/riesgos/recomendaciones del Especialista, "
            "construí el prompt final optimizado para la solicitud: '{solicitud}'. Incorporá las restricciones "
            "del análisis y los riesgos del especialista como instrucciones concretas dentro del prompt, no "
            "como referencia vaga a 'las buenas prácticas'."
        ),
        expected_output="El prompt final, listo para usar, sin explicaciones ni comentarios meta.",
        agent=arquitecto,
        context=[tarea_analisis, tarea_especialidad],
    )

    return Crew(
        agents=[analista, especialista, arquitecto],
        tasks=[tarea_analisis, tarea_especialidad, tarea_prompt],
        process=Process.sequential,
        verbose=False,
    )
    # ponytail: sin tools todavía (solo roles de texto). Agregar Tool a un agente
    # (ej. búsqueda web al Especialista, RAG al Analista) cuando haya una necesidad real.


def ejecutar_con_reintento(crew: Crew, inputs: dict, max_retries=5, initial_delay=1, max_delay=60):
    """Ejecuta crew.kickoff() con reintento y backoff ante rate limits o errores transitorios del servidor"""
    delay = initial_delay
    for intento in range(1, max_retries + 1):
        try:
            return crew.kickoff(inputs=inputs)
        except (genai_errors.ClientError, genai_errors.ServerError) as e:
            code = getattr(e, "code", None)
            if code not in (429, 500, 503) or intento == max_retries:
                raise
            print(f"⚠️ Error temporal ({code}). Reintento {intento}/{max_retries} en {delay}s...")
            time.sleep(delay)
            delay = min(delay * 2, max_delay)
        except NETWORK_ERRORS as e:
            if intento == max_retries:
                raise
            print(f"⚠️ Error de red ({e}). Reintento {intento}/{max_retries} en {delay}s...")
            time.sleep(delay)
            delay = min(delay * 2, max_delay)


def main():
    """Punto de entrada principal"""
    print("=" * 70)
    print("🏭 FÁBRICA DE PROMPTS (CrewAI)")
    print("=" * 70)
    print()

    # Obtener la solicitud del usuario
    if len(sys.argv) > 1:
        solicitud = " ".join(sys.argv[1:])
    else:
        print("Por favor, describe qué tipo de prompt necesitas:")
        print("(Ejemplo: 'Necesito un prompt para analizar datos de ventas en Python')")
        print()
        solicitud = input("> ")

    if not solicitud.strip():
        print("❌ Error: La solicitud no puede estar vacía")
        return

    print()
    print(f"📝 Solicitud: {solicitud}")
    print()

    # Detectar el dominio (local, sin LLM)
    dominio_codigo = detectar_dominio(solicitud)
    dominio_nombre = obtener_nombre_dominio(dominio_codigo)
    print(f"🎯 Dominio detectado: {dominio_nombre} ({dominio_codigo})")
    print()
    print("⚙️  Ejecutando crew...")
    print("-" * 70)
    print()

    try:
        llm = build_llm()
        crew = build_crew(dominio_nombre, llm)
        resultado = ejecutar_con_reintento(crew, {"solicitud": solicitud})

        print()
        print("-" * 70)
        print()
        if not str(resultado).strip():
            print("⚠️ La crew terminó sin generar un prompt final (salida vacía)")
        else:
            print("✅ Proceso completado exitosamente")
            print()
            print("RESULTADO FINAL:")
            print("=" * 70)
            print(resultado)
            print("=" * 70)

    except ValueError as e:
        print()
        print("-" * 70)
        print()
        print(f"❌ Error de configuración: {str(e)}")
        print()
        print("Por favor, configura las variables de entorno:")
        print("  Windows:")
        print("    set GEMINI_API_KEY=tu_gemini_api_key")
        print(f"    set MODEL={DEFAULT_MODEL}")
        print("  Linux/Mac:")
        print("    export GEMINI_API_KEY=tu_gemini_api_key")
        print(f"    export MODEL={DEFAULT_MODEL}")

    except Exception as e:
        print()
        print("-" * 70)
        print()
        print(f"❌ Error durante el proceso: {str(e)}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
