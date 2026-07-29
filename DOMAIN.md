# Запуск на домене (локальный сервер → публичный URL)

## Что нужно подставить

| Файл | Переменная / строка | Подставить |
|------|---------------------|------------|
| `.env` | `BACKEND_CORS_ORIGINS` | `https://snews.example.com` |
| `.env` | `ADMIN_PANEL_URL` | `https://snews.example.com` |
| `.env` | `TELEGRAM_WEBHOOK_URL` | `https://snews.example.com/api/v1/bot/webhook` |
| `.env` | `APP_ENV` | `production` |
| `.env` | `DEBUG` | `false` |
| `docker/nginx/nginx.conf` | `server_name` (HTTPS-блок) | ваш домен, например `snews.example.com` |
| `docker/nginx/nginx.conf` | `ssl_certificate` | `/etc/letsencrypt/live/snews.example.com/fullchain.pem` |
| `docker/nginx/nginx.conf` | `ssl_certificate_key` | `/etc/letsencrypt/live/snews.example.com/privkey.pem` |
| `docker-compose.yml` (frontend `args` / `environment`) | `NEXT_PUBLIC_API_URL` | `https://snews.example.com` |

---

## Шаг 1. Направьте домен на сервер

В панели вашего DNS-провайдера добавьте A-запись:

```
snews.example.com  →  <публичный IP вашего сервера>
```

Проверка (после TTL, обычно 5–15 мин):
```bash
nslookup snews.example.com
```

---

## Шаг 2. Откройте порты

Убедитесь, что firewall (iptables / ufw / облачный Security Group) пропускает:

| Порт | Протокол | Назначение |
|------|----------|------------|
| 80   | TCP | HTTP → редирект на HTTPS + certbot challenge |
| 443  | TCP | HTTPS |

```bash
# ufw (Ubuntu / Debian)
ufw allow 80/tcp
ufw allow 443/tcp
ufw reload
```

---

## Шаг 3. Выпустите TLS-сертификат (Let's Encrypt)

Certbot запускается отдельным разовым контейнером, nginx уже настроен
пропускать `.well-known/acme-challenge/` через volume `certbot/www`.

```bash
docker run --rm \
  -v ./docker/nginx/certbot/conf:/etc/letsencrypt \
  -v ./docker/nginx/certbot/www:/var/www/certbot \
  certbot/certbot certonly --webroot \
  --webroot-path /var/www/certbot \
  -d snews.example.com \
  --email admin@example.com \
  --agree-tos --non-interactive
```

После успеха сертификат будет в `docker/nginx/certbot/conf/live/snews.example.com/`.

---

## Шаг 4. Включите HTTPS в nginx

Раскомментируйте HTTPS-блок в `docker/nginx/nginx.conf`
(файл уже содержит шаблон, нужно только подставить домен).
Пример готового файла:

```nginx
server {
    listen 80;
    server_name snews.example.com;
    # certbot webroot challenge
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }
    # redirect everything else to HTTPS
    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl http2;
    server_name snews.example.com;

    ssl_certificate     /etc/letsencrypt/live/snews.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/snews.example.com/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;

    client_max_body_size 60M;

    location /api/   { proxy_pass http://backend; include /etc/nginx/proxy_params.conf; }
    location /docs   { proxy_pass http://backend; include /etc/nginx/proxy_params.conf; }
    location /health { proxy_pass http://backend; include /etc/nginx/proxy_params.conf; }
    location /media/ { alias /data/media/; expires 7d; add_header Cache-Control "public"; }
    location /       { proxy_pass http://frontend; include /etc/nginx/proxy_params.conf; }
}
```

Перезагрузите nginx:
```bash
docker compose exec nginx nginx -s reload
```

---

## Шаг 5. Обновите `.env` и пересоберите

```bash
# .env — ключевые строки
APP_ENV=production
DEBUG=false
SECRET_KEY=<случайная строка 32+ символов>
BACKEND_CORS_ORIGINS=https://snews.example.com
ADMIN_PANEL_URL=https://snews.example.com
TELEGRAM_WEBHOOK_URL=https://snews.example.com/api/v1/bot/webhook
```

После изменения `.env` нужно пересобрать только frontend
(NEXT_PUBLIC_* встраиваются на этапе сборки):

```bash
docker compose build frontend
docker compose up -d
```

---

## Шаг 6. Telegram Webhook

Если бот сейчас работает в режиме long polling, переведите его на webhook:

```bash
# Зарегистрировать webhook
curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://snews.example.com/api/v1/bot/webhook"
# Проверить
curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
```

Webhook начнёт работать сразу после перезапуска бота (`docker compose restart bot`).

---

## Шаг 7. Автообновление сертификата

Добавьте в cron сервера (не в контейнер):

```cron
0 3 * * * cd /путь/к/snews3.0 && docker run --rm \
  -v ./docker/nginx/certbot/conf:/etc/letsencrypt \
  -v ./docker/nginx/certbot/www:/var/www/certbot \
  certbot/certbot renew --quiet \
  && docker compose exec nginx nginx -s reload
```

---

## Ответ на вопрос о медиавложениях

**Сохраняются ли файлы локально?**

| Этап | Файлы | Где |
|------|-------|-----|
| Скачивание из источника | Исходный файл | `MEDIA_ROOT/news/{news_id}/` |
| Обработка (watermark, ресайз) | Обработанная копия | `MEDIA_ROOT/news/{news_id}/` рядом |
| Публикация в Telegram | Файлы **остаются** на диске | Telegram хранит своя копию, наша никуда не уходит |
| После отклонения (REJECTED/FAILED) | Удаляются задачей `cleanup_temp_media` | через 30 дней (`--days 30`) |

**Итого**: файлы живут в `./data/media/news/` (docker volume `media_data`).
После публикации они **не удаляются** автоматически — остаются для повторного
использования и истории. Удаляются только вложения отклонённых/упавших новостей
(через 30 дней задачей Beat).

Чтобы освободить место, можно вручную запустить:
```bash
docker exec citynews-backend-1 python -m scripts.cleanup_news --keep-telegram --yes
# или целевую очистку только старых rejected:
docker exec citynews-backend-1 python -c "
from workers.celery_app import run_async
from workers.tasks import cleanup_temp_media
cleanup_temp_media(days=7)
"
```
