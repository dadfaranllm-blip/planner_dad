#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -f .env ]; then cp .env.example .env; python3 - <<'PY'
from pathlib import Path
import secrets
p=Path('.env'); s=p.read_text(); s=s.replace('change-this-in-production',secrets.token_urlsafe(48)); p.write_text(s)
PY
fi
docker compose up -d --build
echo "Planner Suite is starting: Web http://localhost:3000 | API http://localhost:8000/health"
