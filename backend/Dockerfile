FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app
COPY alembic.ini ./
COPY alembic ./alembic

# Editable install: the compose bind-mount ./backend:/app then shadows /app with
# live host code, and -e keeps site-packages pointing at /app/app — so uvicorn
# picks up edits without a rebuild. (A plain `pip install .` would freeze the
# built copy in site-packages and stale the dev loop.)
RUN pip install --no-cache-dir -e ".[dev]"

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
