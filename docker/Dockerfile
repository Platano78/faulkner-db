FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    redis-tools \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy application code
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir pydantic redis psycopg2-binary

# Create health check endpoint
COPY docker/healthcheck.py /app/healthcheck.py

# Expose application port
EXPOSE 8000

# Health check script
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python /app/healthcheck.py

# Start application
CMD ["python", "app/main.py"]
