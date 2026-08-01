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

# --- Dependency layer (rarely changes) -------------------------------------
# Install Python deps and the Playwright browser BEFORE copying the frequently
# edited application code. This keeps the expensive (and network-flaky)
# chromium download cached across ordinary code changes, so editing files under
# shared/ no longer forces a full re-download on rebuild.
COPY pyproject.toml README.md ./
# Minimal source needed for the editable install to resolve its metadata.
COPY shared ./shared
RUN pip install --upgrade pip && pip install -e .

# Playwright browser (for JS-heavy website parsing). Installed to a shared path
# so the non-root runtime user can find it.
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN mkdir -p /ms-playwright \
    && python -m playwright install --with-deps chromium \
    && chmod -R a+rx /ms-playwright

# --- Application code layer (changes often) --------------------------------
# Re-copy shared/ (so edits land) plus the rest of the app. These COPYs are
# cheap and do not invalidate the dependency/browser layers above.
COPY shared ./shared
COPY backend ./backend
COPY workers ./workers
COPY telegram_bot ./telegram_bot
COPY scripts ./scripts
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

RUN useradd -m -u 1000 appuser && mkdir -p /data/media /data/backups \
    && chown -R appuser:appuser /app /data /ms-playwright
USER appuser

EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
CMD ["api"]
