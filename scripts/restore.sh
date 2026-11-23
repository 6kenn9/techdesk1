#!/bin/sh
set -e
cd "$(dirname "$0")/.."
[ -f "$1" ] || { echo "Вкажіть наявний файл копії"; ls backups/*.sql 2>/dev/null; exit 1; }
docker compose exec -T db psql -q -o /dev/null -v ON_ERROR_STOP=1 -U techdesk -d techdesk < "$1"
docker compose restart backend >/dev/null
echo "Базу відновлено."
