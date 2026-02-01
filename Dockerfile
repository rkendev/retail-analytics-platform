FROM python:3.11-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ src/
COPY configs/ configs/
COPY dbt_retail/ dbt_retail/

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Default: run the pipeline with prod config
CMD ["python", "-m", "src.pipeline", "--config", "configs/prod.yaml"]
