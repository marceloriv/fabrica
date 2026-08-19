"""Interfaz web local: uvicorn fabrica_prompts.web:app --reload

Modelo async con polling: POST /generar arranca la crew en un thread y devuelve un
job_id; el navegador consulta GET /estado/{job_id} cada 1s para la barra de progreso
real (4 pasos, uno por agente, vía task_callback de CrewAI) y el resultado final.
"""

import logging
import threading
import uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from .dominio import detectar_dominio, obtener_nombre_dominio
from .crew import build_llm, build_crew, ejecutar_con_reintento, formatear_uso
from .tools import parece_instruccion

logger = logging.getLogger(__name__)

app = FastAPI()
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# Un paso por agente de build_crew, en orden — la web los usa solo como etiqueta de
# progreso, no necesitan calzar con el `role` exacto (que en el Especialista es dinámico).
PASOS = ["Analista", "Especialista de dominio", "Arquitecto", "Mediador"]

# ponytail: dict en memoria de un solo proceso — alcanza para un uso local de una persona;
# si esto se expone a más gente, cambiar por algo con expiración/persistencia.
_JOBS: dict[str, dict] = {}


class SolicitudIn(BaseModel):
    solicitud: str


def _ejecutar_job(job_id: str, solicitud: str) -> None:
    job = _JOBS[job_id]
    dominio_codigo = detectar_dominio(solicitud)
    dominio_nombre = obtener_nombre_dominio(dominio_codigo)

    def avance(_task_output) -> None:
        job["paso"] = job["paso"] + 1

    try:
        llm = build_llm()
        crew = build_crew(dominio_nombre, llm, task_callback=avance)
        resultado_crew = ejecutar_con_reintento(crew, {"solicitud": solicitud})
    except ValueError as e:
        job.update(listo=True, error=f"Error de configuración: {e}")
        return
    except Exception as e:
        logger.exception("Error ejecutando la crew para la solicitud: %r", solicitud)
        job.update(listo=True, error=f"Error durante el proceso: {e}")
        return

    texto = str(resultado_crew).strip()
    job.update(
        listo=True,
        error=None,
        resultado={
            "dominio_nombre": dominio_nombre,
            "dominio_codigo": dominio_codigo,
            "vacio": not texto,
            "texto": texto,
            "advertencia_formato": bool(texto) and not parece_instruccion(texto),
            "uso": formatear_uso(resultado_crew) if texto else None,
        },
    )


@app.get("/")
def index(request: Request):
    return templates.TemplateResponse(request, "solicitud.html", {"pasos": PASOS})


@app.post("/generar")
def generar(payload: SolicitudIn):
    solicitud = payload.solicitud.strip()
    if len(solicitud) < 3:
        return {"error": "La solicitud debe tener al menos 3 caracteres."}

    job_id = uuid.uuid4().hex
    _JOBS[job_id] = {"paso": 0, "total": len(PASOS), "listo": False, "error": None, "resultado": None}
    threading.Thread(target=_ejecutar_job, args=(job_id, solicitud), daemon=True).start()
    return {"job_id": job_id}


@app.get("/estado/{job_id}")
def estado(job_id: str):
    job = _JOBS.get(job_id)
    if job is None:
        return {"error": "job_id desconocido (¿se reinició el servidor?)."}
    return job
