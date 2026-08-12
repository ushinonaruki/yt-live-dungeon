FROM python:3.12-slim AS base

RUN pip install --no-cache-dir uv==0.8.13

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN groupadd --system app && \
    useradd --system --gid app --create-home --home-dir /home/app app

FROM base AS source

COPY pyproject.toml uv.lock alembic.ini ./
COPY src ./src

FROM source AS production

RUN uv sync --frozen --no-group dev --no-editable && \
    chown -R app:app /app

ENV PATH="/app/.venv/bin:$PATH"

USER app
EXPOSE 8000
CMD ["uvicorn", "yt_live_dungeon.app:app", "--host", "0.0.0.0", "--port", "8000"]

FROM source AS dev

COPY tests ./tests

RUN uv sync --frozen --no-editable && \
    chown -R app:app /app

ENV PATH="/app/.venv/bin:$PATH"

USER app
EXPOSE 8000
CMD ["uvicorn", "yt_live_dungeon.app:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
