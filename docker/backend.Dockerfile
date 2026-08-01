# syntax=docker/dockerfile:1
# Backend / workers / bot image (shares the same Python codebase).
FROM python:3.13-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System deps: ffmpeg (watermark video), postgres client (backups), fonts, build tools.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        postgresql-client \
        libpq-dev \
        gcc \
        curl \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the full source tree first. The editable install (`pip install -e .`)
# needs every package declared in pyproject.toml (shared, backend, workers,
# telegram_bot) to exist, so all of them must be present before installing.
COPY pyproject.toml README.md ./
COPY shared ./shared
COPY backend ./backend
COPY workers ./workers
COPY telegram_bot ./telegram_bot
COPY scripts ./scripts
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini

RUN pip install --upgrade pip && pip install -e .

# Playwright browser (for JS-heavy website parsing). Installed to a shared path
# so the non-root runtime user can find it.
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN mkdir -p /ms-playwright \
    && python -m playwright install --with-deps chromium \
    && chmod -R a+rx /ms-playwright

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

RUN useradd -m -u 1000 appuser && mkdir -p /data/media /data/backups \
    && chown -R appuser:appuser /app /data /ms-playwright
USER appuser

EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
CMD ["api"]
