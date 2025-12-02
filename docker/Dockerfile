FROM python:3.10-slim
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
ADD requirements.txt /code/
RUN pip install --no-cache-dir -r requirements.txt
COPY . /code/
RUN pip install -e .
