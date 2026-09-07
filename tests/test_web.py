import json
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
import fabrica_prompts.web as web

client = TestClient(web.app)


def test_index_muestra_el_formulario():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "<form" in resp.text
    assert "solicitud" in resp.text
    assert "btn-cancelar" in resp.text


def test_generar_rechaza_solicitud_corta(monkeypatch):
    llamada = MagicMock()
    monkeypatch.setattr(web, "build_llm", llamada)

    resp = client.post("/generar", json={"solicitud": "  "})

    assert resp.status_code == 400
    assert "al menos 3" in resp.json()["detail"]
    llamada.assert_not_called()


def test_generar_stream_emite_progreso_y_resultado(monkeypatch):
    def mock_build_crew(dominio_nombre, llm, task_callback=None):
        if task_callback:
            task_callback(MagicMock())
        return MagicMock()

    monkeypatch.setattr(web, "build_llm", MagicMock())
    monkeypatch.setattr(web, "build_crew", mock_build_crew)
    monkeypatch.setattr(
        web, "ejecutar_con_reintento", MagicMock(return_value="Actúa como un experto")
    )

    resp = client.post("/generar", json={"solicitud": "solicitud con python"})
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]

    eventos = [
        json.loads(linea[5:].strip())
        for linea in resp.text.strip().split("\n\n")
        if linea.startswith("data:")
    ]

    tipos = [e["tipo"] for e in eventos]
    assert "progreso" in tipos
    assert "resultado" in tipos

    resultado = next(e for e in eventos if e["tipo"] == "resultado")
    assert resultado["texto"] == "Actúa como un experto"
    assert resultado["dominio_codigo"] == "python"


def test_generar_stream_emite_error_de_configuracion(monkeypatch):
    monkeypatch.setattr(web, "build_llm", MagicMock(side_effect=ValueError("sin key")))

    resp = client.post("/generar", json={"solicitud": "solicitud valida"})
    assert resp.status_code == 200

    eventos = [
        json.loads(linea[5:].strip())
        for linea in resp.text.strip().split("\n\n")
        if linea.startswith("data:")
    ]

    assert len(eventos) == 1
    assert eventos[0]["tipo"] == "error"
    assert "sin key" in eventos[0]["mensaje"]
