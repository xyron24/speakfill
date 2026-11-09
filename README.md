# SpeakFill — Speak. Confirm. Done.

Voice-first, multilingual form-filling assistant. Built for **HackGlobal 2026**, Track 02 (Multimodal & accessibility).

## Quickstart

```bash
cp .env.example .env   # optional (compose has sane defaults)
docker compose up --build
```

- App (via Caddy): <http://localhost:8080/>
- Health page: <http://localhost:8080/health> (browser → Caddy → API)
- API: reachable through Caddy at `http://localhost:8080/api/healthz`,
  or directly via `docker compose exec api ...`

Stop and wipe volumes: `docker compose down -v`

> Note: only Caddy's ports (8080/8443) are published. The API, web, and
> database services stay on the internal compose network.

## Layout

```
speakfill/
├── docker-compose.yml      # caddy + web + api + db (local profile)
├── .env.example            # all config keys (never commit .env)
├── apps/
│   ├── web/                # Next.js frontend (port 3000, internal)
│   └── api/                # FastAPI backend (port 8000, internal)
├── infra/
│   ├── caddy/Caddyfile     # :80 → / to web, /api/* to api
│   └── deploy.sh           # production deploy entrypoint
└── README.md
```
