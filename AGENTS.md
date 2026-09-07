# AGENTS.md

Guía técnica centralizada para agentes y desarrolladores que trabajan en este repositorio.

## Descripción del Proyecto

"Fábrica de Prompts" — genera un prompt optimizado o contenido directo listo para usar a partir de la solicitud en bruto del usuario, mediante una crew de cuatro agentes coordinados con CrewAI. Utiliza el proveedor nativo de Google Gemini (`crewai[google-genai]`), sin intermediarios de OpenAI ni GitHub Models.

---

## Configuración y Entorno — Requiere Python 3.12

**CrewAI no soporta Python 3.14** (`requires_python: <3.14,>=3.10` en PyPI). Instalarlo en un intérprete 3.14 resuelve silenciosamente a versiones obsoletas rotas (crewai 0.11.2). El proyecto utiliza un entorno virtual con Python 3.12:

```bash
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Ejecución

*(Nota: si el entorno ya está activado o usas Python global, puedes reemplazar `.\.venv\Scripts\python.exe` simplemente por `python` en los comandos siguientes)*

- **CLI puntual**:
  ```bash
  .\.venv\Scripts\python.exe -m fabrica_prompts.cli "tu solicitud de prompt"
  ```
- **CLI interactivo**:
  ```bash
  .\.venv\Scripts\python.exe -m fabrica_prompts.cli
  ```
- **Interfaz Web local (FastAPI con SSE streaming)**:
  ```bash
  .\.venv\Scripts\python.exe -m uvicorn fabrica_prompts.web:app --reload
  ```
- **Pruebas unitarias**:
  ```bash
  .\.venv\Scripts\python.exe -m pytest -v
  ```

### Variables de Entorno (`.env`)
- `GEMINI_API_KEY`: Requerida. Clave de API de Google AI Studio.
- `MODEL`: Opcional. Modelo de Gemini (por defecto: `gemini-3.5-flash-lite`).
- `GEMINI_TIMEOUT_SEGUNDOS`: Opcional. Timeout por llamada (por defecto: `60`).
- `SERPER_API_KEY`: Opcional. Habilita búsqueda web para el Especialista vía `SerperDevTool`.
- `GEMINI_PRICE_INPUT_PER_1M` / `GEMINI_PRICE_OUTPUT_PER_1M`: Opcionales. Costo estimado en reporte de uso.
- `LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`: Opcionales. Telemetría en LangSmith.

---

## Estructura del Código

Paquete plano sin capa `src/`:

```
fabrica/
├── Dockerfile                   # Build multi-stage python:3.12-slim
├── docker-compose.yml           # Servicio local web en 127.0.0.1:8000
├── requirements.txt             # Dependencias estrictas (sin lxml, jinja2 ni multipart)
├── AGENTS.md                    # Esta guía centralizada
├── README.md                    # Documentación técnica estricta del proyecto
├── fabrica_prompts/
│   ├── __init__.py              # Vacío intencionalmente (sin re-exports globales)
│   ├── cli.py                   # Punto de entrada CLI: main(), manejo de stdin/argv
│   ├── web.py                   # Punto de entrada FastAPI: FileResponse + SSE streaming
│   ├── crew.py                  # build_llm, build_crew, ejecutar_con_reintento, formatear_uso
│   ├── dominio.py               # detectar_dominio, obtener_nombre_dominio (local, regex precompilado)
│   ├── tools.py                 # verificar_grounding (tool del Mediador), parece_instruccion (heurística)
│   └── templates/
│       └── solicitud.html       # UI vanilla HTML5 + JS ReadableStream (sin Jinja)
└── tests/
    ├── test_dominio.py          # Pruebas de detección determinista de dominios
    ├── test_crew.py             # Pruebas de reintentos, timeouts y wiring de la crew
    ├── test_tools.py            # Pruebas de heurística de formato y grounding de tecnologías
    └── test_web.py              # Pruebas de endpoints FastAPI y streaming SSE
