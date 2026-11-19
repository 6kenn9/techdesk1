FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
# Повільний інтернет: довший таймаут, повтори й кеш завантажень між спробами збірки
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --default-timeout=300 --retries 10 -r requirements.txt
COPY . .
# Хостинг може задати порт змінною PORT (Render — 10000); локально лишається 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
