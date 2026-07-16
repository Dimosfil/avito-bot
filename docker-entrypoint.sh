#!/bin/sh
set -eu

host="${API_HOST:-0.0.0.0}"
port="${PORT:-${API_PORT:-8000}}"

case "$port" in
  ''|*[!0-9]*)
    echo "PORT or API_PORT must be a numeric TCP port" >&2
    exit 2
    ;;
esac

if [ "$port" -lt 1 ] || [ "$port" -gt 65535 ]; then
  echo "PORT or API_PORT must be between 1 and 65535" >&2
  exit 2
fi

exec /opt/avito-bot/.venv/bin/python -m uvicorn app.main:app \
  --host "$host" \
  --port "$port"
