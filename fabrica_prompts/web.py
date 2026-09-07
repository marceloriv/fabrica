"""Interfaz web local: uvicorn fabrica_prompts.web:app --reload

Streaming en tiempo real con SSE: POST /generar inicia la crew en un worker thread
y emite eventos 'progreso' (uno por cada agente completado) y 'resultado' final.
"""

import asyncio
import json
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from .dominio import detectar_dominio, obtener_nombre_dominio
from .tools import parece_instruccion

try:
    from .crew import build_llm, build_crew, ejecutar_con_reintento, formatear_uso
except ImportError:
    build_llm = None
    build_crew = None
    ejecutar_con_reintento = None
    formatear_uso = None

logger = logging.getLogger(__name__)

app = FastAPI()
HTML_PATH = Path(__file__).parent / "templates" / "solicitud.html"

# Un paso por agente de build_crew, en orden
PASOS = ["Analista", "Especialista de dominio", "Arquitecto", "Mediador"]


class SolicitudIn(BaseModel):
    solicitud: str


async def _generar_stream(solicitud: str):
    dominio_codigo = detectar_dominio(solicitud)
    dominio_nombre = obtener_nombre_dominio(dominio_codigo)

    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()
    paso_actual = 0

    def avance(_task_output) -> None:
        nonlocal paso_actual
        paso_actual += 1
        agente = PASOS[paso_actual - 1] if paso_actual <= len(PASOS) else "Finalizando"
        loop.call_soon_threadsafe(
            queue.put_nowait,
            {"tipo": "progreso", "paso": paso_actual, "total": len(PASOS), "agente": agente},
        )

    def ejecutar() -> None:
        try:
            llm = build_llm()
            crew = build_crew(dominio_nombre, llm, task_callback=avance)
            resultado_crew = ejecutar_con_reintento(crew, {"solicitud": solicitud})

            texto = str(resultado_crew).strip()
            loop.call_soon_threadsafe(
                queue.put_nowait,
                {
                    "tipo": "resultado",
                    "dominio_nombre": dominio_nombre,
                    "dominio_codigo": dominio_codigo,
                    "vacio": not texto,
                    "texto": texto,
                    "advertencia_formato": bool(texto) and not parece_instruccion(texto),
                    "uso": formatear_uso(resultado_crew) if (texto and formatear_uso) else None,
                },
            )
        except ValueError as e:
            loop.call_soon_threadsafe(
                queue.put_nowait,
                {"tipo": "error", "mensaje": f"Error de configuración: {e}"},
            )
        except Exception as e:
            logger.exception("Error ejecutando la crew para la solicitud: %r", solicitud)
            loop.call_soon_threadsafe(
                queue.put_nowait,
                {"tipo": "error", "mensaje": f"Error durante el proceso: {e}"},
            )
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)

    task = asyncio.create_task(asyncio.to_thread(ejecutar))

    try:
        while True:
            item = await queue.get()
            if item is None:
                break
            yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
    except asyncio.CancelledError:
        logger.info("Cliente desconectado del stream SSE")
        raise
    finally:
        if not task.done():
            task.cancel()


@app.get("/")
def index():
    return FileResponse(HTML_PATH)


@app.post("/generar")
def generar(payload: SolicitudIn):
    solicitud = payload.solicitud.strip()
    if len(solicitud) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La solicitud debe tener al menos 3 caracteres.",
        )

    return StreamingResponse(
        _generar_stream(solicitud),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
