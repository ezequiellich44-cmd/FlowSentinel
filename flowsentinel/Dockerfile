FROM python:3.12-slim

WORKDIR /app

# Install build-essential for any compiled dependencies (e.g. uvloop, asyncpg)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY src/ ./src/
COPY scripts/ ./scripts/

RUN pip install --no-cache-dir -e .

EXPOSE 8000 8002

CMD ["python", "-m", "flowsentinel.main"]
