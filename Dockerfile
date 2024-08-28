# Build stage
FROM python:3.10-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry

# Set the working directory
WORKDIR /app

# Copy only the files needed for installation
COPY pyproject.toml poetry.lock* ./

# Install project dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root --without=dev # -E server -E browser -E datascience

# Final stage
FROM python:3.10-slim

# Install git and common tools
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy installed packages from builder stage
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy the project files
#COPY gptme .
COPY . .

# Set PYTHONPATH
ENV PYTHONPATH=/app

# Create a non-root user and switch to it
RUN useradd -m appuser
USER appuser

# Disable virtualenv creation
RUN poetry config virtualenvs.create false

# Expose port 5000
EXPOSE 5000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/ || exit 1

# TODO: make into separate image
# CMD ["poetry", "run", "python", "-m", "gptme.server"]

# Entrypoint if prompt/args given, run the CLI
ENTRYPOINT ["poetry", "run", "python", "-m", "gptme"]
