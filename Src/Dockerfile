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

COPY requirements.txt .

# audioop-lts==0.2.2 requires Python 3.13. 
RUN sed -i '/audioop-lts/d' requirements.txt && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

# Set PYTHONPATH
ENV PYTHONPATH=/app

# Railway จะส่ง Port มาให้ผ่าน Env ดังนั้นไม่ต้องระบุตายตัว
EXPOSE 8000

# Default command
CMD ["python", "main.py"]