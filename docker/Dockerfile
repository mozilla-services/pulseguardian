FROM python:3.13-slim
RUN apt-get update && apt-get install -y \
                gcc \
                libffi-dev \
                libssl-dev \
                postgresql-client \
                python3-dev \
    && rm -rf /var/lib/apt/lists/*
ENV PYTHONUNBUFFERED 1
ENV DATABASE_URL postgres://postgres:postgres@db:5432/postgres
ENV FLASK_SECRET_KEY GBhQrZfbN9KGMcyLVImGeS2Wtj3SFCdF
ENV RABBIT_MANAGEMENT_URL http://pulse:15672/api/
ENV EMAIL_ENABLED 0
WORKDIR /code

# Upgrade pip to latest version
RUN pip install --no-cache-dir --upgrade pip

# Copy and install dependencies
ADD requirements.txt /code/
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . /code/

# Install the application in editable mode
RUN pip install --no-cache-dir -e .
