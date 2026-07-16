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

shared_dir="${SHARED_DIR:-/app/data}"
log_dir="${AVITO_LOG_DIR:-${shared_dir%/}/avito-bot/logs}"

case "$log_dir" in
  /*) ;;
  *)
    echo "AVITO_LOG_DIR must be an absolute path" >&2
    exit 2
    ;;
esac

mkdir -p "$log_dir"
export API_HOST="$host" PORT="$port" AVITO_LOG_DIR="$log_dir"

exec /opt/avito-bot/.venv/bin/python -m app.server
