import time
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
import fabrica_prompts.web as web

client = TestClient(web.app)


def test_index_muestra_el_formulario():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "<form" in resp.text
    assert "solicitud" in resp.text


def test_generar_rechaza_solicitud_corta_sin_llamar_a_la_crew(monkeypatch):
    llamada = MagicMock()
    monkeypatch.setattr(web, "build_llm", llamada)

    resp = client.post("/generar", json={"solicitud": "  "})

    assert resp.status_code == 200
    assert "al menos 3" in resp.json()["error"]
    llamada.assert_not_called()


def test_ejecutar_job_guarda_resultado_en_jobs(monkeypatch):
    monkeypatch.setattr(web, "build_llm", MagicMock())
    monkeypatch.setattr(web, "build_crew", MagicMock())
    monkeypatch.setattr(
        web, "ejecutar_con_reintento", MagicMock(return_value="Actúa como una prueba")
    )

    web._JOBS["job-test"] = {"paso": 0, "total": 4, "listo": False, "error": None, "resultado": None}
    web._ejecutar_job("job-test", "una solicitud de prueba con python")

    job = web._JOBS["job-test"]
    assert job["listo"] is True
    assert job["error"] is None
    assert job["resultado"]["texto"] == "Actúa como una prueba"
    assert job["resultado"]["dominio_codigo"] == "python"


def test_ejecutar_job_guarda_error_de_configuracion(monkeypatch):
    monkeypatch.setattr(web, "build_llm", MagicMock(side_effect=ValueError("sin key")))

    web._JOBS["job-err"] = {"paso": 0, "total": 4, "listo": False, "error": None, "resultado": None}
    web._ejecutar_job("job-err", "otra solicitud")

    job = web._JOBS["job-err"]
    assert job["listo"] is True
    assert "sin key" in job["error"]


def test_generar_arranca_job_y_estado_lo_expone(monkeypatch):
    monkeypatch.setattr(web, "build_llm", MagicMock())
    monkeypatch.setattr(web, "build_crew", MagicMock())
    monkeypatch.setattr(
        web, "ejecutar_con_reintento", MagicMock(return_value="Actúa como otra prueba")
    )

    resp = client.post("/generar", json={"solicitud": "necesito un prompt de prueba"})
    assert resp.status_code == 200
    job_id = resp.json()["job_id"]

    for _ in range(50):
        estado = client.get(f"/estado/{job_id}").json()
        if estado["listo"]:
            break
        time.sleep(0.05)
    else:
        pytest.fail("el job no terminó a tiempo")

    assert estado["error"] is None
    assert estado["resultado"]["texto"] == "Actúa como otra prueba"


def test_estado_job_inexistente_devuelve_error():
    resp = client.get("/estado/no-existe")
    assert resp.status_code == 200
    assert "error" in resp.json()
