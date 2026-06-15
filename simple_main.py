"""
Fábrica de Prompts - Implementación simplificada

Esta versión utiliza GitHub Models (compatible con OpenAI SDK).

Arquitectura:
Usuario → Analista → Especialista → Arquitecto → Auditor → Prompt Final
"""

import sys
import os
from typing import Dict, List
from dotenv import load_dotenv

# Cargar variables de entorno desde archivo .env
load_dotenv()

from dominio import detectar_dominio, obtener_nombre_dominio
from modelos import (
    AnalisisOutput,
    EspecialidadOutput,
    ArquitecturaOutput,
    AuditoriaOutput,
)

# Try to import OpenAI, provide helpful error if not installed
try:
    from openai import OpenAI

    print("✅ Cliente OpenAI importado correctamente.")
except ImportError:
    print("❌ Error: OpenAI library not installed")
    print("Please install it with: pip install openai")
    sys.exit(1)


class SimplePromptFactory:
    """Fábrica de prompts simplificada usando OpenAI directamente"""

    def __init__(self, base_url: str = None, api_key: str = None):
        """Inicializa la fábrica con la configuración de GitHub Models"""
        self.base_url = base_url or os.environ.get("OPENAI_BASE_URL")
        self.api_key = api_key or os.environ.get("GITHUB_TOKEN")

        if not self.base_url or not self.api_key:
            raise ValueError(
                "OPENAI_BASE_URL and GITHUB_TOKEN environment variables not set"
            )

        self.client = OpenAI(base_url=self.base_url, api_key=self.api_key)

    def _call_openai(self, system_prompt: str, user_prompt: str) -> str:
        """Llama a la API de OpenAI con los prompts dados"""
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"Error calling GitHub Models API: {str(e)}")

    def analizar_solicitud(self, solicitud: str) -> Dict:
        """Paso 1: Analista de Requerimientos"""
        system_prompt = """Eres un Analista de Requerimientos experto.
Tu objetivo es extraer la necesidad real, restricciones y perfil del usuario a partir de la solicitud inicial.
Debes leer entre líneas, definir claramente el perfil del usuario final y establecer los criterios de éxito del proyecto.
Entrega tu análisis en formato JSON con las siguientes claves:
- objetivo: El objetivo principal del proyecto
- usuario: El perfil del usuario final
- dominio: El dominio del proyecto
- restricciones: Lista de restricciones
- criterios_exito: Lista de criterios de éxito"""

        user_prompt = f"Analiza la siguiente solicitud: '{solicitud}'"

        resultado = self._call_openai(system_prompt, user_prompt)
        return {"analisis": resultado, "solicitud_original": solicitud}

    def especializar_dominio(self, analisis: Dict) -> Dict:
        """Paso 2: Especialista de Dominio"""
        dominio_codigo = detectar_dominio(analisis["solicitud_original"])
        dominio_nombre = obtener_nombre_dominio(dominio_codigo)

        system_prompt = f"""Eres una autoridad mundial en {dominio_nombre}.
Tu trabajo es proveer el contexto técnico, táctico y estratégico necesario.
Identificas riesgos ocultos y recomiendas las mejores prácticas de la industria.
Entrega tu respuesta en formato JSON con las siguientes claves:
- best_practices: Lista de mejores prácticas
- riesgos: Lista de riesgos potenciales
- recomendaciones: Lista de recomendaciones"""

        user_prompt = f"Provee conocimiento especializado para: {analisis['analisis']}"

        resultado = self._call_openai(system_prompt, user_prompt)
        return {"especialidad": resultado, "dominio": dominio_nombre}

    def construir_prompt(self, analisis: Dict, especialidad: Dict) -> Dict:
        """Paso 3: Arquitecto de Prompts"""
        system_prompt = """Eres un Arquitecto Senior de Prompts. Tu función es transformar requerimientos,
análisis de negocio y conocimiento especializado en prompts altamente precisos y reutilizables.
Nunca asumes información no validada. Tu prioridad es: Claridad, Precisión, Reproducibilidad y Consistencia.
Seleccionas automáticamente la mejor estrategia (Zero-Shot, Few-Shot, CoT, etc.) según la complejidad.
Entrega tu respuesta en formato JSON con las siguientes claves:
- prompt_final: El prompt final estructurado y optimizado
- estrategia: La estrategia de prompt engineering utilizada
- componentes: Lista de componentes del prompt"""

        user_prompt = f"""Construye el prompt final usando:
ANÁLISIS: {analisis['analisis']}
ESPECIALIDAD: {especialidad['especialidad']}"""

        resultado = self._call_openai(system_prompt, user_prompt)
        return {"arquitectura": resultado}

    def auditar_prompt(self, analisis: Dict, arquitectura: Dict) -> Dict:
        """Paso 4: Auditor de Calidad"""
        system_prompt = """Eres el guardián final de la calidad. Buscas contradicciones lógicas, sesgos,
fugas de contexto y vulnerabilidades (como posibles prompt injections). Si el prompt no es
perfecto o no cumple con los criterios de éxito del Analista, detallas los fallos.
Entrega tu respuesta en formato JSON con las siguientes claves:
- aprobado: Boolean indicando si el prompt está aprobado
- prompt_final: El prompt final (si está aprobado) o None
- correcciones: Lista de correcciones requeridas (si no está aprobado)
- observaciones: Lista de observaciones adicionales"""

        user_prompt = f"""Audita el siguiente prompt:
ANÁLISIS ORIGINAL: {analisis['analisis']}
PROMPT GENERADO: {arquitectura['arquitectura']}"""

        resultado = self._call_openai(system_prompt, user_prompt)
        return {"auditoria": resultado}

    def aplicar_correcciones(
        self,
        arquitectura: Dict,
        correcciones: List[str],
        analisis: Dict,
        especialidad: Dict,
    ) -> Dict:
        """Paso 5: Aplicar correcciones del auditor y regenerar prompt"""
        system_prompt = """Eres un Arquitecto Senior de Prompts. Tu función es mejorar un prompt existente
basándote en correcciones específicas de un auditor de calidad.
Debes mantener la estructura y el propósito original del prompt, pero incorporar todas las correcciones
sugeridas para lograr la máxima calidad y precisión.
Entrega tu respuesta en formato JSON con las siguientes claves:
- prompt_final: El prompt mejorado y corregido
- estrategia: La estrategia de prompt engineering utilizada
- componentes: Lista de componentes del prompt"""

        correcciones_texto = "\n".join(
            [f"- {correccion}" for correccion in correcciones]
        )
        user_prompt = f"""Mejora el siguiente prompt aplicando estas correcciones:
CORRECCIONES:
{correcciones_texto}

PROMPT ORIGINAL:
{arquitectura['arquitectura']}

CONTEXTO ADICIONAL:
ANÁLISIS: {analisis['analisis']}
ESPECIALIDAD: {especialidad['especialidad']}"""

        resultado = self._call_openai(system_prompt, user_prompt)
        return {"arquitectura": resultado}

    def ejecutar_fabrica(self, solicitud: str, max_iteraciones: int = 3) -> str:
        """Ejecuta el pipeline completo de la fábrica con ciclo de retroalimentación"""
        print("🔍 Paso 1: Analizando solicitud...")
        analisis = self.analizar_solicitud(solicitud)
        print(f"✅ Análisis completado")

        print("\n🎯 Paso 2: Especializando por dominio...")
        especialidad = self.especializar_dominio(analisis)
        print(f"✅ Especialización completada: {especialidad['dominio']}")

        print("\n🏗️  Paso 3: Construyendo prompt...")
        arquitectura = self.construir_prompt(analisis, especialidad)
        print(f"✅ Prompt construido")

        # Ciclo de auditoría y mejora
        iteracion = 0
        while iteracion < max_iteraciones:
            iteracion += 1
            print(f"\n🔍 Paso 4: Auditando prompt (Iteración {iteracion})...")
            auditoria = self.auditar_prompt(analisis, arquitectura)
            print(f"✅ Auditoría completada")

            # Parsear resultado de auditoría
            try:
                import json
                import re

                # Limpiar el JSON si viene con formato markdown
                auditoria_text = auditoria["auditoria"]
                # Eliminar backticks si existen
                auditoria_text = re.sub(r"```json\s*", "", auditoria_text)
                auditoria_text = re.sub(r"```\s*", "", auditoria_text)
                auditoria_text = auditoria_text.strip()

                auditoria_data = json.loads(auditoria_text)

                if auditoria_data.get("aprobado", False):
                    print(f"\n✅ Prompt aprobado después de {iteracion} iteración(es)")
                    return auditoria["auditoria"]

                correcciones = auditoria_data.get("correcciones", [])
                observaciones = auditoria_data.get("observaciones", [])

                if not correcciones and iteracion == 1:
                    # Si no hay correcciones en la primera iteración, aprobar
                    print(f"\n✅ Prompt aprobado (sin correcciones críticas)")
                    return auditoria["auditoria"]

                print(f"\n🔄 Aplicando {len(correcciones)} corrección(es)...")
                for i, correccion in enumerate(correcciones, 1):
                    print(f"   {i}. {correccion}")

                if observaciones:
                    print(f"\n📝 Observaciones:")
                    for i, obs in enumerate(observaciones, 1):
                        print(f"   {i}. {obs}")

                # Aplicar correcciones
                print(f"\n🏗️  Regenerando prompt con correcciones...")
                arquitectura = self.aplicar_correcciones(
                    arquitectura, correcciones, analisis, especialidad
                )
                print(f"✅ Prompt regenerado")

            except json.JSONDecodeError:
                print(
                    f"\n⚠️ Error al parsear respuesta de auditoría, aprobando por defecto"
                )
                return auditoria["auditoria"]

        # Si se alcanzó el máximo de iteraciones, devolver el prompt actual
        print(f"\n⚠️ Se alcanzó el máximo de {max_iteraciones} iteraciones")
        print(f"📝 Devolviendo el prompt actual (aunque puede requerir mejoras)")

        # Extraer el prompt actual de la arquitectura
        try:
            import json
            import re

            arquitectura_text = arquitectura["arquitectura"]
            arquitectura_text = re.sub(r"```json\s*", "", arquitectura_text)
            arquitectura_text = re.sub(r"```\s*", "", arquitectura_text)
            arquitectura_text = arquitectura_text.strip()

            arquitectura_data = json.loads(arquitectura_text)
            prompt_actual = arquitectura_data.get("prompt_final", arquitectura_text)

            # Crear respuesta final con el prompt actual
            resultado_final = json.dumps(
                {
                    "aprobado": False,
                    "prompt_final": prompt_actual,
                    "correcciones": auditoria_data.get("correcciones", []),
                    "observaciones": auditoria_data.get("observaciones", []),
                    "nota": "Se alcanzó el máximo de iteraciones. El prompt puede requerir ajustes manuales.",
                },
                indent=2,
                ensure_ascii=False,
            )

            return resultado_final
        except (json.JSONDecodeError, KeyError):
            # Si hay error al parsear, devolver la arquitectura tal cual
            return arquitectura["arquitectura"]


