# Database schema & ER diagram

```mermaid
erDiagram
    USERS ||--o{ AUDIT_LOGS : performs
    USERS ||--o{ NEWS : moderates
    CITIES ||--o{ CHANNELS : has
    CITIES ||--o{ NEWS : categorizes
    CITIES }o--o{ SOURCES : feeds
    SOURCES ||--o{ NEWS : discovers
    TEMPLATES ||--o{ NEWS : formats
    TEMPLATES ||--o{ CHANNELS : formats
    AI_PROFILES ||--o{ NEWS : processes
    NEWS ||--o{ MEDIA_ASSETS : contains
    NEWS ||--o{ NEWS_VERSIONS : versioned_by

    USERS {
        int id PK
        string email UK
        string hashed_password
        enum role
        bool is_active
        bool is_2fa_enabled
        bigint telegram_id UK
    }
    CITIES {
        int id PK
        string name
        string slug UK
        string[] keywords
        string[] extra_keywords
        string[] exclude_keywords
        int telegram_topic_id
        bool is_active
    }
    SOURCES {
        int id PK
        string url
        enum type
        enum parser_engine
        int check_interval_seconds
        jsonb selectors
        jsonb headers
    }
    NEWS {
        int id PK
        text original_text
        text text
        enum status
        enum origin
        int city_id FK
        int source_id FK
        string content_hash
        bigint simhash
        float[] embedding
        float match_score
        bool is_spoiler
        timestamptz scheduled_at
    }
    MEDIA_ASSETS {
        int id PK
        int news_id FK
        enum type
        string file_path
        string processed_path
        int position
        bool is_spoiler
    }
    NEWS_VERSIONS {
        int id PK
        int news_id FK
        int version
        jsonb snapshot
    }
    CHANNELS {
        int id PK
        int city_id FK
        string chat_id
        int topic_id
        enum publish_mode
    }
    TEMPLATES {
        int id PK
        string name
        enum format
        text header
        text body
        text footer
    }
    AI_PROFILES {
        int id PK
        enum provider
        text system_prompt
        float temperature
    }
    WATERMARK_PROFILES {
        int id PK
        string logo_path
        string position
        float opacity
    }
    SETTINGS {
        string key PK
        jsonb value
        string category
    }
    AUDIT_LOGS {
        int id PK
        int user_id FK
        string action
        string entity_type
        jsonb changes
        string ip_address
    }
```

## Migrations

Managed by Alembic. The baseline is `alembic/versions/0001_initial.py`.

```bash
alembic upgrade head          # apply
alembic revision --autogenerate -m "message"   # create new
alembic downgrade -1          # roll back one
```
