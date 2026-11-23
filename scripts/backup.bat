@echo off
chcp 65001 >nul
cd /d "%~dp0.."
if not exist backups mkdir backups
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HH-mm"') do set STAMP=%%i
set FILE=backups\techdesk_%STAMP%.sql
docker compose exec -T db pg_dump -U techdesk -d techdesk --clean --if-exists --no-owner > "%FILE%"
if errorlevel 1 (
  del "%FILE%" 2>nul
  echo Не вдалося зробити копію. Перевірте, що Docker запущено: docker compose up -d
  exit /b 1
)
echo Копію збережено: %FILE%
