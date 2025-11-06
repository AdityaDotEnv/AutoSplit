# backend/Dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps:
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc \
    tesseract-ocr tesseract-ocr-eng \
    libgl1 \
 && rm -rf /var/lib/apt/lists/*

# Let pytesseract find the binary
ENV TESSERACT_CMD=/usr/bin/tesseract
# ✅ Also tell it where the language data lives on Debian
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the app
COPY . .

EXPOSE 5000

# (Optional) Quick runtime check that tesseract exists
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD tesseract --version || exit 1

CMD ["python", "app.py"]
