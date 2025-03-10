# Build stage
FROM python:3.12-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install poetry in its own venv
RUN python -m venv /opt/poetry && \
    /opt/poetry/bin/pip install poetry

# Copy files needed for building wheel
COPY pyproject.toml poetry.lock README.md ./
COPY gptme gptme/

# Install dependencies and export requirements for server
RUN /opt/poetry/bin/poetry self add poetry-plugin-export && \
    /opt/poetry/bin/poetry export --without-hashes --without dev -f requirements.txt -o requirements.txt && \
    /opt/poetry/bin/poetry export --without-hashes --without dev -E server -f requirements.txt -o requirements-server.txt && \
    /opt/poetry/bin/poetry build

# Final stage
FROM python:3.12-slim

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    git \
    tmux \
    curl \
    pandoc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy wheel and requirements, then install
COPY --from=builder /app/dist/gptme-*.whl /app/requirements*.txt /tmp/
RUN pip install /tmp/gptme-*.whl && rm /tmp/gptme-*.whl

# Create non-root user and workspace
RUN useradd -m appuser && \
    mkdir /workspace && \
    chown -R appuser:appuser /workspace

USER appuser
WORKDIR /workspace

ENTRYPOINT ["gptme"]
