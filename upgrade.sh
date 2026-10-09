#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
./backup.sh
docker compose build api web
docker compose up -d db
docker compose run --rm api python migrate.py
docker compose up -d --remove-orphans
echo 'Upgrade complete. Central PostgreSQL data volume preserved.'
