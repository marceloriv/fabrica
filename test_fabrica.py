import pytest
from unittest.mock import MagicMock
from dominio import detectar_dominio, obtener_nombre_dominio
from crewai import Process, LLM
from google.genai import errors as genai_errors
from simple_main import ejecutar_con_reintento, build_crew, build_llm

def test_detectar_dominio():
    """Prueba que el dominio se detecte correctamente basándose en palabras clave."""
    assert detectar_dominio("Necesito escribir código en python") == "python"
    assert detectar_dominio("Generar una campaña de marketing digital") == "marketing"
    assert detectar_dominio("Cómo optimizar despliegues con Docker y Kubernetes") == "devops"
    assert detectar_dominio("hola mundo") == "general"

def test_obtener_nombre_dominio():
    """Prueba la traducción de código de dominio a su nombre legible."""
    assert obtener_nombre_dominio("python") == "Desarrollo de Software"
    assert obtener_nombre_dominio("marketing") == "Marketing Digital"
    assert obtener_nombre_dominio("inexistente") == "General"


def test_ejecutar_con_reintento_exitoso_sin_reintento():
    crew = MagicMock()
    crew.kickoff.return_value = "prompt final"
    resultado = ejecutar_con_reintento(crew, {"solicitud": "x"}, max_retries=3, initial_delay=1)
    assert resultado == "prompt final"
    crew.kickoff.assert_called_once()


def test_ejecutar_con_reintento_reintenta_ante_429(monkeypatch):
    crew = MagicMock()
    crew.kickoff.side_effect = [genai_errors.ClientError(429, {}), "prompt final"]
    sleeps = []
    monkeypatch.setattr("simple_main.time.sleep", sleeps.append)

    resultado = ejecutar_con_reintento(crew, {}, max_retries=3, initial_delay=1)

    assert resultado == "prompt final"
    assert crew.kickoff.call_count == 2
    assert sleeps == [1]


def test_ejecutar_con_reintento_no_reintenta_error_no_retryable(monkeypatch):
    crew = MagicMock()
    crew.kickoff.side_effect = genai_errors.ClientError(400, {})
    monkeypatch.setattr("simple_main.time.sleep", lambda s: pytest.fail("no debería dormir"))

    with pytest.raises(genai_errors.ClientError):
        ejecutar_con_reintento(crew, {}, max_retries=3, initial_delay=1)

    assert crew.kickoff.call_count == 1


def test_ejecutar_con_reintento_agota_reintentos():
    crew = MagicMock()
    crew.kickoff.side_effect = genai_errors.ClientError(503, {})

    with pytest.raises(genai_errors.ClientError):
        ejecutar_con_reintento(crew, {}, max_retries=3, initial_delay=0)

    assert crew.kickoff.call_count == 3


def test_ejecutar_con_reintento_backoff_exponencial(monkeypatch):
    crew = MagicMock()
    crew.kickoff.side_effect = [
        genai_errors.ClientError(429, {}),
        genai_errors.ClientError(429, {}),
        "ok",
    ]
    sleeps = []
    monkeypatch.setattr("simple_main.time.sleep", sleeps.append)

    resultado = ejecutar_con_reintento(crew, {}, max_retries=5, initial_delay=1, max_delay=60)

    assert resultado == "ok"
    assert sleeps == [1, 2]


def test_ejecutar_con_reintento_reintenta_error_de_red(monkeypatch):
    crew = MagicMock()
    crew.kickoff.side_effect = [ConnectionError("dns fail"), "ok"]
    monkeypatch.setattr("simple_main.time.sleep", lambda s: None)

    resultado = ejecutar_con_reintento(crew, {}, max_retries=3, initial_delay=1)

    assert resultado == "ok"


def test_build_crew_arma_3_agentes_en_orden():
    llm = LLM(model="gemini/gemini-3.5-flash-lite", api_key="fake-key")
    crew = build_crew("Desarrollo de Software", llm)

    assert [a.role for a in crew.agents] == [
        "Analista de Requerimientos",
        "Especialista en Desarrollo de Software",
        "Arquitecto Senior de Prompts",
    ]
    assert crew.process == Process.sequential


def test_build_crew_encadena_contexto_entre_tareas():
    llm = LLM(model="gemini/gemini-3.5-flash-lite", api_key="fake-key")
    crew = build_crew("Marketing Digital", llm)
    tarea_analisis, tarea_especialidad, tarea_prompt = crew.tasks

    assert tarea_especialidad.context == [tarea_analisis]
    assert tarea_prompt.context == [tarea_analisis, tarea_especialidad]


def test_build_llm_falla_sin_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ValueError):
        build_llm()
