# AGENTS.md
- Estructura: paquete `fabrica_prompts/` (cli.py, web.py, crew.py, dominio.py, tools.py) + `tests/`
- Punto de entrada CLI: `.venv\Scripts\python.exe -m fabrica_prompts.cli "solicitud"`
- Punto de entrada web (local, sin auth): `.venv\Scripts\python.exe -m uvicorn fabrica_prompts.web:app --reload`
- Pruebas: `.venv\Scripts\python.exe -m pytest`
- Configuración: `.env` requerido (`GEMINI_API_KEY`, `MODEL=gemini-3.5-flash-lite`)
- Stack: `crewai` (Agent/Task/Crew, 4 agentes con `crewai-tools`), `fastapi`+`uvicorn` (web), venv Python 3.12 en `.venv` (CrewAI no soporta 3.14 todavía)

<!-- ponytail: configuración mínima -->
