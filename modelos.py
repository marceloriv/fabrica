from pydantic import BaseModel
from typing import List, Optional


class AnalisisOutput(BaseModel):
    objetivo: str
    usuario: str
    dominio: str
    restricciones: List[str]
    criterios_exito: List[str]


class EspecialidadOutput(BaseModel):
    best_practices: List[str]
    riesgos: List[str]
    recomendaciones: List[str]


class ArquitecturaOutput(BaseModel):
    prompt_final: str
    estrategia: str
    componentes: List[str]


class AuditoriaOutput(BaseModel):
    aprobado: bool
    prompt_final: Optional[str] = None
    correcciones: List[str] = []
    observaciones: List[str] = []
