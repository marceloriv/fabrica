# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

"Fábrica de Prompts" — generates an optimized LLM prompt from a user's raw request, using a CrewAI crew of four role-based agents. Uses Gemini directly (`crewai[google-genai]` native provider), not OpenAI or GitHub Models.

## Setup — requires Python 3.12

**CrewAI does not support Python 3.14** (`requires_python: <3.14,>=3.10` on PyPI) — installing it under an unpinned 3.14 interpreter silently resolves to crewai 0.11.2 (Jan 2024, broken against modern langchain), not a real error. This repo's system Python is 3.14, so a dedicated venv exists at `.venv` built with Python 3.12 (installed via `winget install Python.Python.3.12`, invoked as `py -3.12`).

```bash
py -3.12 -m venv .venv                        # only if .venv doesn't exist
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m fabrica_prompts.cli "tu solicitud de prompt"
.venv\Scripts\python.exe -m pytest -q
```

Requires `.env` (copy from `.env.example`): `GEMINI_API_KEY`, `MODEL`. Optional: `SERPER_API_KEY` (web search for the Especialista), `GEMINI_PRICE_INPUT_PER_1M`/`GEMINI_PRICE_OUTPUT_PER_1M` (cost estimate).

Windows console encoding note: if running outside the project's normal terminal, `print()` of the emoji banner can raise `UnicodeEncodeError` under cp1252 — set `PYTHONIOENCODING=utf-8` in that case (not needed in a UTF-8-capable terminal).

## Structure

Flat package, no `src/` layer (this is an internal CLI, not something distributed via `pip install`):

```
fabrica_prompts/
├── cli.py     # entry point: main(), argv/stdin handling, printing
├── web.py      # entry point: FastAPI app, local-only HTML form (no auth)
├── crew.py     # build_llm, build_crew (agents + tasks), ejecutar_con_reintento, formatear_uso
├── dominio.py   # detectar_dominio, obtener_nombre_dominio — local, no LLM
└── tools.py     # verificar_grounding (Mediador's grounding tool), parece_instruccion (drift check)
tests/
├── test_dominio.py
├── test_crew.py
├── test_tools.py
└── test_web.py
```

Mirrors the module split: a new module gets a matching test file, not everything piling into one `test_fabrica.py`. `__init__.py` is intentionally empty — no public API re-exports until something outside the package actually imports from it.

## Architecture

```
Usuario → detectar_dominio (local, no LLM) → Crew (Analista → Especialista → Arquitecto → Mediador) → Prompt Final
```

Two entry points share the same `crew` module: `fabrica_prompts/cli.py` (terminal, synchronous) and `fabrica_prompts/web.py` (local FastAPI, no auth). Both call `parece_instruccion()` after a successful run and show a warning if the output doesn't look like an instruction (see "Prompt vs. direct answer" below) — deterministic, no LLM call.

`web.py` is async/polling, not a plain synchronous form POST — it needs a real progress bar (4 steps, one per agent), which a blocking request can't report mid-flight. `POST /generar` (a Pydantic `SolicitudIn` body) validates length, creates a job id, and starts `_ejecutar_job` on a daemon `threading.Thread` (not FastAPI `BackgroundTasks`, since that only runs *after* the response is sent — here the response with the job id has to go out *before* work starts). Progress comes from `Crew(task_callback=...)`, which CrewAI calls once per completed task; the callback just increments `_JOBS[job_id]["paso"]`. `GET /estado/{job_id}` polls that in-memory dict — no HTML/Jinja involved in the result at all, `index()` renders `solicitud.html` once (empty form + the `PASOS` label list via `{{ pasos | tojson }}`), and all four templates.js there (`llenar`/`mostrar` helpers, `<template>` tags for error/resultado) build the DOM from JSON via `textContent` — inherently XSS-safe, no `html.escape()` needed anywhere in this file for that reason (the earlier synchronous version needed it because it interpolated user content directly into server-rendered HTML strings; this version never does that). `_JOBS` is a single-process in-memory dict with no expiry — fine for local single-user use, noted with a `ponytail:` comment; would need real storage before this could serve more than one person.

