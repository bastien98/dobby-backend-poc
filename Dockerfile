FROM python:3.12-slim

WORKDIR /app

# Install system dependencies (if any)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry

# Copy only requirements to cache them in docker layer
COPY pyproject.toml poetry.lock ./

# Project initialization:
# 1. Disable virtualenv creation (we want system-wide install in container)
# 2. Install only main dependencies (no dev dependencies like pytest)
RUN poetry config virtualenvs.create false \
    && poetry install --only main --no-interaction --no-ansi --no-root

# Copy the rest of the application code
COPY . .

# Expose port (AWS App Runner defaults to 8080)
EXPOSE 8080

# Command to run the application using python module execution
# Use PORT environment variable for Railway support, default to 8080
CMD sh -c "python -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"
