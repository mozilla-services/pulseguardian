FROM ghcr.io/astral-sh/uv:python3.14-trixie-slim

RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    DATABASE_URL=postgres://postgres:postgres@db:5432/postgres \
    RABBIT_MANAGEMENT_URL=http://pulse:15672/api/ \
    EMAIL_ENABLED=0

WORKDIR /code

# Install dependencies first for layer caching
COPY uv.lock pyproject.toml /code/
RUN uv sync --frozen --no-install-project

# Copy application code
COPY . /code/
RUN uv sync --frozen
