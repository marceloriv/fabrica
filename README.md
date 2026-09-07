# Fabrica de Prompts

## Descripcion

Sistema de generacion y optimizacion de prompts y contenidos directos estructurados para Inteligencia Artificial. Utiliza un pipeline secuencial de 4 agentes de CrewAI (`Process.sequential`) con el proveedor nativo de Google Gemini (`crewai[google-genai]`), ejecutado sobre Python 3.12.

### Arquitectura de Agentes

El flujo de procesamiento opera en cascada acumulativa:

1. **Analista de Requerimientos**: Analiza la solicitud cruda del usuario, extrae objetivo, usuario final, restricciones de contenido, restricciones del prompt, criterios de exito y clasifica el `Tipo de entrega` (`Instruccion para IA conversacional` vs. `Contenido directo para herramienta no conversacional`).
2. **Especialista en {dominio}**: Rol contextualizado por clasificacion determinista previa de palabras clave (`dominio.py`). Aporta mejores practicas, riesgos y recomendaciones especificas del area. Dispone de busqueda web via `SerperDevTool` si se configura `SERPER_API_KEY`.
3. **Arquitecto Senior de Prompts**: Integra el analisis y el conocimiento de dominio. Construye una seccion por cada subtema identificado con 2 a 3 subdirectivas basadas en los riesgos del especialista. Si el tipo de entrega es conversacional genera directivas tipo "Actua como..."; si es contenido directo genera la salida lista para usar (ej. parametros de Midjourney, SQL, configuraciones).
4. **Mediador de Consistencia**: Valida que el formato del resultado coincida con el `Tipo de entrega`. Realiza control de grounding con la herramienta `verificar_grounding` para eliminar o relativizar afirmaciones tecnicas no presentes en las salidas del Analista o Especialista. Dispone de delegacion asimetrica puntual hacia el Arquitecto (`allow_delegation=True`, `max_iter=8`) para resolver dudas de grounding.

---

## Sintaxis / Interfaz

### Requisitos de Entorno
- Python >= 3.10, < 3.14 (requerido 3.12 debido a incompatibilidad de CrewAI con Python 3.14).

```bash
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Variables de Entorno

Archivo `.env` en la raiz del proyecto:

| Variable | Tipo | Requerida | Descripcion |
|---|---|---|---|
| `GEMINI_API_KEY` | `str` | Si | Clave de autenticacion para la API de Google Gemini. |
| `MODEL` | `str` | No | Nombre del modelo Gemini. Valor por defecto: `gemini-3.5-flash-lite`. |
| `GEMINI_TIMEOUT_SEGUNDOS` | `int` (inferido) | No | Tiempo maximo en segundos por llamada a la API. Valor por defecto: `60`. |
| `SERPER_API_KEY` | `str` | No | Clave para `SerperDevTool`. Habilita busqueda web al Especialista de dominio. |
| `GEMINI_PRICE_INPUT_PER_1M` | `float` (inferido) | No | Precio en USD por millon de tokens de entrada para calculo de costos. |
| `GEMINI_PRICE_OUTPUT_PER_1M` | `float` (inferido) | No | Precio en USD por millon de tokens de salida para calculo de costos. |
| `LANGSMITH_TRACING` | `str` | No | Habilita rastreo en LangSmith (`"true"` o `""`). |
| `LANGSMITH_API_KEY` | `str` | No | Clave de API para LangSmith. |
| `LANGSMITH_PROJECT` | `str` | No | Identificador de proyecto en LangSmith. |

### Interfaces de Entrada

#### 1. Linea de Comandos (CLI)
Punto de entrada: `fabrica_prompts.cli`

```bash
# Modo de ejecucion directa (un solo paso)
.venv\Scripts\python.exe -m fabrica_prompts.cli "<solicitud>"

# Modo interactivo continuo
.venv\Scripts\python.exe -m fabrica_prompts.cli
```

Comandos de salida interactiva: `salir`, `exit`, `quit` o linea vacia.

#### 2. Interfaz Web HTTP (FastAPI)
Punto de entrada: `fabrica_prompts.web:app`

```bash
.venv\Scripts\python.exe -m uvicorn fabrica_prompts.web:app --host 127.0.0.1 --port 8000
```

- **`GET /`**: Retorna `solicitud.html` (`FileResponse`, media type `text/html`).
- **`POST /generar`**:
  - Encabezados: `Content-Type: application/json`
  - Cuerpo: `{"solicitud": "<texto de al menos 3 caracteres>"}`
  - Respuesta exitosa: `StreamingResponse` con media type `text/event-stream` (Server-Sent Events).
  - Eventos emitidos en el stream:
    - `data: {"tipo": "progreso", "paso": int, "total": int, "agente": str}`
    - `data: {"tipo": "resultado", "dominio_nombre": str, "dominio_codigo": str, "vacio": bool, "texto": str, "advertencia_formato": bool, "uso": str | null}`
    - `data: {"tipo": "error", "mensaje": str}`

#### 3. Despliegue en Contenedores (Docker)

```bash
# Iniciar servicio web en http://127.0.0.1:8000
docker compose up -d

