# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry

# Copy the project files into the container
COPY pyproject.toml poetry.lock* README.md ./
COPY gptme ./gptme
COPY static ./static
COPY media ./media

# Install project dependencies including eval extras
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi -E server -E browser -E datascience

# Make port 5000 available to the world outside this container
# (assuming your Flask server runs on port 5000)
EXPOSE 5000

# Set environment variable for eval
ENV PYTHONPATH=/app

# Default command to run the server
CMD ["poetry", "run", "gptme-server"]

# Add an entry point for running evals
ENTRYPOINT ["poetry", "run", "python", "-m", "gptme.eval.main"]
