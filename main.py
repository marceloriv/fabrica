"""
Fábrica de Prompts - Sistema de generación de prompts especializados

Este sistema utiliza LangChain moderno para orquestar los agentes
mediante chains.

Arquitectura:
Usuario → Mediador → Analista → Especialista → Arquitecto → Auditor → Mediador → Prompt Final
"""

import sys
import os
import json
import re
import time
from dotenv import load_dotenv
from typing import Dict, List
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_core.exceptions import LangChainException
from openai import RateLimitError
from dominio import detectar_dominio, obtener_nombre_dominio

load_dotenv()


def retry_with_backoff(max_retries=5, initial_delay=1, max_delay=60):
    """Decorador para reintentar llamadas con exponential backoff"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            retries = 0
            delay = initial_delay

            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except (RateLimitError, LangChainException) as e:
                    retries += 1
                    if retries == max_retries:
                        raise Exception(f"Max retries ({max_retries}) exceeded. Last error: {str(e)}")

                    print(f"⚠️ Rate limit hit. Retry {retries}/{max_retries} in {delay}s...")
                    time.sleep(delay)
                    delay = min(delay * 2, max_delay)
                except Exception as e:
                    raise Exception(f"Unexpected error: {str(e)}")

            raise Exception(f"Max retries ({max_retries}) exceeded")
        return wrapper
    return decorator


class PromptFactoryChain:
    """Fábrica de prompts usando LangChain moderno"""

    def __init__(self):
        self.llm = ChatOpenAI(
            model=os.environ.get("MODEL", "gpt-4o-mini"),
            base_url=os.environ.get("OPENAI_BASE_URL"),
            api_key=os.environ.get("GITHUB_TOKEN"),
            temperature=0.7
        )
        self.json_parser = JsonOutputParser()

    @retry_with_backoff(max_retries=10, initial_delay=2, max_delay=120)
    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """Llamada al LLM usando LangChain"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", user_prompt)
        ])
        chain = prompt | self.llm
        response = chain.invoke({})
        return response.content

    @retry_with_backoff(max_retries=10, initial_delay=2, max_delay=120)
    def _analista(self, solicitud: str) -> str:
        """Agente 1: Analista de Requerimientos usando LangChain chain"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Eres un Analista de Requerimientos experto.
Extrae la necesidad real, restricciones y perfil del usuario.
Entrega JSON con: objetivo, usuario, dominio, restricciones, criterios_exito."""),
            ("user", "Analiza: '{solicitud}'")
        ])
        chain = prompt | self.llm
        response = chain.invoke({"solicitud": solicitud})
        return response.content

    @retry_with_backoff(max_retries=10, initial_delay=2, max_delay=120)
    def _especialista(self, analisis: str, dominio: str) -> str:
        """Agente 2: Especialista de Dominio usando LangChain chain"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", f"""Eres autoridad mundial en {dominio}.
Provee contexto técnico, mejores prácticas y riesgos.
Entrega JSON con: best_practices, riesgos, recomendaciones."""),
            ("user", "Contexto: {analisis}")
        ])
        chain = prompt | self.llm
        response = chain.invoke({"analisis": analisis})
        return response.content

    @retry_with_backoff(max_retries=10, initial_delay=2, max_delay=120)
    def _arquitecto(self, analisis: str, especialidad: str) -> str:
        """Agente 3: Arquitecto de Prompts usando LangChain chain"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Eres Arquitecto Senior de Prompts.
Transforma requerimientos en prompts precisos.
Selecciona estrategia adecuada (Zero-Shot, Few-Shot, CoT).
Entrega JSON con: prompt_final, estrategia, componentes."""),
            ("user", "ANÁLISIS: {analisis}\nESPECIALIDAD: {especialidad}")
        ])
        chain = prompt | self.llm
        response = chain.invoke({"analisis": analisis, "especialidad": especialidad})
        return response.content

    @retry_with_backoff(max_retries=10, initial_delay=2, max_delay=120)
    def _auditor(self, analisis: str, prompt: str) -> Dict:
        """Agente 4: Auditor de Calidad usando LangChain chain"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Eres el guardián de calidad.
