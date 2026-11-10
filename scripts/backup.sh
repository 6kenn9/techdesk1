#!/bin/sh
# Резервна копія бази TechDesk з Docker (Linux/macOS): ./scripts/backup.sh
set -e
cd "$(dirname "$0")/.."
mkdir -p backups
file="backups/techdesk_$(date +%Y-%m-%d_%H-%M).sql"
docker compose exec -T db pg_dump -U techdesk -d techdesk --clean --if-exists --no-owner > "$file" || { rm -f "$file"; echo "Не вдалося зробити копію"; exit 1; }
echo "Копію збережено: $file"