`fabrica_prompts/cli.py`: `main()` detects the domain via `dominio.py`'s `detectar_dominio` (keyword-count matcher against `DOMINIOS`, word-boundary matched, no LLM), then `crew.build_crew(dominio_nombre, llm)` wires four `crewai.Agent`s into a sequential `Crew`:

1. **Analista de Requerimientos** — infers objective, user profile, constraints, success criteria, and **"Tipo de entrega"**: `Instrucción para IA conversacional` vs. `Contenido directo para herramienta no conversacional` (see below — this drives what "the prompt" means for the rest of the pipeline).
2. **Especialista en {dominio}** — role name is built from the locally-detected domain; contributes best practices/risks/recommendations. Gets `SerperDevTool()` (web search) attached only if `SERPER_API_KEY` is set — degrades to model-only knowledge otherwise, doesn't error.
3. **Arquitecto Senior de Prompts** — receives both prior tasks as `context` and produces the draft final prompt text.
4. **Mediador de Consistencia** — receives all three prior tasks as `context`; checks the Arquitecto's draft for claims (technologies, numbers, constraints) not grounded in the Analista's or Especialista's output, strips or reformulates the ungrounded parts, returns the final prompt. No approve/reject verdict, no manual correction loop in our own code (see "Mediador vs. the old Auditor" below) — it can, however, `allow_delegation=True` (capped `max_iter=8`) to ask the Arquitecto a direct question via CrewAI's built-in delegation tool when grounding is genuinely ambiguous; this is CrewAI's own single-task mechanism, not a loop we wrote, and the Mediador's backstory tells it to use it as a last resort, not routinely. Has `tools.verificar_grounding` attached: a plain-Python (no LLM call) regex heuristic that flags technical-looking terms in the draft not present in the combined Analista+Especialista text — the agent treats its output as a starting point, not a verdict, since it can false-positive on synonyms/generic terms.

`crew.build_llm()` configures one shared `crewai.LLM(model=f"gemini/{MODEL}", api_key=GEMINI_API_KEY)` — CrewAI's native Gemini provider (`google-genai` extra), no OpenAI-compatible endpoint involved. **Timeout gotcha, found via a real hang in production use**: `LLM(timeout=...)` only wires into CrewAI's generic litellm-based path — the native Gemini provider (`GeminiCompletion`, what we actually use) never reads `self.timeout`, only `self.client_params`. The real fix is `client_params={"http_options": genai_types.HttpOptions(timeout=<ms>)}`; without it, a hung network call to Gemini blocks forever with no way out. `crew.ejecutar_con_reintento()` wraps `crew.kickoff(inputs={"solicitud": ...})` with exponential backoff on `google.genai.errors.ClientError/ServerError` (429/500/503) and on `ConnectionError`/`TimeoutError`/`httpx.TimeoutException` — note `httpx.TimeoutException` does **not** subclass the builtin `TimeoutError` (separate hierarchy), so it has to be listed explicitly in `NETWORK_ERRORS` or a real timeout escapes the retry loop entirely. The native provider has no retry of its own. `str()`/`print()` of the result is the last task's raw text — no JSON envelope, no manual parsing. `crew.formatear_uso()` returns real token counts from `resultado.token_usage` after a successful run (both `cli.py` and `web.py` print/render it), and an estimated USD cost only if `GEMINI_PRICE_INPUT_PER_1M`/`GEMINI_PRICE_OUTPUT_PER_1M` are set — no hardcoded price table, since `gemini-3.5-flash-lite` is a post-training-cutoff model name with no verified pricing.

Before adding a tool to the Analista or Arquitecto, confirm there's a concrete need — the two tools that exist (Especialista's web search, Mediador's grounding check) were each added for a specific, stated reason, not speculatively.

`dominio.py`'s keyword matching special-cases: mentions of "ponytail", "audit", or "opencode" are steered toward the `python` (software dev) domain rather than being misread as unrelated topics — same steering is echoed in the Analista's `backstory`.

