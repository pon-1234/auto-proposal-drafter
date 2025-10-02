FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml ./
COPY src ./src

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Copy service code
COPY services ./services

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Expose port
EXPOSE 8080

# Run the API service (override CMD for worker service)
CMD ["uvicorn", "services.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