```

Cada nuevo módulo de producción debe tener un archivo de prueba correspondiente en `tests/`.

---

## Arquitectura y Pipeline

```
Usuario → detectar_dominio (local, regex) → Crew (Analista → Especialista → Arquitecto → Mediador) → Salida Final
```

Dos puntos de entrada consumen el módulo `crew`:
1. `fabrica_prompts/cli.py` (consola, síncrono).
2. `fabrica_prompts/web.py` (FastAPI, Server-Sent Events en tiempo real).

Ambos evalúan `parece_instruccion()` sobre el resultado final y muestran una advertencia si la salida parece una respuesta directa en lugar de un prompt (cuando el tipo de entrega es conversacional).

### Pipeline de los 4 Agentes (`Process.sequential`)

1. **Analista de Requerimientos**: Extrae objetivo, perfil de usuario, restricciones y criterios de éxito. Clasifica el **"Tipo de entrega"**: `'Instrucción para IA conversacional'` vs. `'Contenido directo para herramienta no conversacional'`. Fija la lista `Sub-temas a cubrir`.
2. **Especialista en {dominio}**: Rol contextualizado dinámicamente con el dominio detectado por `dominio.py`. Aporta mejores prácticas, riesgos y recomendaciones específicas. Utiliza `SerperDevTool()` únicamente si existe `SERPER_API_KEY` en el entorno; si falta, degrada a memoria interna del LLM sin fallar.
3. **Arquitecto Senior de Prompts**: Recibe el contexto acumulado de Analista + Especialista. Genera el borrador mapeando cada subtema a una sección dedicada con 2-3 subdirectivas basadas en los riesgos del especialista. Prohibido usar placeholders genéricos (`[INSERTAR AQUÍ]`). Si el tipo de entrega es conversacional, instruye a una IA ("Actúa como..."); si es contenido directo, emite el artefacto listo para usar.
4. **Mediador de Consistencia**: Recibe la traza completa (Analista + Especialista + Arquitecto).
   - *Paso 1 (Formato)*: Verifica coincidencia con el `Tipo de entrega`. Si hay desvío de formato (ej. saludo al lector o instrucción innecesaria en contenido directo), lo corrige inmediatamente.
   - *Paso 2 (Grounding)*: Poda datos o restricciones inventadas que no aparezcan en Analista ni Especialista. Tolera elaboración técnica razonable. Usa `tools.verificar_grounding` como soporte heurístico.
   - *Delegación puntual*: Tiene `allow_delegation=True` (`max_iter=8`) para formular consultas aclaratorias al Arquitecto como último recurso si el grounding es genuinamente ambiguo. Estructura asimétrica: el Arquitecto no puede re-delegar ni repreguntar.

---

## Detalles Críticos de Implementación

### Timeout en Proveedor Nativo de Gemini
`LLM(timeout=...)` en CrewAI solo se conecta a la ruta genérica de LiteLLM. El proveedor nativo de Gemini (`google-genai`) ignora `self.timeout` y solo lee `self.client_params`. La configuración correcta en `build_llm()` es:
```python
client_params={"http_options": genai_types.HttpOptions(timeout=timeout_segundos * 1000)}
```
Sin esto, llamadas bloqueadas a la API cuelgan indefinidamente.

### Política de Reintentos de Red
`crew.ejecutar_con_reintento()` captura:
- Errores de API: `google.genai.errors.ClientError` y `ServerError` (códigos 429, 500, 503).
- Errores de transporte: `ConnectionError`, `TimeoutError`, y explícitamente `httpx.TimeoutException` (que **no** hereda de `TimeoutError` de la biblioteca estándar).
Aplica backoff exponencial (1s a 60s) hasta un máximo de 5 intentos.

### Streaming SSE en `web.py`
- `POST /generar` valida longitud y retorna `StreamingResponse(media_type="text/event-stream")`.
- La ejecución de la crew corre en un hilo de trabajo (`asyncio.to_thread`).
- El callback síncrono `task_callback` envía eventos de avance a un `asyncio.Queue` thread-safe (`loop.call_soon_threadsafe`).
- No se mantiene estado en memoria (`_JOBS` eliminado).
- Soporta cancelación interactiva desde la UI mediante `AbortController` y detección de `CancelledError`.
- La UI sirve `solicitud.html` como archivo estático vía `FileResponse` (sin Jinja2).

### Heurística de Grounding (`tools.py`)
- `_PATRON_TERMINO_TECNICO`: Captura tecnologías con símbolos (`C#`, `C++`, `.NET`), acrónimos de 2+ letras (`API`, `SQL`, `REST`), términos con mayúscula interna (`FastAPI`, `PostgreSQL`), y nombres propios capitalizados.
- Filtra palabras de apertura de oración mediante `inicios_oracion` para evitar falsos positivos con verbos imperativos en español (`Despliega`, `Escribe`).
- Comprueba presencia en contexto con delimitadores estrictos de palabra `(?<!\w)...(?!\w)` para evitar falsos respaldos (ej. `"api"` dentro de `"rapidez"`).

---

## Historia del Proyecto

El sistema atravesó cuatro iteraciones antes de estabilizarse:
1. **Pipeline artesanal de 4 etapas**: Analista → Especialista → Arquitecto → Auditor, con bucle de corrección de hasta 3 rondas y parseo manual de JSON. Descartado por latencia (3-8 llamadas LLM secuenciales) y auto-aprobación complaciente del auditor.
2. **Colapso a llamada única**: Se eliminó el pipeline y se podaron `modelos.py` y `auditoria.py`.
3. **Reconstrucción con CrewAI (3 agentes)**: Diseñado para permitir acoplar herramientas independientes a agentes específicos (`SerperDevTool` en el Especialista).
4. **Incorporación del Mediador (4 agentes)**: Agente de consistencia y grounding single-pass sin bucle externo ni veredictos booleanos de rechazo.
5. **Modernización reactiva y poda**: Migración de polling HTTP a SSE streaming nativo en FastAPI, poda de dependencias (`lxml`, `python-multipart`, `jinja2`), precompilación de regex en dominios, y robustecimiento de regex en grounding.

---

## Principios de Desarrollo

- **Auditoría Ponytail**: No agregar dependencias si la biblioteca estándar o la plataforma lo cubren. Borrar antes que añadir.
- **Cambios quirúrgicos**: Modificar únicamente las líneas necesarias para cumplir el objetivo.
- **Sin código muerto**: Todo helper o import no utilizado debe removerse inmediatamente.
