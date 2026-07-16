from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_bothost_runtime_is_outside_app_bind_mount() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "WORKDIR /opt/avito-bot" in dockerfile
    assert "WORKDIR /app" not in dockerfile
    assert 'SHARED_DIR=/app/data' in dockerfile
    assert 'CMD ["avito-bot-entrypoint"]' in dockerfile


def test_docker_image_defines_healthcheck() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "HEALTHCHECK" in dockerfile
    assert "/api/health" in dockerfile


def test_compose_persists_state_at_the_image_data_path() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "./.codex-runtime:/app/data/avito-bot" in compose
    assert "/app/.codex-runtime" not in compose


def test_entrypoint_execs_the_immutable_python_runtime() -> None:
    entrypoint = (ROOT / "docker-entrypoint.sh").read_text(encoding="utf-8")

    assert 'log_dir="${AVITO_LOG_DIR:-${shared_dir%/}/avito-bot/logs}"' in entrypoint
    assert 'mkdir -p "$log_dir"' in entrypoint
    assert "exec /opt/avito-bot/.venv/bin/python -m app.server" in entrypoint
