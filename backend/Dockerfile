# Multi-stage production Dockerfile for TourSafe Backend API
# Stage 1: Build & Dependencies
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Production Minimal Runtime
FROM python:3.11-slim AS runtime

# Install dumb-init for reliable PID 1 signal forwarding (SIGTERM / SIGINT) and curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    dumb-init \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-privileged system group and user
RUN groupadd -g 10001 toursafe && \
    useradd -u 10001 -g toursafe -s /bin/bash -m toursafe

WORKDIR /app

# Copy Python packages from builder stage to non-root user directory
COPY --from=builder --chown=toursafe:toursafe /root/.local /home/toursafe/.local

# Copy application source code
COPY --chown=toursafe:toursafe backend/app /app/app
COPY --chown=toursafe:toursafe backend/requirements.txt /app/

# Environment configurations
ENV PATH=/home/toursafe/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENVIRONMENT=production \
    PORT=8000

USER toursafe:toursafe

EXPOSE 8000

# Health check against liveness endpoint
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health/live || exit 1

ENTRYPOINT ["/usr/bin/dumb-init", "--"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--log-level", "info", "--no-access-log"]
