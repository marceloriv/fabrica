# Fábrica de Prompts

Este proyecto es un sistema de generación y optimización de prompts especializados utilizando agentes de Inteligencia Artificial coordinados con LangChain.

---

## Configuración de Variables de Entorno

Para ejecutar el proyecto, debes crear un archivo llamado `.env` en la raíz del proyecto y copiar los contenidos de [.env.example](file:///c:/Users/Marcelo-HP/Desktop/Codigo/Proyectos/fabrica/.env.example) para completarlos con tus credenciales.

### ¿Qué significa cada variable y de dónde se obtiene?

#### 1. `OPENAI_BASE_URL`
* **Para qué sirve:** Define la dirección del servidor (API) al que se le enviarán las solicitudes de inteligencia artificial. En este caso, se utiliza para conectarse al catálogo de modelos de GitHub (GitHub Models).
* **De dónde se obtiene:** Deja el valor predeterminado `"https://models.github.io/inference"` o `"https://models.github.ai/inference"`.

#### 2. `GITHUB_TOKEN`
* **Para qué sirve:** Es tu clave de acceso (contraseña) para que el programa pueda autenticarse con GitHub y consumir los modelos de inteligencia artificial de forma gratuita (sujeto a límites de uso).
* **De dónde se obtiene:**
  1. Ve a tu cuenta de GitHub.
  2. Haz clic en tu foto de perfil (esquina superior derecha) -> **Settings** (Configuración).
  3. En el menú de la izquierda, baja hasta el final y haz clic en **Developer settings** (Configuración de desarrollador).
  4. Selecciona **Personal access tokens** -> **Tokens (classic)**.
  5. Haz clic en **Generate new token** -> **Generate new token (classic)**.
  6. Escribe una nota descriptiva (ej. `Fabrica de Prompts`).
  7. **No necesitas marcar ningún permiso (scopes) específico** para usar GitHub Models, pero asegúrate de que el token sea creado.
  8. Copia el token generado (empieza por `github_pat_...`) y pégalo aquí.

#### 3. `MODEL`
* **Para qué sirve:** Especifica el modelo de lenguaje que el sistema utilizará para procesar y optimizar los prompts.
* **De dónde se obtiene:** Puedes usar modelos disponibles en GitHub Models, como por ejemplo:
  * `gpt-4o-mini` (Recomendado: rápido y de bajo consumo de límite)
  * `gpt-4o`

#### 4. Variables de LangSmith (Opcionales)
* `LANGSMITH_TRACING`: Habilita (`"true"`) o deshabilita (`""`) el rastreo y monitoreo de tus agentes en LangSmith.
* `LANGSMITH_API_KEY`: Tu clave de API de LangSmith (se obtiene registrándote en [LangSmith](https://smith.langchain.com/)).
* `LANGSMITH_PROJECT`: Nombre del proyecto en tu panel de LangSmith para agrupar las trazas.
