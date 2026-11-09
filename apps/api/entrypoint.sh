#!/bin/sh
# Container entrypoint: wait for Postgres, migrate, seed, then run CMD.
# Makes the api self-healing against wiped volumes (fresh clones, prunes).
set -e

python - <<'EOF'
import os, time
import psycopg

url = os.environ.get("DATABASE_URL", "").replace("postgresql+psycopg://", "postgresql://")
for _ in range(30):
    try:
        psycopg.connect(url, autocommit=True).close()
        break
    except Exception:
        time.sleep(1)
else:
    raise SystemExit("database not reachable after 30s")
EOF

alembic upgrade head
python -m app.seed
exec "$@"
