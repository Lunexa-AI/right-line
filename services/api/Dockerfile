# Multi-stage Dockerfile for RightLine API Service
# Optimized for production with minimal size and security

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

# Install system build dependencies
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

# Copy dependency files (cache layer)
COPY ../../pyproject.toml ../../poetry.lock ./

# Install dependencies (this layer is cached unless deps change)
RUN poetry install --only main --no-root --no-ansi

# Copy libs (shared code)
COPY ../../libs ./libs

# Copy service code
COPY . ./services/api

# Install the application
RUN poetry install --only main --no-ansi

# Stage 2: Runtime
FROM python:3.11-slim as runtime

# Build arguments for metadata
ARG VERSION="0.1.0"
ARG COMMIT_SHA="unknown"
ARG BUILD_DATE="unknown"
ARG SERVICE_NAME="api"

# Labels for metadata
LABEL org.opencontainers.image.title="RightLine API Service" \
      org.opencontainers.image.description="API Gateway and orchestrator for RightLine" \
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
    PORT=8000

# Install runtime dependencies (minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
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
COPY --from=builder --chown=rightline:rightline /app/services/api ./services/api

# Set Python path
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app:$PYTHONPATH"

# Create necessary directories with correct permissions
RUN mkdir -p /app/logs && chown -R rightline:rightline /app/logs

# Switch to non-root user
USER rightline

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:${PORT}/health || exit 1

# Expose port
EXPOSE ${PORT}

# Run the application
CMD ["python", "-m", "uvicorn", "services.api.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2", \
     "--loop", "uvloop", \
     "--access-log"]
