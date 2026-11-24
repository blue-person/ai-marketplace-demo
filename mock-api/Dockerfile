FROM python:3.13-slim

# uv installs the dependencies from the lock file, so every build gets the same versions.
COPY --from=ghcr.io/astral-sh/uv:0.13.9 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_NO_DEV=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app
RUN useradd --create-home --uid 10002 mock

COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen

COPY app.py .
USER mock
EXPOSE 9000
CMD ["gunicorn", "--bind", "0.0.0.0:9000", "--workers", "2", "--threads", "4", "--access-logfile", "-", "app:app"]
