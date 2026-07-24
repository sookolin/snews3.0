#!/usr/bin/env bash
# Entrypoint dispatching to the correct process based on the first argument.
set -euo pipefail

ROLE="${1:-api}"

wait_for_db() {
    echo "Waiting for PostgreSQL at ${POSTGRES_HOST}:${POSTGRES_PORT}..."
    until pg_isready -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" >/dev/null 2>&1; do
        sleep 1
    done
    echo "PostgreSQL is ready."
}

case "$ROLE" in
    api)
        wait_for_db
        alembic upgrade head
        python -m scripts.seed || true
        exec uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --proxy-headers
        ;;
    worker)
        wait_for_db
        exec celery -A workers.celery_app worker -l info --concurrency="${CELERY_CONCURRENCY:-4}"
        ;;
    beat)
        wait_for_db
        exec celery -A workers.celery_app beat -l info
        ;;
    flower)
        exec celery -A workers.celery_app flower --port=5555
        ;;
    bot)
        wait_for_db
        exec python -m telegram_bot.main
        ;;
    migrate)
        wait_for_db
        exec alembic upgrade head
        ;;
    *)
        exec "$@"
        ;;
esac
