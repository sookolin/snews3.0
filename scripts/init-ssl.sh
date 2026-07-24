#!/usr/bin/env bash
#
# init-ssl.sh — obtain Let's Encrypt certificates via certbot (webroot) and
# enable the HTTPS server block in nginx.
#
# Usage: DOMAIN=news.example.com EMAIL=admin@example.com ./scripts/init-ssl.sh
#
set -euo pipefail

DOMAIN="${DOMAIN:?Set DOMAIN=your-domain.com}"
EMAIL="${EMAIL:?Set EMAIL=you@example.com}"
CONF_DIR="docker/nginx/certbot/conf"
WWW_DIR="docker/nginx/certbot/www"

mkdir -p "$CONF_DIR" "$WWW_DIR"

echo "[ssl] Requesting certificate for $DOMAIN ..."
docker run --rm \
    -v "$(pwd)/$CONF_DIR:/etc/letsencrypt" \
    -v "$(pwd)/$WWW_DIR:/var/www/certbot" \
    certbot/certbot certonly --webroot -w /var/www/certbot \
    --email "$EMAIL" --agree-tos --no-eff-email \
    -d "$DOMAIN"

echo "[ssl] Certificate obtained. Uncomment the HTTPS server block in"
echo "      docker/nginx/nginx.conf, set server_name to $DOMAIN, then run:"
echo "      docker compose restart nginx"
echo
echo "[ssl] Set up auto-renewal with a cron entry, e.g.:"
echo "      0 3 * * * cd $(pwd) && docker run --rm -v \$(pwd)/$CONF_DIR:/etc/letsencrypt -v \$(pwd)/$WWW_DIR:/var/www/certbot certbot/certbot renew --quiet && docker compose restart nginx"
