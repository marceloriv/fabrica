import httpx
import pytest
from unittest.mock import MagicMock
from crewai import Process, LLM
from google.genai import errors as genai_errors
from fabrica_prompts.crew import ejecutar_con_reintento, build_crew, build_llm


def test_ejecutar_con_reintento_exitoso_sin_reintento():
    crew = MagicMock()
    crew.kickoff.return_value = "prompt final"
    resultado = ejecutar_con_reintento(
        crew, {"solicitud": "x"}, max_retries=3, initial_delay=1
    )
    assert resultado == "prompt final"
    crew.kickoff.assert_called_once()


def test_ejecutar_con_reintento_reintenta_ante_429(monkeypatch):
    crew = MagicMock()
    crew.kickoff.side_effect = [genai_errors.ClientError(429, {}), "prompt final"]
    sleeps = []
    monkeypatch.setattr("fabrica_prompts.crew.time.sleep", sleeps.append)

    resultado = ejecutar_con_reintento(crew, {}, max_retries=3, initial_delay=1)

    assert resultado == "prompt final"
    assert crew.kickoff.call_count == 2
    assert sleeps == [1]


def test_ejecutar_con_reintento_no_reintenta_error_no_retryable(monkeypatch):
    crew = MagicMock()
    crew.kickoff.side_effect = genai_errors.ClientError(400, {})
    monkeypatch.setattr(
        "fabrica_prompts.crew.time.sleep", lambda s: pytest.fail("no debería dormir")
    )

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
    monkeypatch.setattr("fabrica_prompts.crew.time.sleep", sleeps.append)

    resultado = ejecutar_con_reintento(
        crew, {}, max_retries=5, initial_delay=1, max_delay=60
    )

    assert resultado == "ok"
    assert sleeps == [1, 2]


def test_ejecutar_con_reintento_reintenta_error_de_red(monkeypatch):
    crew = MagicMock()
    crew.kickoff.side_effect = [ConnectionError("dns fail"), "ok"]
    monkeypatch.setattr("fabrica_prompts.crew.time.sleep", lambda s: None)

    resultado = ejecutar_con_reintento(crew, {}, max_retries=3, initial_delay=1)

    assert resultado == "ok"


def test_ejecutar_con_reintento_reintenta_ante_timeout_de_httpx(monkeypatch):
    """httpx.TimeoutException NO hereda de TimeoutError — regresión real: sin esto,
    un timeout de la llamada a Gemini se escapaba del retry sin reintentar."""
    crew = MagicMock()
    crew.kickoff.side_effect = [httpx.ReadTimeout("timed out"), "ok"]
    monkeypatch.setattr("fabrica_prompts.crew.time.sleep", lambda s: None)

    resultado = ejecutar_con_reintento(crew, {}, max_retries=3, initial_delay=1)

    assert resultado == "ok"


def test_build_llm_fija_timeout_al_proveedor_nativo(monkeypatch):
    """El kwarg timeout= de LLM() no llega al proveedor nativo de Gemini — solo
    client_params->http_options.timeout lo hace. Sin esto, una llamada colgada no corta."""
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    monkeypatch.setenv("GEMINI_TIMEOUT_SEGUNDOS", "45")

    llm = build_llm()

    http_options = llm.client_params["http_options"]
    assert http_options.timeout == 45_000


def test_build_crew_arma_4_agentes_en_orden():
    llm = LLM(model="gemini/gemini-3.5-flash-lite", api_key="fake-key")
    crew = build_crew("Desarrollo de Software", llm)

    assert [a.role for a in crew.agents] == [
        "Analista de Requerimientos",
        "Especialista en Desarrollo de Software",
        "Arquitecto Senior de Prompts",
        "Mediador de Consistencia",
    ]
    assert crew.process == Process.sequential


def test_mediador_puede_delegar_al_arquitecto_con_tope():
    llm = LLM(model="gemini/gemini-3.5-flash-lite", api_key="fake-key")
    crew = build_crew("Desarrollo de Software", llm)
    mediador = crew.agents[3]

    assert mediador.role == "Mediador de Consistencia"
    assert mediador.allow_delegation is True
    assert mediador.max_iter == 8


def test_build_crew_encadena_contexto_entre_tareas():
    llm = LLM(model="gemini/gemini-3.5-flash-lite", api_key="fake-key")
    crew = build_crew("Marketing Digital", llm)
    tarea_analisis, tarea_especialidad, tarea_prompt, tarea_mediacion = crew.tasks

    assert tarea_especialidad.context == [tarea_analisis]
    assert tarea_prompt.context == [tarea_analisis, tarea_especialidad]
    assert tarea_mediacion.context == [tarea_analisis, tarea_especialidad, tarea_prompt]


def test_build_llm_falla_sin_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ValueError):
        build_llm()
