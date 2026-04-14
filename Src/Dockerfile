# Use Python 3.12-slim as it's stable and modern
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    gcc \
    curl \
    sed \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements.txt first
COPY requirements.txt .

# audioop-lts==0.2.2 requires Python 3.13. 
# Since we are on 3.12, we can safely remove it because audioop is built-in.
RUN sed -i '/audioop-lts==0.2.2/d' requirements.txt && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . /app

# Set PYTHONPATH
ENV PYTHONPATH=/app

# Expose common ports
EXPOSE 7860
EXPOSE 8000

# Run from Src directory
WORKDIR /app

# Default command
CMD ["python", "main.py"]