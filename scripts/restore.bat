@echo off
chcp 65001 >nul
cd /d "%~dp0.."
if "%~1"=="" (
  echo Вкажіть файл копії, наприклад: scripts\restore.bat backups\techdesk_2026-11-10_18-40.sql
  echo Наявні копії:
  dir /b backups\*.sql 2>nul
  exit /b 1
)
if not exist "%~1" (
  echo Файл %~1 не знайдено.
  exit /b 1
)
echo Поточні дані в базі буде замінено даними з %~1
set /p OK=Продовжити? (y/n): 
if /i not "%OK%"=="y" exit /b 0
docker compose exec -T db psql -q -o /dev/null -v ON_ERROR_STOP=1 -U techdesk -d techdesk < "%~1"
if errorlevel 1 (
  echo Під час відновлення сталася помилка.
  exit /b 1
)
docker compose restart backend >nul
echo Базу відновлено.
