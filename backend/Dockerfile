# Build context is the project root (see docker-compose.yml).
FROM python:3.13-slim

# uv installs the dependencies from the lock file, so every build gets the same versions.
COPY --from=ghcr.io/astral-sh/uv:0.13.9 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_NO_DEV=1 \
    PATH="/app/backend/.venv/bin:$PATH"

WORKDIR /app/backend

COPY backend/pyproject.toml backend/uv.lock backend/.python-version ./
RUN uv sync --frozen

COPY . /app

EXPOSE 8000

CMD ["gunicorn", "-c", "gunicorn.conf.py", "app:create_app()"]