def main():
    """Punto de entrada principal"""
    print("=" * 70)
    print("🏭 FÁBRICA DE PROMPTS (Versión Simplificada)")
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

    if not solicitud or solicitud.strip() == "":
        print("❌ Error: La solicitud no puede estar vacía")
        return

    print()
    print(f"📝 Solicitud: {solicitud}")
    print()

    # Detectar el dominio
    dominio_codigo = detectar_dominio(solicitud)
    dominio_nombre = obtener_nombre_dominio(dominio_codigo)
    print(f"🎯 Dominio detectado: {dominio_nombre} ({dominio_codigo})")
    print()
    print("⚙️  Iniciando proceso de generación...")
    print("-" * 70)
    print()

    try:
        # Crear la fábrica y ejecutar
        fabrica = SimplePromptFactory()
        resultado = fabrica.ejecutar_fabrica(solicitud)

        print()
        print("-" * 70)
        print()
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
        print("    set OPENAI_BASE_URL=https://models.inference.ai.azure.com")
        print("    set GITHUB_TOKEN=tu_github_token")
        print("  Linux/Mac:")
        print("    export OPENAI_BASE_URL=https://models.inference.ai.azure.com")
        print("    export GITHUB_TOKEN=tu_github_token")

    except Exception as e:
        print()
        print("-" * 70)
        print()
        print(f"❌ Error durante el proceso: {str(e)}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