### Prompt vs. direct answer — and the "Tipo de entrega" split

Real failure mode observed in production use: the Arquitecto/Mediador can drift into writing the *answer* to the solicitud (second-person content addressed to the end reader, e.g. starting with "¡Hola!" or a markdown guide title) instead of a *prompt* (an instruction addressed to whatever AI will execute it later, e.g. "Actúa como..."). This is non-deterministic — the same solicitud can produce either shape across runs — so it's guarded at two layers: the Arquitecto's `goal`/backstory and the Mediador's `goal`/backstory both carry an explicit, repeated rule against it (checked before grounding).

That rule isn't universal, though — it only holds when the Analista classifies "Tipo de entrega" as `Instrucción para IA conversacional`. The other case, `Contenido directo para herramienta no conversacional`, exists because of a real product gap: a request like "necesito un prompt para Midjourney de X" doesn't want a meta-instruction telling some other AI to go write a Midjourney prompt — it wants the actual Midjourney-ready text (positive/negative blocks, native params like `--v 6.0 --style raw`) *as the deliverable itself*, because the target tool (an image generator, a SQL engine, a linter config) has no conversational AI in the loop to receive instructions. For that case the rule flips: wrapping the output in "Actúa como..." is the bug, not the fix. Both the Arquitecto and Mediador check `Tipo de entrega` before deciding which shape is correct — see their `goal`/`backstory` in `crew.py`.

`tools.parece_instruccion()` is a cheap regex-based last-resort check at the CLI/web layer — it only recognizes the instruction-shaped case (flags greeting/title patterns as suspicious) and has no visibility into `Tipo de entrega`, so it can false-positive-warn on a legitimate `Contenido directo` result (e.g. a Midjourney prompt). That's a known, accepted limitation, not a bug to chase: it's a non-blocking warning ("revisalo antes de usarlo"), and plumbing the classification through to that layer would need parsing an intermediate task's output just to silence an optional banner — not worth the fragility.

### Mediador vs. the old Auditor

The Mediador is not the old Auditor pattern (see History, step 1) reintroduced — it's built specifically to avoid why that one got cut: it never emits an approve/reject verdict, it produces plain text like every other task (no JSON parsing to go fragile), and its scope is narrowly grounding-only — checking claims against what the Analista/Especialista actually said, not judging style or quality. If a future change adds a boolean verdict or JSON output back onto this agent, that's the old anti-pattern re-emerging — don't.

The one deliberate exception, added after explicit user confirmation despite this warning: `allow_delegation=True` (capped `max_iter=8`) lets the Mediador ask the Arquitecto a direct question mid-task when grounding is ambiguous. This is *not* the old Auditor's regenerate-and-reaudit loop — there's still no code in `crew.py` that re-runs a task or loops `crew.kickoff()`; it's CrewAI's own built-in "ask coworker" tool, used inside the Mediador's single task execution, and the backstory explicitly tells it this is a last resort, not the default path. If you're extending this, keep it that way: a question, not a rewrite request, and don't let it grow into a second correction loop.

## History

This went through three prior shapes before landing on the current one:
1. A 4-stage hand-rolled LLM pipeline (Analista → Especialista → Arquitecto → Auditor, up to 3 correction iterations, JSON-parsed between steps via regex fence-stripping) plus unused `modelos.py` Pydantic schemas and an unwired `auditoria.py` rule-based validator.
2. Collapsed to a single LLM call after review found the intermediate steps added latency (3-8 sequential LLM calls per request) without adding reasoning a single well-scoped prompt couldn't do, and the self-audit loop rarely rejected its own output. `modelos.py` and `auditoria.py` were deleted as dead code.
3. Rebuilt as a 3-agent CrewAI crew (no Auditor stage) once there was a concrete reason to hold that structure: near-term plans to attach real tools (web search, RAG, external validation) to specific agents — something a single flat prompt can't do per-role.
4. A 4th agent, Mediador de Consistencia, was added for hallucination-grounding on the Arquitecto's output — see "Mediador vs. the old Auditor" above for how it avoids repeating step 1's mistake.
