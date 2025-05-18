FROM python:3.9-slim

LABEL maintainer="siyahkare"
LABEL version="4.0.0"
LABEL description="Telegram Bot"

# Çalışma dizini oluştur
WORKDIR /app

# Önbelleği kapatarak Docker imajını daha küçük tut
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# PostgreSQL istemcisi ve diğer bağımlılıkları kur
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    build-essential \
    libpq-dev \
    netcat-traditional \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# requirements.txt'yi kopyala
COPY requirements.txt .

# Python bağımlılıklarını yükle
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Uygulama kodunu kopyala
COPY . .

# Gerekli dizinleri oluştur
RUN mkdir -p runtime/database/backups runtime/logs runtime/sessions data/media logs session

# Başlangıç betiğini çalıştırma izni ver
RUN chmod +x start.sh

# Uygulamayı çalıştır
CMD ["./start.sh"] 