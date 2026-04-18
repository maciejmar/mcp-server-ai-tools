FROM repo.bank.com.pl/python:3.11-slim AS builder

ENV POETRY_VERSION=1.8.3 \
    POETRY_HOME=/opt/poetry \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1

# Instalacja Poetry z wewnętrznego PyPI mirror
RUN pip install --no-cache-dir \
    --index-url https://repo.bank.com.pl/artifactory/api/pypi/pypi-remote/simple \
    --trusted-host repo.bank.com.pl \
    "poetry==$POETRY_VERSION"

WORKDIR /app
COPY pyproject.toml poetry.lock* ./

RUN poetry install --only main --no-root --no-cache

# --- Runtime image ---
FROM repo.bank.com.pl/python:3.11-slim

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY src/ ./src/
COPY .env.example .env

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()" || exit 1

CMD ["python", "-m", "src.server"]
