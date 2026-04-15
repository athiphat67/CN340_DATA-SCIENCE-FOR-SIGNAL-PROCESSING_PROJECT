FROM python:3.12-slim

# ตั้งค่าพื้นฐาน
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

WORKDIR /app

# ติดตั้ง System Dependencies (ถ้าต้องใช้ในการ Build)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ติดตั้ง Python Dependencies
COPY requirements.txt .
RUN sed -i '/audioop-lts/d' requirements.txt && \
    pip install --no-cache-dir -r requirements.txt

# Copy ไฟล์ทั้งหมดเข้า Container
COPY . .

# กำหนด Default Port เป็น 8080 (เผื่อไว้ในกรณีรัน Local)
ENV PORT=8080

# รันแอป
# ใช้คำสั่ง python main.py โดยตรงได้เลย เพราะโค้ดคุณดึง os.environ.get("PORT") อยู่แล้ว
CMD ["python", "main.py"]