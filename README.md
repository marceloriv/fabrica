# Fábrica de Prompts

Este proyecto es un sistema de generación y optimización de prompts especializados utilizando una crew de agentes de Inteligencia Artificial coordinados con CrewAI.

---

## Instalación

CrewAI todavía no soporta Python 3.14, así que el proyecto usa un entorno virtual con Python 3.12:

```bash
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Estructura

```
fabrica_prompts/     # paquete: cli.py, web.py (entradas), crew.py (agentes/tasks), dominio.py, tools.py
tests/                # test_dominio.py, test_crew.py, test_web.py, test_tools.py
```

## Ejecución

CLI (una solicitud por vez, o interactivo si no pasás argumento):

```bash
.venv\Scripts\python.exe -m fabrica_prompts.cli "tu solicitud de prompt"
```

Interfaz web local (formulario simple en el navegador):

```bash
.venv\Scripts\python.exe -m uvicorn fabrica_prompts.web:app --reload
```

Abrí http://127.0.0.1:8000 en el navegador. Sin auth, pensada para uso local en tu máquina.

Tests:

```bash
.venv\Scripts\python.exe -m pytest -q
```

## Configuración de Variables de Entorno

Para ejecutar el proyecto, debes crear un archivo llamado `.env` en la raíz del proyecto y copiar los contenidos de [.env.example](file:///c:/Users/Marcelo-HP/Desktop/Codigo/Proyectos/fabrica/.env.example) para completarlos con tus credenciales.

### ¿Qué significa cada variable y de dónde se obtiene?

#### 1. `GEMINI_API_KEY`
* **Para qué sirve:** Es tu clave de acceso para que el programa pueda autenticarse con Google y consumir los modelos Gemini (sujeto a límites de uso gratuito).
* **De dónde se obtiene:**
  1. Ve a [Google AI Studio](https://aistudio.google.com/apikey).
  2. Inicia sesión con tu cuenta de Google.
  3. Haz clic en **Create API key**.
  4. Copia el token generado y pégalo aquí.

#### 2. `MODEL`
* **Para qué sirve:** Especifica el modelo de lenguaje que el sistema utilizará para procesar y optimizar los prompts.
* **De dónde se obtiene:** Puedes usar modelos disponibles de Gemini, como por ejemplo:
  * `gemini-3.5-flash-lite` (Recomendado: rápido y de bajo consumo de límite)
  * `gemini-2.0-flash`

#### 3. Variables de LangSmith (Opcionales)
* `LANGSMITH_TRACING`: Habilita (`"true"`) o deshabilita (`""`) el rastreo y monitoreo de tus agentes en LangSmith.
* `LANGSMITH_API_KEY`: Tu clave de API de LangSmith (se obtiene registrándote en [LangSmith](https://smith.langchain.com/)).
* `LANGSMITH_PROJECT`: Nombre del proyecto en tu panel de LangSmith para agrupar las trazas.
