# Architecture

CityNews is a monorepo organised around a single installable Python package,
`shared`, which contains the domain model, infrastructure and business
services. Three thin service layers consume it.

## Components

| Component | Tech | Responsibility |
|-----------|------|----------------|
| `backend/` | FastAPI | REST API + Swagger, auth, CRUD, moderation, publishing triggers |
| `telegram_bot/` | aiogram 3 | Moderation buttons + user news submissions |
| `workers/` | Celery + Beat | Source polling, ingestion pipeline, publishing, scheduling, backups |
| `frontend/` | Next.js 14 | Admin panel (all configuration lives here) |
| `shared/` | — | config, db, redis, models, schemas, services, plugins |

## Data flow

```
Source (RSS/Telegram/Website/API/HTML)
        │  parser plugin (fetch)
        ▼
IngestionPipeline
  ├─ CityMatcher      (keywords + morphology + exclusions)
  ├─ DedupService     (hash + simhash + Levenshtein + embeddings)
  ├─ persist News (PROCESSING)
  ├─ MediaService     (download attachments)
  └─ AIService        (rewrite via provider plugin) → PENDING
        │
        ▼
TelegramAdminService.send_moderation_card  → moderation group (inline buttons)
        │  Approve
        ▼
PublisherService
  ├─ resolve Template  → TemplateRenderer
  ├─ WatermarkService  (images: Pillow, video: FFmpeg)
  └─ publisher plugin  → Telegram channel(s) → PUBLISHED
```

## Plugin system

Three registries in `shared/plugins` implement the Open/Closed principle:

- **parsers** — keyed by `SourceType` (`rss`, `telegram`, `website`, `html`, `api`)
- **ai** — keyed by `AIProviderType` (`anthropic`, `openai`, `gemini`, `local`)
- **publishers** — keyed by name (`telegram`, extendable)

Add a new implementation by subclassing the base class and decorating it with
`@registry.register("key")`. No existing code changes.

## Configuration split

- **Secrets** (API keys, tokens, DB creds) → `.env` only.
- **Business parameters** (prompts, templates, watermark, dedup thresholds,
  feature toggles, i18n overrides) → `settings` table, editable from the web
  panel with no redeploy.

## Scaling

- Workers scale horizontally (`docker compose up -d --scale worker=N`).
- Backend and bot are stateless (JWT + Redis FSM) and can run multiple replicas
  behind nginx.
- Redis is the Celery broker + rate-limit + bot FSM store.
