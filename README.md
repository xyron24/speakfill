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
├── docker-compose.yml      # caddy + web + api + db (Caddyfile or Caddyfile.prod)
├── .env.example            # all config keys (never commit .env)
├── apps/
│   ├── web/                # Next.js frontend (port 3000, internal)
│   └── api/                # FastAPI backend (port 8000, internal)
├── infra/
│   ├── caddy/Caddyfile     # local: :80 → / to web, /api/* to api
│   ├── caddy/Caddyfile.prod# prod: {$DOMAIN} + auto-TLS + security headers
│   └── deploy.sh           # production deploy (pull → build → pregen → smoke)
├── scripts/
│   └── smoke.py            # post-deploy smoke test (runs anywhere)
└── README.md
```

## Production

Target: one Vultr VPS (Ubuntu 24.04, 2 GB RAM), `https://<you>.duckdns.org`
(free subdomain) with automatic TLS. Claim the hackathon Vultr credits from the
event Discord before provisioning.

Server setup (run once on the VPS):

```bash
# 1. base: user, firewall, docker
sudo apt-get update && sudo apt-get install -y git ufw
sudo ufw allow 22 && sudo ufw allow 80 && sudo ufw allow 443 && sudo ufw --force enable
curl -fsSL https://get.docker.com | sh && sudo usermod -aG docker $USER
# log out + back in so the docker group applies

# 2. code
sudo mkdir -p /opt/speakfill && sudo chown $USER:$USER /opt/speakfill
git clone https://github.com/xyron24/speakfill /opt/speakfill
cd /opt/speakfill

# 3. config (fill values; never commit this file)
cp .env.example .env
# .env must set: DOMAIN=<you>.duckdns.org, CADDYFILE=Caddyfile.prod,
# APP_BASE_URL=https://<you>.duckdns.org, SMALLEST_API_KEY=<key>

# 4. point DNS at the VPS, then deploy
./infra/deploy.sh
```

Redeploys are the same last command. Useful ops commands:

```bash
docker compose logs -f api        # api logs (use web/caddy/db for others)
docker compose ps                 # service status
docker compose restart api        # restart one service
tar -czf speakfill-data-$(date +%F).tgz -C /var/lib/docker/volumes \
  speakfill_pgdata speakfill_appdata   # backup database + uploads/audio/pdfs
```

Watch the smallest.ai usage dashboard during busy periods; static prompts are
pre-generated once and served from cache, so repeat traffic costs nothing.
Redeploying never re-synthesizes cached audio.
```
