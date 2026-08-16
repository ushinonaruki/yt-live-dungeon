FROM python:3.12-slim AS base

RUN pip install --no-cache-dir uv==0.8.13

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN groupadd --system app && \
    useradd --system --gid app --create-home --home-dir /home/app app

COPY pyproject.toml uv.lock alembic.ini ./
COPY src ./src
COPY tests ./tests

RUN uv sync --frozen --no-editable && \
    chown -R app:app /app

USER app
CMD ["sh", "-c", "exec uvicorn yt_live_dungeon.app:app --host 0.0.0.0 --port ${API_PORT_CONTAINER}"]
