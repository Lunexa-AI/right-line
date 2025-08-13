# Multi-stage Dockerfile for RightLine Summarizer Service
# Handles multi-tier summarization with local models and API fallback

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

# Install system build dependencies (for PyTorch/ONNX)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    gcc \
    g++ \
    cmake \
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
COPY . ./services/summarizer

# Install the application
RUN poetry install --only main --no-ansi

# Stage 2: Model download (separate stage for caching)
FROM builder as model-downloader

# Download models during build (cached layer)
RUN python -c "from sentence_transformers import SentenceTransformer; \
    model = SentenceTransformer('all-MiniLM-L6-v2'); \
    model.save('/app/models/sentence-transformer')"

# Stage 3: Runtime
FROM python:3.11-slim as runtime

# Build arguments for metadata
ARG VERSION="0.1.0"
ARG COMMIT_SHA="unknown"
ARG BUILD_DATE="unknown"
ARG SERVICE_NAME="summarizer"

# Labels for metadata
LABEL org.opencontainers.image.title="RightLine Summarizer Service" \
      org.opencontainers.image.description="Multi-tier text summarization service" \
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
    PORT=8002 \
    # Model settings
    MODEL_PATH=/app/models \
    DEVICE=cpu \
    BATCH_SIZE=8 \
    MAX_LENGTH=512 \
    # PyTorch optimization
    OMP_NUM_THREADS=4 \
    MKL_NUM_THREADS=4 \
    TORCH_NUM_THREADS=4 \
    # Disable gradients for inference
    PYTORCH_ENABLE_MPS_FALLBACK=1

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    # Required for ONNX Runtime
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -g 1000 rightline && \
    useradd -r -u 1000 -g rightline -m -s /bin/bash rightline

# Set working directory
WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder --chown=rightline:rightline /app/.venv /app/.venv

# Copy models from model-downloader stage
COPY --from=model-downloader --chown=rightline:rightline /app/models /app/models

# Copy application code
COPY --from=builder --chown=rightline:rightline /app/libs ./libs
COPY --from=builder --chown=rightline:rightline /app/services/summarizer ./services/summarizer

# Set Python path
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app:$PYTHONPATH"

# Create necessary directories with correct permissions
RUN mkdir -p /app/cache /app/logs && \
    chown -R rightline:rightline /app/cache /app/logs /app/models

# Switch to non-root user
USER rightline

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
  CMD curl -f http://localhost:${PORT}/health || exit 1

# Expose port
EXPOSE ${PORT}

# Run the service
CMD ["python", "-m", "uvicorn", "services.summarizer.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8002", \
     "--workers", "1", \
     "--loop", "uvloop"]