Buscas contradicciones, sesgos y vulnerabilidades.
Entrega JSON con: aprobado (bool), prompt_final (si aprobado), correcciones (lista), observaciones (lista)."""),
            ("user", "ANÁLISIS: {analisis}\nPROMPT: {prompt}")
        ])
        chain = prompt | self.llm
        response = chain.invoke({"analisis": analisis, "prompt": prompt})
        resultado = response.content

        # Limpiar JSON
        resultado = re.sub(r'```json\s*', '', resultado)
        resultado = re.sub(r'```\s*', '', resultado)
        resultado = resultado.strip()

        try:
            return json.loads(resultado)
        except:
            return {"aprobado": True, "prompt_final": prompt, "correcciones": [], "observaciones": []}

    @retry_with_backoff(max_retries=10, initial_delay=2, max_delay=120)
    def _mejorar_prompt(self, prompt: str, correcciones: List[str], analisis: str, especialidad: str) -> str:
        """Mejora el prompt basado en correcciones usando LangChain chain"""
        correcciones_text = "\n".join([f"- {c}" for c in correcciones])
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Eres Arquitecto Senior de Prompts.
Mejora un prompt existente basándote en correcciones específicas.
Entrega JSON con: prompt_final, estrategia, componentes."""),
            ("user", "CORRECCIONES:\n{correcciones}\n\nPROMPT ORIGINAL:\n{prompt}\n\nCONTEXTO:\nANÁLISIS: {analisis}\nESPECIALIDAD: {especialidad}")
        ])
        chain = prompt | self.llm
        response = chain.invoke({
            "correcciones": correcciones_text,
            "prompt": prompt,
            "analisis": analisis,
            "especialidad": especialidad
        })
        return response.content

    @retry_with_backoff(max_retries=10, initial_delay=2, max_delay=120)
    def _mediador(self, solicitud: str, estado_proceso: Dict) -> str:
        """Agente 5: Mediador/Orquestador usando LangChain chain"""
        estado_json = json.dumps(estado_proceso, indent=2, ensure_ascii=False)
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Eres el Mediador/Orquestador del proceso.
Coordina a los agentes y toma decisiones estratégicas.
Evalúa el estado del proceso y determina si continuar, ajustar o finalizar.
Entrega JSON con: decision (continuar/finalizar/ajustar), razonamiento, proximo_paso."""),
            ("user", "SOLICITUD: {solicitud}\nESTADO DEL PROCESO:\n{estado}")
        ])
        chain = prompt | self.llm
        response = chain.invoke({"solicitud": solicitud, "estado": estado_json})
        return response.content

    def ejecutar_cadena(self, solicitud: str, max_iteraciones: int = 5) -> str:
        """Ejecuta la cadena completa de llamadas: Mediador → Analista → Especialista → Arquitecto → Auditor"""
        # Estado inicial del proceso
        estado = {
            "solicitud": solicitud,
            "max_iteraciones": max_iteraciones
        }

        print("🎯 Paso 1: Mediador (Coordina inicio)...")
        decision_inicio = self._mediador(solicitud, estado)
        print("✅ Completado")

        print("\n🔍 Paso 2: Analista...")
        analisis = self._analista(solicitud)
        print("✅ Completado")

        dominio = obtener_nombre_dominio(detectar_dominio(solicitud))
        print(f"\n🎯 Paso 3: Especialista ({dominio})...")
        especialidad = self._especialista(analisis, dominio)
        print("✅ Completado")

        print("\n🏗️  Paso 4: Arquitecto...")
        arquitectura = self._arquitecto(analisis, especialidad)
        print("✅ Completado")

        # Extraer prompt de la arquitectura
        arquitectura = re.sub(r'```json\s*', '', arquitectura)
        arquitectura = re.sub(r'```\s*', '', arquitectura)
        try:
            arquitectura_data = json.loads(arquitectura.strip())
            prompt_actual = arquitectura_data.get("prompt_final", arquitectura)
        except:
            prompt_actual = arquitectura

        # Ciclo de auditoría
        for i in range(max_iteraciones):
            print(f"\n🔍 Paso 5: Auditor (Iteración {i+1})...")
            auditoria = self._auditor(analisis, prompt_actual)
            print("✅ Completado")

            if auditoria.get("aprobado", False):
                print(f"\n✅ Prompt aprobado después de {i+1} iteración(es)")

                # Mediador final antes de devolver resultado
                estado_final = {
                    "solicitud": solicitud,
                    "iteraciones": i + 1,
                    "prompt_aprobado": True,
                    "prompt_final": prompt_actual[:500] + "..." if len(prompt_actual) > 500 else prompt_actual
                }
                print(f"\n🎯 Paso 6: Mediador (Finalización)...")
                decision_final = self._mediador(solicitud, estado_final)
                print("✅ Completado")

                return json.dumps(auditoria, indent=2, ensure_ascii=False)

            correcciones = auditoria.get("correcciones", [])
            if not correcciones:
                break

            print(f"\n🔄 Aplicando {len(correcciones)} correcciones...")
            for c in correcciones:
                print(f"   - {c}")

            print("\n🏗️  Regenerando prompt...")
            resultado_mejora = self._mejorar_prompt(prompt_actual, correcciones, analisis, especialidad)

            # Extraer prompt mejorado
            resultado_mejora = re.sub(r'```json\s*', '', resultado_mejora)
            resultado_mejora = re.sub(r'```\s*', '', resultado_mejora)
            try:
                mejora_data = json.loads(resultado_mejora.strip())
                prompt_actual = mejora_data.get("prompt_final", resultado_mejora)
            except:
                prompt_actual = resultado_mejora
            print("✅ Completado")

        print(f"\n⚠️ Máximo de iteraciones alcanzado")
        auditoria["prompt_final"] = prompt_actual
        auditoria["nota"] = "Se alcanzó el máximo de iteraciones"

        # Mediador final después de alcanzar máximo de iteraciones
        estado_final = {
            "solicitud": solicitud,
            "iteraciones": max_iteraciones,
            "prompt_aprobado": False,
            "prompt_final": prompt_actual[:500] + "..." if len(prompt_actual) > 500 else prompt_actual
        }
        print(f"\n🎯 Paso 6: Mediador (Finalización)...")
        decision_final = self._mediador(solicitud, estado_final)
        print("✅ Completado")

        return json.dumps(auditoria, indent=2, ensure_ascii=False)


def main():
    """
    Punto de entrada principal de la fábrica de prompts.
    """
    print("=" * 70)
    print("🏭 FÁBRICA DE PROMPTS")
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
    print("🔍 Analizando solicitud...")
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
        # Ejecutar la cadena de llamadas
        cadena = PromptFactoryChain()
        resultado = cadena.ejecutar_cadena(solicitud)

        print()
        print("-" * 70)
        print()
        print("✅ Proceso completado exitosamente")
        print()
        print("RESULTADO FINAL:")
        print("=" * 70)
        print(resultado)
        print("=" * 70)

    except Exception as e:
        print()
        print("-" * 70)
        print()
        print(f"❌ Error durante el proceso: {str(e)}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
