FROM python:3.13-slim

RUN apt-get update && apt-get install -y \
                gcc \
                libffi-dev \
                libssl-dev \
                postgresql-client \
                python3-dev \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    DATABASE_URL=postgres://postgres:postgres@db:5432/postgres \
    FLASK_SECRET_KEY=GBhQrZfbN9KGMcyLVImGeS2Wtj3SFCdF \
    RABBIT_MANAGEMENT_URL=http://pulse:15672/api/ \
    EMAIL_ENABLED=0

WORKDIR /code

# Upgrade pip to latest version
RUN pip install --no-cache-dir --upgrade pip

# Copy application code
COPY . /code/

# Install the application in editable mode
RUN pip install --no-cache-dir -e .
