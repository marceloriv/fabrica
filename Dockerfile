# syntax=docker/dockerfile:1

# CrewAI no soporta Python 3.14 (requires_python: <3.14,>=3.10 en PyPI) -> 3.12-slim fijo.

# ---- Builder: resuelve dependencias en un venv aislado ----
FROM python:3.12-slim AS builder

WORKDIR /app

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
# crewai/lxml publican wheels manylinux para cp312 amd64 -> sin build-essential.
# Si el build falla por falta de wheel en tu arch, agregar aquí:
#   apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ---- Runtime: solo el venv resuelto + código fuente, sin toolchain de build ----
FROM python:3.12-slim AS runtime

WORKDIR /app

# Usuario no-root: el servicio web no necesita privilegios.
RUN useradd --create-home --uid 1000 app

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8

# Solo el paquete de la app; tests/, .git, tooling quedan fuera vía .dockerignore.
COPY fabrica_prompts/ ./fabrica_prompts/

USER app

EXPOSE 8000

# GET / no requiere GEMINI_API_KEY (solo el POST construye la crew) -> healthcheck válido sin secretos.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/', timeout=3).status==200 else 1)"

# Modo web por defecto: el CLI interactivo (input()) no sirve sin TTY en un container.
# Para CLI puntual: docker compose run --rm fabrica-prompts python -m fabrica_prompts.cli "tu solicitud"
CMD ["python", "-m", "uvicorn", "fabrica_prompts.web:app", "--host", "0.0.0.0", "--port", "8000"]
