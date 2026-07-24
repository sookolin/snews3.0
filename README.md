# CityNews — News Monitoring & Publishing Platform

Production-ready service that monitors many news sources, detects city-relevant
news, deduplicates, rewrites them with AI, moderates them through Telegram, and
publishes to Telegram channels/topics. All configuration lives in the Web panel.

## Architecture

The project is a **monorepo** built around a single installable Python package
`shared` that contains the domain model, infrastructure and business services.
Three thin service layers consume it:

```
┌──────────────┐   ┌───────────────┐   ┌───────────────┐
│  backend/    │   │ telegram_bot/ │   │   workers/    │
│  (FastAPI)   │   │  (aiogram 3)  │   │  (Celery)     │
└──────┬───────┘   └───────┬───────┘   └───────┬───────┘
       │                   │                   │
       └───────────────────┼───────────────────┘
                           ▼
                   ┌────────────────┐
                   │    shared/     │  config · db · redis · models ·
                   │  (core domain) │  schemas · services · plugins
                   └───────┬────────┘
                           ▼
        PostgreSQL  ·  Redis  ·  Object storage (media)
```

Design principles: **Clean Architecture, SOLID, DRY, KISS**. Everything
pluggable (parsers, AI providers, publishers) via a registry so new
implementations are added without touching existing code.

### Directory layout

```
snews3.0/
├── shared/                 # Installable core package (imported by every service)
│   ├── config.py           # Pydantic settings (.env)
│   ├── database.py         # Async SQLAlchemy 2.0 engine/session
│   ├── redis_client.py     # Redis connection helper
│   ├── logging.py          # Structured logging
│   ├── i18n.py             # Multi-language message catalog
│   ├── security.py         # JWT, bcrypt, permissions
│   ├── exceptions.py       # Domain exceptions
│   ├── enums.py            # Shared enums
│   ├── models/             # SQLAlchemy ORM models
│   ├── schemas/            # Pydantic v2 schemas
│   ├── repositories/       # Data-access layer
│   ├── services/           # Business services (dedup, matcher, publisher…)
│   └── plugins/            # Registry + parsers/ai/publishers plugins
├── backend/                # FastAPI application (REST API + Swagger)
│   └── app/
│       ├── main.py
│       ├── deps.py
│       └── api/            # Routers per domain
├── telegram_bot/           # aiogram 3.x bot (moderation + user submissions)
├── workers/                # Celery tasks + beat schedule
├── frontend/               # Next.js 14 + Tailwind + shadcn/ui admin panel
├── docker/                 # Dockerfiles + nginx config
├── scripts/                # deploy.sh, backup, seed
├── docs/                   # Extended docs + ER diagram
├── alembic/                # DB migrations
├── docker-compose.yml
├── pyproject.toml
└── .env.example
```

## Quick start (local, one command)

```bash
cp .env.example .env          # fill in secrets (bot token, AI key, etc.)
docker compose up -d --build
```

Services:
- API + Swagger: http://localhost:8000/docs
- Frontend admin: http://localhost:3000
- Flower (Celery monitor): http://localhost:5555

Create the first super admin (after containers are up):

```bash
docker compose exec backend python -m scripts.seed
```

## Local dev without Docker

```bash
python -m venv .venv && . .venv/Scripts/activate   # Windows
pip install -e ".[dev]"
alembic upgrade head
uvicorn backend.app.main:app --reload
celery -A workers.celery_app worker -l info -P solo
celery -A workers.celery_app beat -l info
python -m telegram_bot.main
```

## Deployment

`scripts/deploy.sh` pulls from GitHub on the VPS, rebuilds containers, runs
migrations and reloads nginx. CI/CD in `.github/workflows/ci.yml` runs lint +
type-check + tests and can trigger the deploy over SSH.

See `docs/` for the full ER diagram, API overview and operations runbook.
