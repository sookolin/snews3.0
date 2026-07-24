# API overview

Base path: `/api/v1`. Interactive docs at `/docs` (Swagger) and `/redoc`.

Auth: `Authorization: Bearer <access_token>`. Obtain tokens via `/auth/login`.

## Auth
| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/login` | Login (email, password, optional `totp_code`) → token pair |
| POST | `/auth/refresh` | Exchange refresh token for a new pair |
| GET  | `/auth/me` | Current user |
| POST | `/auth/2fa/setup` | Generate TOTP secret + provisioning URI |
| POST | `/auth/2fa/enable` | Verify code and enable 2FA |
| POST | `/auth/2fa/disable` | Disable 2FA |

## Resources (CRUD)
| Resource | Base | Permission |
|----------|------|-----------|
| Users | `/users` | `user:*` |
| Cities | `/cities` | `city:*` (auto-creates Telegram topic) |
| Sources | `/sources` | `source:*` (+ `POST /{id}/check`) |
| News | `/news` | `news:*` |
| Media | `/media` | `news:edit` (upload/reorder/spoiler) |
| Templates | `/templates` | `template:manage` (+ `/{id}/preview`) |
| Watermarks | `/watermarks` | `watermark:manage` (+ `/{id}/logo`) |
| AI profiles | `/ai` | `ai:manage` (+ `/test`, `/providers`) |
| Channels | `/channels` | `channel:manage` |
| Settings | `/settings` | `settings:manage` |

## News workflow
| Method | Path | Description |
|--------|------|-------------|
| GET | `/news` | List with filters: `status`, `city_id`, `source_id`, `origin`, `search` |
| PATCH | `/news/{id}` | Edit (snapshots a version) |
| GET | `/news/{id}/versions` | Version history |
| POST | `/news/{id}/versions/{v}/restore` | Roll back |
| POST | `/news/{id}/approve` | Approve (+ optional publish) |
| POST | `/news/{id}/reject` | Reject with reason |
| POST | `/news/{id}/publish` | Publish immediately |

## Dashboard / monitoring
| Method | Path | Description |
|--------|------|-------------|
| GET | `/dashboard/stats` | Counts + status breakdown + 7-day series |
| GET | `/dashboard/system` | Service health, CPU/mem, queue depth, workers |
| GET | `/settings/audit/logs` | Audit log browser |

## Error format
```json
{ "error": { "code": "not_found", "message": "News 5 not found" } }
```
