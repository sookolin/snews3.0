# syntax=docker/dockerfile:1
# Frontend (Next.js 14) multi-stage build.
FROM node:20-alpine AS deps
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY frontend/ ./
ENV NEXT_TELEMETRY_DISABLED=1
# Server-side proxy target baked into the build (Docker service name).
ARG API_PROXY_TARGET=http://backend:8000
ENV API_PROXY_TARGET=${API_PROXY_TARGET}
# Public build-time envs (inlined into client bundle at BUILD time — changing
# them in .env requires a frontend rebuild, not just a restart).
ARG NEXT_PUBLIC_YANDEX_MAPS_KEY=
ENV NEXT_PUBLIC_YANDEX_MAPS_KEY=${NEXT_PUBLIC_YANDEX_MAPS_KEY}
ARG NEXT_PUBLIC_TELEGRAM_BOT_USERNAME=
ENV NEXT_PUBLIC_TELEGRAM_BOT_USERNAME=${NEXT_PUBLIC_TELEGRAM_BOT_USERNAME}
ARG NEXT_PUBLIC_TELEGRAM_CLIENT_ID=
ENV NEXT_PUBLIC_TELEGRAM_CLIENT_ID=${NEXT_PUBLIC_TELEGRAM_CLIENT_ID}
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1
RUN addgroup -g 1001 -S nodejs && adduser -S nextjs -u 1001

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000
ENV PORT=3000 HOSTNAME=0.0.0.0
CMD ["node", "server.js"]
