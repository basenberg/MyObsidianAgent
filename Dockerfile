# syntax=docker/dockerfile:1

# Multi-stage build for optimized production image
# Using official uv images and Python 3.12 on Debian Bookworm Slim

# Stage 1: Builder - Install dependencies
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

# Set working directory
WORKDIR /app

# Enable bytecode compilation for faster startup
ENV UV_COMPILE_BYTECODE=1

# Use copy link mode for cache mounts
ENV UV_LINK_MODE=copy

# Copy dependency files first (better layer caching)
COPY pyproject.toml uv.lock ./

# Install dependencies only (not the project itself)
# This layer is cached unless dependencies change
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-dev

# Copy application source code
COPY . .

# Install the project itself with non-editable install
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-editable --no-dev

# Stage 2: Runtime - Minimal production image
FROM python:3.12-slim-bookworm

# Set working directory
WORKDIR /app

# Copy only the virtual environment from builder
# This significantly reduces the final image size
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY . .

# Ensure the virtual environment is used
ENV PATH="/app/.venv/bin:$PATH"

# Expose port (adjust if your app uses a different port)
EXPOSE 8123

# Run the application
# Adjust the module/script name based on your entry point
CMD ["python", "-m", "app.main"]
