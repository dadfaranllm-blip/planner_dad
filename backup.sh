#!/usr/bin/env bash
set -euo pipefail
mkdir -p backups
stamp=$(date -u +%Y%m%dT%H%M%SZ)
docker compose exec -T db pg_dump -U "${POSTGRES_USER:-planner}" "${POSTGRES_DB:-planner}" | gzip > "backups/planner-${stamp}.sql.gz"
echo "backups/planner-${stamp}.sql.gz"
