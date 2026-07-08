FROM python:3.14-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_LINK_MODE=copy
ENV PATH="/app/.venv/bin:${PATH}"

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
RUN test -x /app/.venv/bin/uvicorn

COPY app ./app

RUN mkdir -p /app/.codex-runtime

EXPOSE 8000

CMD ["sh", "-c", "/app/.venv/bin/uvicorn app.main:app --host ${API_HOST:-0.0.0.0} --port ${PORT:-${API_PORT:-8000}}"]
