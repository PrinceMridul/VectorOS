# syntax=docker/dockerfile:1

FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencies resolve from pyproject alone, so this layer is cached across
# every source edit — the common case during development.
COPY pyproject.toml ./
RUN python -m pip install --upgrade pip \
    && python -m pip install "fastapi>=0.115" "uvicorn[standard]>=0.32" "pydantic>=2.9" \
       "pydantic-settings>=2.6" "sqlalchemy>=2.0.36" "greenlet>=3.1" "aiosqlite>=0.20" \
       "asyncpg>=0.30" "pgvector>=0.3.6" "httpx>=0.27" "python-jose[cryptography]>=3.3" \
       "langgraph>=0.2.50" "structlog>=24.4"

COPY app ./app

# Run unprivileged. The container writes nothing outside /app in the SQLite
# path, and nothing at all when pointed at Postgres.
RUN useradd --create-home --uid 10001 vectoros && chown -R vectoros:vectoros /app
USER vectoros

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status == 200 else 1)"

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
