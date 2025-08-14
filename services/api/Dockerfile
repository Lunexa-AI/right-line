# Lightweight Dockerfile for RightLine API MVP
# Multi-stage build for minimal image size

# Build stage
FROM python:3.11-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /build

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Runtime stage
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 -s /bin/bash rightline

# Set working directory
WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /root/.local /home/rightline/.local

# Copy application code
COPY --chown=rightline:rightline libs/ /app/libs/
COPY --chown=rightline:rightline services/api/ /app/services/api/

# Create necessary directories
RUN mkdir -p /data /app/logs && \
    chown -R rightline:rightline /data /app/logs

# Set Python path
ENV PYTHONPATH=/app:$PYTHONPATH
ENV PATH=/home/rightline/.local/bin:$PATH

# Switch to non-root user
USER rightline

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

# Run the application
CMD ["python", "-m", "uvicorn", "services.api.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--loop", "uvloop", \
     "--access-log", \
     "--log-config", "/app/services/api/logging.json"]