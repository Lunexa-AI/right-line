# Multi-stage Dockerfile for RightLine Retrieval Service
# Handles hybrid search (BM25 + vector) and reranking

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

# Install system build dependencies (for numpy/scipy compilation)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    gcc \
    g++ \
    gfortran \
    libopenblas-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="$POETRY_HOME/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy dependency files (cache layer)
COPY ../../pyproject.toml ../../poetry.lock ./

# Install dependencies (including ML libraries)
RUN poetry install --only main --no-root --no-ansi

# Copy libs (shared code)
COPY ../../libs ./libs

# Copy service code
COPY . ./services/retrieval

# Install the application
RUN poetry install --only main --no-ansi

# Stage 2: Runtime
FROM python:3.11-slim as runtime

# Build arguments for metadata
ARG VERSION="0.1.0"
ARG COMMIT_SHA="unknown"
ARG BUILD_DATE="unknown"
ARG SERVICE_NAME="retrieval"

# Labels for metadata
LABEL org.opencontainers.image.title="RightLine Retrieval Service" \
      org.opencontainers.image.description="Hybrid search and ranking service" \
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
    PORT=8001 \
    # ML optimization
    OMP_NUM_THREADS=4 \
    MKL_NUM_THREADS=4 \
    OPENBLAS_NUM_THREADS=4

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    # Linear algebra libraries for numpy/scipy
    libopenblas0 \
    libgomp1 \
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
COPY --from=builder --chown=rightline:rightline /app/services/retrieval ./services/retrieval

# Set Python path
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app:$PYTHONPATH"

# Create necessary directories with correct permissions
RUN mkdir -p /app/models /app/cache /app/logs && \
    chown -R rightline:rightline /app/models /app/cache /app/logs

# Switch to non-root user
USER rightline

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:${PORT}/health || exit 1

# Expose port
EXPOSE ${PORT}

# Run the service
CMD ["python", "-m", "uvicorn", "services.retrieval.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8001", \
     "--workers", "1", \
     "--loop", "uvloop"]
