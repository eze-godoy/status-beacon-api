# syntax=docker/dockerfile:1

# Build stage - using uv's official image with Python included
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

# Enable bytecode compilation for faster startup
ENV UV_COMPILE_BYTECODE=1
# Use copy mode to avoid hardlink issues between cache and venv
ENV UV_LINK_MODE=copy
# Use the system Python (same version in both stages)
ENV UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# Install dependencies first (better layer caching)
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev

# Copy source and install the project
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

# Production stage - slim image without uv
FROM python:3.13-slim-bookworm AS production

# Security: Create non-root user
RUN groupadd --system --gid 1000 appgroup && \
    useradd --system --gid 1000 --uid 1000 --create-home appuser

WORKDIR /app

# Copy the application from the builder (with correct ownership)
COPY --from=builder --chown=appuser:appgroup /app /app

# Add venv to PATH
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install curl for health checks (more reliable than Python-based checks)
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Run the application
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
