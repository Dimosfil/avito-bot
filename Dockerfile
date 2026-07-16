FROM python:3.12-slim AS builder

ENV UV_LINK_MODE=copy

WORKDIR /opt/avito-bot

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project \
    && test -x /opt/avito-bot/.venv/bin/python


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/avito-bot/.venv/bin:${PATH}" \
    SHARED_DIR=/app/data

WORKDIR /opt/avito-bot

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/avito-bot/.venv ./.venv
COPY app ./app
COPY docker-entrypoint.sh /usr/local/bin/avito-bot-entrypoint

RUN chmod +x /usr/local/bin/avito-bot-entrypoint \
    && mkdir -p /app/data /opt/avito-bot/.codex-runtime

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import json, os, urllib.request; port=os.getenv('PORT') or os.getenv('API_PORT') or '8000'; response=urllib.request.urlopen(f'http://127.0.0.1:{port}/api/health', timeout=3); raise SystemExit(0 if json.load(response).get('status') == 'ok' else 1)"

CMD ["avito-bot-entrypoint"]
