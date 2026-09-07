"""Punto de entrada: python -m fabrica_prompts.cli ["solicitud"]

Con argumento: corre una vez y termina (uso en scripts).
Sin argumento: pregunta solicitudes en loop hasta que escribas vacío/salir (uso interactivo).
"""

import sys
from dotenv import load_dotenv

# Cargar variables de entorno desde archivo .env
load_dotenv()

from .dominio import detectar_dominio, obtener_nombre_dominio
from .crew import (
    DEFAULT_MODEL,
    build_llm,
    build_crew,
    ejecutar_con_reintento,
    formatear_uso,
)
from .tools import parece_instruccion

COMANDOS_SALIDA = {"salir", "exit", "quit"}


def procesar_solicitud(solicitud: str) -> None:
    """Corre la crew para una solicitud y muestra el resultado (o el error)."""
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

        print(f"\n{'-' * 70}\n")
        if not str(resultado).strip():
            print("⚠️ La crew terminó sin generar un prompt final (salida vacía)")
        else:
            print("✅ Proceso completado exitosamente")
            if not parece_instruccion(str(resultado)):
                print(
                    "⚠️ El resultado no parece un prompt (instrucción para una IA), sino una "
                    "respuesta directa — revisalo antes de usarlo."
                )
            print()
            print("RESULTADO FINAL:")
            print("=" * 70)
            print(resultado)
            print("=" * 70)
            uso = formatear_uso(resultado)
            if uso:
                print()
                print(uso)

    except ValueError as e:
        print(f"\n{'-' * 70}\n")
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
        print(f"\n{'-' * 70}\n")
        print(f"❌ Error durante el proceso: {str(e)}")
        import traceback

        traceback.print_exc()


def main():
    """Punto de entrada principal"""
    print("=" * 70)
    print("🏭 FÁBRICA DE PROMPTS (CrewAI)")
    print("=" * 70)
    print()

    if len(sys.argv) > 1:
        procesar_solicitud(" ".join(sys.argv[1:]))
        return

    print("Por favor, describe qué tipo de prompt necesitas.")
    print("(Ejemplo: 'Necesito un prompt para analizar datos de ventas en Python')")
    print(f"Escribí vacío o '{'/'.join(COMANDOS_SALIDA)}' para salir.")
    print()

    while True:
        solicitud = input("> ").strip()
        if not solicitud or solicitud.lower() in COMANDOS_SALIDA:
            return
        procesar_solicitud(solicitud)
        print()


if __name__ == "__main__":
    main()
