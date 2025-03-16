FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Install dependencies first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories with proper permissions
RUN mkdir -p /app/data /app/logs && \
    chmod 777 /app/data /app/logs

# Install curl for healthcheck
RUN apt-get update && apt-get install -y curl && apt-get clean

# Expose the port
EXPOSE 8000

# Command to run the application
CMD ["python", "main.py"]