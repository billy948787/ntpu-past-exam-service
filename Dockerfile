FROM python:3.12-slim AS builder

RUN pip install poetry==2.1.3

WORKDIR /build

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache


COPY pyproject.toml poetry.lock ./

RUN poetry install --without dev --no-root

FROM python:3.12-slim AS runtime

ENV VIRTUAL_ENV=/.venv \
    PATH="/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN groupadd --system app \
    && useradd --system --gid app --home-dir /app --no-create-home app

COPY --from=builder /build/.venv ${VIRTUAL_ENV}

COPY --chown=app:app . .

USER app

EXPOSE 8080

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/ping', timeout=3)"]

CMD ["sh", "scripts/start-production.sh"]
