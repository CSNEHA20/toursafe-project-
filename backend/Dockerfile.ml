# Multi-stage production Dockerfile for TourSafe ML Inference & Lifecycle Service
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Runtime Stage
FROM python:3.11-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    dumb-init \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -g 10001 toursafe && \
    useradd -u 10001 -g toursafe -s /bin/bash -m toursafe

WORKDIR /app

COPY --from=builder --chown=toursafe:toursafe /root/.local /home/toursafe/.local
COPY --chown=toursafe:toursafe backend/app /app/app

ENV PATH=/home/toursafe/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENVIRONMENT=production \
    ML_SERVICE_ROLE=inference_worker

USER toursafe:toursafe

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health/live || exit 1

ENTRYPOINT ["/usr/bin/dumb-init", "--"]
CMD ["python", "-m", "app.services.ml.engine"]
