# Bothost Runtime Contract

## Purpose

Keep the public AvitoBot web process reachable across Bothost deploys, host
restarts, and platform bind mounts while preserving production runtime state.

## Verified Hosting Constraint

Bothost can bind-mount the Git checkout over `/app` when a custom Docker image
starts. Image-layer application files, build artifacts, or virtual environments
stored below `/app` can therefore disappear at runtime. Compose-only settings
such as `restart` and `healthcheck` are not part of the hosted Dockerfile
contract.

## Required Image Layout

- Store immutable application code and its Python virtual environment below
  `/opt/avito-bot`, never below `/app`.
- Reserve `/app/data` for host-persistent SQLite state, backups, and other
  documented runtime data.
- Local Compose must mount the host `.codex-runtime` folder at
  `/app/data/avito-bot`, matching the image's storage resolution without moving
  or resetting existing project runtime files.
- Prefer managed PostgreSQL through `DATABASE_URL`; otherwise default
  `SHARED_DIR` to `/app/data` in the production image.
- Start Uvicorn through a small entrypoint that validates the injected
  `PORT`/`API_PORT` and uses `exec`, making the server process PID 1.
- Define the `/api/health` check in the Dockerfile itself. Compose may repeat
  the same check for local operation but cannot be its only owner.
- Create `/app/data/avito-bot/logs` before application startup. Persist rotating
  `runtime.log` and `events.jsonl` there while retaining stdout/stderr output for
  the Bothost runtime-log panel.
- Use a project-supported stable Python runtime. The hosted image currently
  uses Python 3.12, matching `requires-python >=3.12`.

## Verification

Before publishing a Docker runtime change:

1. Build the repository Dockerfile from a clean source context.
2. Run the image with the repository mounted over `/app` to reproduce the
   Bothost bind-mount constraint.
3. Verify `/api/health` and `/` return HTTP 200 on the injected `PORT`.
4. Verify container health becomes `healthy` and PID 1 is the Uvicorn Python
   process, not a shell or `uv run` dependency installer.
5. Confirm runtime SQLite/backups resolve below `/app/data/avito-bot` when
   `DATABASE_URL` is not configured.
6. After an authorized production deployment, verify the public health and UI
   endpoints and inspect runtime logs if either is unavailable.
