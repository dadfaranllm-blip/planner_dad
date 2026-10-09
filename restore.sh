#!/usr/bin/env bash
set -euo pipefail
f=${1:?Usage: ./restore.sh backup.sql.gz}
gzip -dc "$f" | docker compose exec -T db psql -v ON_ERROR_STOP=1 -U "${POSTGRES_USER:-planner}" "${POSTGRES_DB:-planner}"
