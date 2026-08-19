# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

"Fábrica de Prompts" — generates an optimized LLM prompt from a user's raw request, using a CrewAI crew of three role-based agents. Uses Gemini directly (`crewai[google-genai]` native provider), not OpenAI or GitHub Models.

## Setup — requires Python 3.12

**CrewAI does not support Python 3.14** (`requires_python: <3.14,>=3.10` on PyPI) — installing it under an unpinned 3.14 interpreter silently resolves to crewai 0.11.2 (Jan 2024, broken against modern langchain), not a real error. This repo's system Python is 3.14, so a dedicated venv exists at `.venv` built with Python 3.12 (installed via `winget install Python.Python.3.12`, invoked as `py -3.12`).

```bash
py -3.12 -m venv .venv                        # only if .venv doesn't exist
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe simple_main.py "tu solicitud de prompt"
.venv\Scripts\python.exe -m pytest -q
```

Requires `.env` (copy from `.env.example`): `GEMINI_API_KEY`, `MODEL`.

Windows console encoding note: if running outside the project's normal terminal, `print()` of the emoji banner can raise `UnicodeEncodeError` under cp1252 — set `PYTHONIOENCODING=utf-8` in that case (not needed in a UTF-8-capable terminal).

## Architecture

```
Usuario → detectar_dominio (local, no LLM) → Crew (Analista → Especialista → Arquitecto) → Prompt Final
```

`simple_main.py`: `main()` detects the domain via `dominio.py`'s `detectar_dominio` (keyword-count matcher against `DOMINIOS`, no LLM), then `build_crew(dominio_nombre, llm)` wires three `crewai.Agent`s into a sequential `Crew`:

1. **Analista de Requerimientos** — infers objective, user profile, constraints, success criteria.
2. **Especialista en {dominio}** — role name is built from the locally-detected domain; contributes best practices/risks/recommendations.
3. **Arquitecto Senior de Prompts** — receives both prior tasks as `context` and produces the final prompt text.

`build_llm()` configures one shared `crewai.LLM(model=f"gemini/{MODEL}", api_key=GEMINI_API_KEY)` — CrewAI's native Gemini provider (`google-genai` extra), no OpenAI-compatible endpoint involved. `crew.kickoff(inputs={"solicitud": ...})` returns a `CrewOutput`; `str()`/`print()` of it is the last task's raw text — no JSON envelope, no manual parsing.

No tools are attached to any agent yet — this is deliberate scaffolding for real ones (web search, RAG, external validation) to be added per-agent later; see the `ponytail:` comment in `build_crew`. Don't add tools speculatively.

`dominio.py`'s keyword matching special-cases: mentions of "ponytail", "audit", or "opencode" are steered toward the `python` (software dev) domain rather than being misread as unrelated topics — same steering is echoed in the Analista's `backstory`.

## History

This went through two prior shapes before landing on CrewAI:
1. A 4-stage hand-rolled LLM pipeline (Analista → Especialista → Arquitecto → Auditor, up to 3 correction iterations, JSON-parsed between steps via regex fence-stripping) plus unused `modelos.py` Pydantic schemas and an unwired `auditoria.py` rule-based validator.
2. Collapsed to a single LLM call after review found the intermediate steps added latency (3-8 sequential LLM calls per request) without adding reasoning a single well-scoped prompt couldn't do, and the self-audit loop rarely rejected its own output. `modelos.py` and `auditoria.py` were deleted as dead code.
3. Rebuilt as the current 3-agent CrewAI crew (no Auditor stage) once there was a concrete reason to hold that structure: near-term plans to attach real tools (web search, RAG, external validation) to specific agents — something a single flat prompt can't do per-role.
