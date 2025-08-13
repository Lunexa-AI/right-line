# Multi-stage Dockerfile for RightLine Ingestion Service
# Handles document processing, OCR, and indexing

# Stage 1: Builder
FROM python:3.11-slim as builder

# Build arguments
ARG PYTHON_VERSION=3.11
ARG POETRY_VERSION=1.7.1

# Set environment variables for build
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_VERSION=${POETRY_VERSION} \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1

# Install system build dependencies (including poppler for PDF processing)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="$POETRY_HOME/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy dependency files (cache layer)
COPY ../../pyproject.toml ../../poetry.lock ./

# Install dependencies
RUN poetry install --only main --no-root --no-ansi

# Copy libs (shared code)
COPY ../../libs ./libs

# Copy service code
COPY . ./services/ingestion

# Install the application
RUN poetry install --only main --no-ansi

# Stage 2: Runtime
FROM python:3.11-slim as runtime

# Build arguments for metadata
ARG VERSION="0.1.0"
ARG COMMIT_SHA="unknown"
ARG BUILD_DATE="unknown"
ARG SERVICE_NAME="ingestion"

# Labels for metadata
LABEL org.opencontainers.image.title="RightLine Ingestion Service" \
      org.opencontainers.image.description="Document processing and ingestion pipeline" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${COMMIT_SHA}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.source="https://github.com/Lunexa-AI/right-line" \
      org.opencontainers.image.licenses="MIT" \
      service="${SERVICE_NAME}"

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_ENV=production \
    APP_VERSION=${VERSION} \
    SERVICE_NAME=${SERVICE_NAME} \
    WORKER_CONCURRENCY=4

# Install runtime dependencies for document processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    # OCR support
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-sna \
    tesseract-ocr-nya \
    # PDF processing
    poppler-utils \
    # Image processing
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -g 1000 rightline && \
    useradd -r -u 1000 -g rightline -m -s /bin/bash rightline

# Set working directory
WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder --chown=rightline:rightline /app/.venv /app/.venv

# Copy application code
COPY --from=builder --chown=rightline:rightline /app/libs ./libs
COPY --from=builder --chown=rightline:rightline /app/services/ingestion ./services/ingestion

# Set Python path
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app:$PYTHONPATH"

# Create necessary directories with correct permissions
RUN mkdir -p /app/data/documents /app/data/ocr /app/logs /app/tmp && \
    chown -R rightline:rightline /app/data /app/logs /app/tmp

# Switch to non-root user
USER rightline

# No exposed port for worker service
# This service runs as Arq worker consuming from Redis queue

# Run the worker
CMD ["python", "-m", "arq", "services.ingestion.worker.WorkerSettings"]
