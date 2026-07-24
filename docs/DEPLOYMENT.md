# Deployment guide

## Local (one command)

```bash
cp .env.example .env    # fill in TELEGRAM_BOT_TOKEN, AI keys, etc.
docker compose up -d --build
docker compose exec backend python -m scripts.seed
```

- API + Swagger: http://localhost:8000/docs
- Admin panel: http://localhost:3000 (login with FIRST_SUPERADMIN_*)
- Flower: http://localhost:5555

## VPS (Ubuntu) first-time setup

```bash
# 1. Install Docker + compose plugin
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER" && newgrp docker

# 2. Clone and configure
git clone https://github.com/<you>/citynews.git /opt/citynews
cd /opt/citynews
cp .env.example .env && nano .env      # set secrets + APP_ENV=production

# 3. First deploy
./scripts/deploy.sh

# 4. HTTPS (optional)
DOMAIN=news.example.com EMAIL=admin@example.com ./scripts/init-ssl.sh
# then uncomment the 443 block in docker/nginx/nginx.conf and:
docker compose restart nginx
```

## Continuous deployment

`.github/workflows/ci.yml` lints, type-checks, tests, builds the frontend and,
on push to `main`, SSHes into the VPS and runs `scripts/deploy.sh`.

Required GitHub secrets: `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`, `VPS_APP_DIR`.

## systemd (alternative to compose restart policies)

`docker compose` already restarts containers with `restart: unless-stopped`.
To manage the whole stack as a unit, create `/etc/systemd/system/citynews.service`:

```ini
[Unit]
Description=CityNews stack
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/citynews
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now citynews
```

## Scaling workers

```bash
docker compose up -d --scale worker=4
```

## Backups

Nightly DB + media backups run via Celery Beat (`run_backup`) at
`BACKUP_CRON_HOUR`. Archives are written to `BACKUP_ROOT` (mounted volume).
Restore with `workers.backup.restore_backup(path)`.
