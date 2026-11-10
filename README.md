# SpeakFill — Speak. Confirm. Done.

Voice-first, multilingual form filling. Speak your answers in your own language, confirm
each field as it reads back, and get a filled, ready-to-submit PDF. Built for
**HackGlobal 2026**, Track 02 (Multimodal & accessibility).

## Demo

- **Live app:** run locally (see below) and open http://localhost:8080 — production URL is added on deploy day.
- **Demo video:** unlisted link added before submission.
- **Fastest tour:** open the app and press **60-second demo** — two fields come pre-filled, you answer the third by voice.

## The problem

Forms gate opportunity — scholarships, admissions, clinic intake, government services —
yet they assume the applicant reads dense instructions, writes in English, and never
slips on field 17 of 20. That locks out low-literacy and non-English speakers, blind
and low-vision users, elderly users, and international students. Translators and
chatbots translate *words*; nobody walks the user field-by-field to a finished,
correct document. SpeakFill does exactly that.

## Features

- **Voice interview loop** — each question asked aloud, answers understood, every value read back for yes/no confirmation (English + Hindi)
- **Photo pre-fill** — photograph a paper form; visible values pre-fill and get voice-confirmed one by one
- **Live form preview** — watch fields fill and confirm in real time
- **Full review + read-aloud** — hear the whole form before finishing; jump back to edit any field
- **Filled PDF export** — submission record with per-field source badges and a verify footer
- **Typed fallback everywhere** — every field works typed; mic-denied and STT-outage paths stay usable
- **One-tap feedback** — country + rating + comment after every completion

## How it works

```
Browser (Next.js) ──HTTPS──▶ API (FastAPI) ──▶ Postgres (sessions, answers, jobs)
        │                         ├──▶ smallest.ai Pulse ── speech → text
        │                         ├──▶ smallest.ai Lightning ── text → speech (cached)
        │                         ├──▶ LLM (OpenAI-compatible) ── value normalization, photo reading
        │                         └──▶ /data ── uploads, audio cache, PDFs
```

Each turn: record (≤30 s) → transcribe → normalize to the field's type → persist the
attempt → read back ("I heard X. Correct?") → confirm advances, reject re-asks
(max 3 attempts, then a typed nudge). Photo uploads run as async jobs and map to
schema keys; anything unmappable is quarantined, never forced into the form.

## Stack

| Layer | Choice |
|---|---|
| Frontend | Next.js 14 + Tailwind, mobile-first |
| Backend | FastAPI + SQLAlchemy 2 + Alembic |
| Database | Postgres 16 (+ JSONB) |
| Voice | smallest.ai Waves API (Pulse STT, Lightning TTS) |
| Language/vision | OpenAI-compatible LLM behind a thin adapter (offline stub included) |
| PDF | WeasyPrint (Jinja HTML template) |
| Hosting | Single VPS, Docker Compose (Caddy + web + api + db, auto-TLS) |

## API reference

| Method | Path | Purpose |
|---|---|---|
| GET | /api/healthz | Liveness |
| GET | /api/templates | List form templates |
| GET | /api/templates/{id} | Template schema (fields, prompts, options) |
| POST | /api/sessions | Start interview `{template_id, language}` |
| GET | /api/sessions/{id} | Full state (resume any time) |
| POST | /api/sessions/{id}/answer | JSON `{text}` or multipart `audio` |
| POST | /api/sessions/{id}/confirm | JSON `{accepted}` or multipart `audio` |
| POST | /api/sessions/{id}/goto | Jump to field `{ord}` (review edits) |
| POST | /api/sessions/{id}/restart | Start the interview over |
| POST | /api/sessions/{id}/photo | Paper-form photo → `{job_id}` (202) |
| GET | /api/jobs/{id} | Poll photo extraction |
| GET | /api/audio/prompt/{tpl}/{ord}?language= | Spoken question audio |
| GET | /api/audio/{hash}.wav | Cached prompt audio |
| GET | /api/sessions/{id}/review | Ordered rows + read-back script + block state |
| POST | /api/sessions/{id}/export | Create submission (idempotent) |
| GET | /api/submissions/{id}.pdf | Download filled PDF |
| POST | /api/feedback | `{session_id, country, rating, comment?}` |
| GET | /api/stats | Traction counters (sessions, feedback by country, rating) |

## Project structure

```
speakfill/
├── docker-compose.yml      # caddy + web + api + db
├── apps/web/               # Next.js app (interview, review, completion screens)
├── apps/api/               # FastAPI app (routes, services, models, tests)
├── infra/caddy/            # local + production Caddy profiles
├── infra/deploy.sh         # production deploy (pull → build → pregen → smoke)
├── scripts/smoke.py        # post-deploy smoke test
└── README.md
```

## Getting started

```bash
cp .env.example .env        # add SMALLEST_API_KEY for real voice (optional for a look-around)
docker compose up --build -d
open http://localhost:8080
```

That's it: the API migrates and seeds itself, and the interview works end-to-end
(voice features need the key; everything else runs offline).

## Configuration

All keys live in `.env` (see `.env.example`, never committed): `APP_BASE_URL`,
`DATABASE_URL`, `SMALLEST_API_KEY`, `VOICE_PROVIDER`, `LLM_PROVIDER`,
`LLM_API_KEY`, `LLM_MODEL`, `LLM_BASE_URL`, plus server-only `DOMAIN`/`CADDYFILE`
for production. Provider values of `stub` select the offline doubles used by tests.

## Testing

```bash
docker compose exec api python -m pytest tests/ -q   # 33 service/route tests
docker compose exec api python -m scripts.run_evals   # 10-case normalization eval set
python3 scripts/smoke.py http://localhost:8080        # live end-to-end smoke
```

Eval evidence lives in `apps/api/tests/eval_logs/`.

## Production

One VPS + free subdomain + `./infra/deploy.sh`. Target: one VPS (Ubuntu 24.04,
2 GB RAM) with automatic TLS. Server setup (run once on the VPS):

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
# .env must set: DOMAIN=<your>.duckdns.org, CADDYFILE=Caddyfile.prod,
# APP_BASE_URL=https://<your>.duckdns.org, SMALLEST_API_KEY=<key>

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

## License

MIT — see [LICENSE](./LICENSE).
