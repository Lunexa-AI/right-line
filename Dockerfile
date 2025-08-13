# Multi-stage Dockerfile for RightLine API
# Optimized for production with minimal size and security

# Stage 1: Builder
FROM python:3.11-slim as builder

# Build arguments
ARG PYTHON_VERSION=3.11
ARG POETRY_VERSION=1.7.1

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_VERSION=${POETRY_VERSION} \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="$POETRY_HOME/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Install dependencies
RUN poetry install --only main --no-root --no-ansi

# Copy application code
COPY services ./services
COPY libs ./libs

# Install the application
RUN poetry install --only main --no-ansi

# Stage 2: Runtime
FROM python:3.11-slim as runtime

# Build arguments for metadata
ARG VERSION="0.1.0"
ARG COMMIT_SHA="unknown"
ARG BUILD_DATE="unknown"

# Labels for metadata
LABEL org.opencontainers.image.title="RightLine API" \
      org.opencontainers.image.description="WhatsApp-first legal copilot for Zimbabwe" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${COMMIT_SHA}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.source="https://github.com/Lunexa-AI/right-line" \
      org.opencontainers.image.licenses="MIT"

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_ENV=production \
    APP_VERSION=${VERSION}

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tesseract-ocr \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -g 1000 rightline && \
    useradd -r -u 1000 -g rightline -m -s /bin/bash rightline

# Set working directory
WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder --chown=rightline:rightline /app/.venv /app/.venv

# Copy application code
COPY --from=builder --chown=rightline:rightline /app/services ./services
COPY --from=builder --chown=rightline:rightline /app/libs ./libs

# Set Python path
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app:$PYTHONPATH"

# Switch to non-root user
USER rightline

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Run the application
CMD ["python", "-m", "uvicorn", "services.api.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2", \
     "--loop", "uvloop", \
     "--access-log", \
     "--log-config", "logging.json"]