# Ejecutar CLI puntual dentro del contenedor
docker compose run --rm fabrica-prompts python -m fabrica_prompts.cli "<solicitud>"
```

---

## Ejemplo de uso

### Ejecucion via CLI

```bash
.venv\Scripts\python.exe -m fabrica_prompts.cli "Necesito un prompt para analizar logs de errores en Python con FastAPI"
```

Salida esperada en consola:

```text
======================================================================
FABRICA DE PROMPTS (CrewAI)
======================================================================

Solicitud: Necesito un prompt para analizar logs de errores en Python con FastAPI

Dominio detectado: Desarrollo de Software (python)

Ejecutando crew...
----------------------------------------------------------------------

----------------------------------------------------------------------
Proceso completado exitosamente

RESULTADO FINAL:
======================================================================
Actua como un ingeniero de confiabilidad y desarrollador senior especializado en Python y FastAPI.
Tu tarea es analizar los logs de errores adjuntos y diagnosticar la causa raiz de los incidentes reportados...
======================================================================

Tokens: 2450 total (1850 prompt + 600 completion, 4 llamadas)
```

### Ejecucion via HTTP con cURL (SSE Stream)

```bash
curl -N -X POST "http://127.0.0.1:8000/generar" \
     -H "Content-Type: application/json" \
     -d '{"solicitud": "Crear un prompt para auditoria de seguridad en APIs REST"}'
```

Salida del stream SSE:

```text
data: {"tipo": "progreso", "paso": 1, "total": 4, "agente": "Analista"}

data: {"tipo": "progreso", "paso": 2, "total": 4, "agente": "Especialista de dominio"}

data: {"tipo": "progreso", "paso": 3, "total": 4, "agente": "Arquitecto"}

data: {"tipo": "progreso", "paso": 4, "total": 4, "agente": "Mediador"}

data: {"tipo": "resultado", "dominio_nombre": "Ciberseguridad", "dominio_codigo": "seguridad", "vacio": false, "texto": "Actua como un auditor de seguridad senior...", "advertencia_formato": false, "uso": "Tokens: 2890 total..."}
```

### Ejecucion de Pruebas Automatizadas

```bash
.venv\Scripts\python.exe -m pytest tests/test_dominio.py tests/test_tools.py tests/test_web.py -v
```

---

## Errores / Excepciones

- **`ValueError` ("GEMINI_API_KEY environment variable not set")**:
  - Lanzado por: `build_llm()` en `fabrica_prompts/crew.py`.
  - Causa: Falta la variable de entorno `GEMINI_API_KEY` o se encuentra vacia.
  - Efecto: En CLI muestra instrucciones de configuracion. En Web emite evento SSE `{"tipo": "error", "mensaje": "Error de configuracion: ..."}`.
- **`HTTPException` (Codigo 400)**:
  - Lanzado por: Endpoint `POST /generar` en `fabrica_prompts/web.py`.
  - Causa: El cuerpo de la solicitud contiene una cadena `solicitud` con longitud menor a 3 caracteres tras eliminar espacios en blanco.
  - Respuesta: JSON `{"detail": "La solicitud debe tener al menos 3 caracteres."}` antes de iniciar la conexion de streaming.
- **`google.genai.errors.ClientError` / `google.genai.errors.ServerError` (Codigos HTTP 429, 500, 503)**:
  - Manejado por: `ejecutar_con_reintento()` en `fabrica_prompts/crew.py`.
  - Efecto: Aplica reintentos con backoff exponencial (1s a 60s) hasta un maximo de 5 intentos. Si se agotan los intentos, la excepcion se propaga.
- **`NETWORK_ERRORS` (`ConnectionError`, `TimeoutError`, `httpx.TimeoutException`)**:
  - Manejado por: `ejecutar_con_reintento()` en `fabrica_prompts/crew.py`.
  - Efecto: Aplica la misma politica de reintentos escalonados hasta 5 intentos ante fallas transitorias de red o tiempos de espera agotados.
- **`asyncio.CancelledError`**:
  - Manejado por: `_generar_stream()` en `fabrica_prompts/web.py`.
  - Causa: El cliente cierra la conexion HTTP o aborta la peticion desde el frontend mediante el boton "Cancelar".
  - Efecto: Se registra la desconexion en el log y se cancela la tarea asincrona.
