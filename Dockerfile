# Use Python 3.11 slim image
FROM python:3.11-slim AS horizon-runtime

# Set working directory
WORKDIR /app

# Install uv for faster dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY data ./data
COPY profiles ./profiles
COPY .env.example .env.example

# Install optional extras from a comma-separated list, e.g. "trafilatura,openbb".
ARG EXTRAS=""
RUN set -eu; \
    set --; \
    if [ -n "$EXTRAS" ]; then \
        case "$EXTRAS" in ,*|*,|*,,*) echo "Invalid EXTRAS list: $EXTRAS" >&2; exit 2 ;; esac; \
        old_ifs=$IFS; IFS=,; \
        for extra in $EXTRAS; do \
            case "$extra" in [._-]*|*[._-]|*[!A-Za-z0-9._-]*) echo "Invalid extra: $extra" >&2; exit 2 ;; esac; \
            set -- "$@" --extra "$extra"; \
        done; \
        IFS=$old_ifs; \
    fi; \
    uv sync --frozen --no-dev "$@"

# Runtime data is mounted here; keep the image and process unprivileged.
RUN useradd --create-home --uid 10001 horizon \
    && chown -R horizon:horizon /app

# Create volume mount points
VOLUME ["/app/data"]

# Set environment variables
ENV PYTHONUNBUFFERED=1
USER horizon

# Run the application
ENTRYPOINT ["uv", "run", "horizon"]
CMD []

# Optional scheduler image; the final runtime target preserves one-shot usage.
FROM horizon-runtime AS scheduler
USER root
ARG TARGETARCH
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends ca-certificates curl tzdata \
    && rm -rf /var/lib/apt/lists/*
RUN set -eu; \
    case "$TARGETARCH" in \
        amd64) checksum=71b0d58cc53f6bd72cf2f293e09e294b79c666d8 ;; \
        arm64) checksum=e0f0c06ebc5627e43b25475711e694450489ab00 ;; \
        *) echo "Unsupported scheduler architecture: $TARGETARCH" >&2; exit 1 ;; \
    esac; \
    curl -fsSL --retry 3 "https://github.com/aptible/supercronic/releases/download/v0.2.33/supercronic-linux-${TARGETARCH}" -o /usr/local/bin/supercronic; \
    echo "$checksum  /usr/local/bin/supercronic" | sha1sum -c -; \
    chmod 755 /usr/local/bin/supercronic
COPY docker/horizon.crontab /app/horizon.crontab
ENV TZ=Asia/Shanghai
USER horizon
ENTRYPOINT ["/usr/local/bin/supercronic"]
CMD ["/app/horizon.crontab"]

FROM horizon-runtime AS runtime
