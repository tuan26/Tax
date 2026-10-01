FROM python:3.11-slim

# Tesseract tiếng Việt (OCR tự host) và pg_dump cho sao lưu. Để trống chỉ dùng khi thử nghiệm ở nơi
# không tải được gói Debian; image như vậy không có OCR và không chạy được backup.
ARG SYSTEM_PACKAGES="tesseract-ocr tesseract-ocr-vie postgresql-client"
RUN if [ -n "$SYSTEM_PACKAGES" ]; then \
      apt-get update && apt-get install -y --no-install-recommends $SYSTEM_PACKAGES && rm -rf /var/lib/apt/lists/*; \
    fi

WORKDIR /srv/backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY ops /srv/ops
RUN useradd --system --uid 10001 app && mkdir -p /data/storage /data/backups && chown -R app /data
USER app
ENV STORAGE_DIR=/data/storage PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
