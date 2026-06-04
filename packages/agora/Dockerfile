# =============================================================================
# Agora — MCP Service Mesh Dockerfile
# =============================================================================
# Stage 1: builder — install dependencies
# Stage 2: runtime — minimal non-root image
#
# Usage:
#   docker build . -t agora:latest
#   docker run -d -p 7430:7430 agora:latest agora-web
#   docker run -d -p 7422:7422 agora:latest agora-mcp
# =============================================================================

# ── Stage 1: builder ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential gcc \
    && rm -rf /var/lib/apt/lists/*

# Core models is a local workspace dependency — install it first
COPY packages/core-models/ /build/core-models/
RUN pip install --no-cache-dir /build/core-models/

# Install agora itself (depends on core-models)
COPY packages/agora/ /build/agora/
RUN pip install --no-cache-dir /build/agora/


# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

LABEL org.opencontainers.image.title="Agora — MCP Service Mesh"
LABEL org.opencontainers.image.description="Route, monitor, and govern inter-service communication"
LABEL org.opencontainers.image.source="https://github.com/starlink-awaken/omostation"

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates tini \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 1001 appgroup \
 && useradd  --uid 1001 --gid appgroup --shell /bin/bash --create-home appuser

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER appuser

EXPOSE 7430 7422 7431

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:7430/ || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["agora-mcp"]
