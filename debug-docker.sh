#!/bin/bash
# Adım adım hata ayıklamalı Docker kurulum script'i

echo "=== DEBUG DOCKER KURULUMU ==="
set -x  # Komutları ekranda görüntüle

# Önce temizlik
echo "1) Eski konteynerleri temizleme..."
docker stop telegram-bot-server db-server redis-server 2>/dev/null || true
docker rm telegram-bot-server db-server redis-server 2>/dev/null || true

# Ortam değişkenlerini manuel olarak ayarla
echo "2) Test ortam değişkenlerini ayarlama..."
TEST_API_ID="12345678"
TEST_API_HASH="abcdef1234567890abcdef1234567890"
TEST_BOT_TOKEN="1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZ"

# Runtime dizinlerini oluştur
echo "3) Çalışma dizinlerini oluşturma..."
mkdir -p runtime/database runtime/logs runtime/sessions
chmod -R 777 runtime

# Tek tek konteynerleri başlat
echo "4) Veritabanı konteyneri başlatma..."
docker run --name db-server \
  -e POSTGRES_USER=botuser \
  -e POSTGRES_PASSWORD=botpass \
  -e POSTGRES_DB=botdb \
  -p 5432:5432 \
  -d postgres:14-alpine

echo "5) Redis konteyneri başlatma..."
docker run --name redis-server \
  -p 6379:6379 \
  -d redis:7-alpine

# Servisler başlayana kadar bekle
echo "6) Veritabanı ve Redis başlaması bekleniyor..."
sleep 10

# En basit Docker imajı oluştur
echo "7) Docker imajı oluşturma..."
cat > Dockerfile.debug << EOF
FROM python:3.10-slim
WORKDIR /app
RUN apt-get update && apt-get install -y libpq-dev && apt-get clean
COPY requirements.staging.txt /app/requirements.txt
RUN pip install -r requirements.txt
COPY app /app/app
COPY alembic.ini /app/
EXPOSE 8000
CMD ["python", "-m", "app.main"]
EOF

# Docker imajı oluştur
docker build -f Dockerfile.debug -t telegram-debug:latest .

# Uygulama konteyneri başlat
echo "8) Test konteyneri başlatma..."
docker run --name telegram-bot-server \
  --link db-server:postgres \
  --link redis-server:redis \
  -e TELEGRAM_API_ID="$TEST_API_ID" \
  -e TELEGRAM_API_HASH="$TEST_API_HASH" \
  -e TELEGRAM_BOT_TOKEN="$TEST_BOT_TOKEN" \
  -e API_ID="$TEST_API_ID" \
  -e API_HASH="$TEST_API_HASH" \
  -e BOT_TOKEN="$TEST_BOT_TOKEN" \
  -e DATABASE_URL="postgresql://botuser:botpass@postgres:5432/botdb" \
  -e REDIS_URL="redis://redis:6379/0" \
  -e SESSION_NAME="telegram_session" \
  -e ENV="staging" \
  -e DEBUG=true \
  -v $(pwd)/runtime:/app/runtime \
  -p 8000:8000 \
  -d telegram-debug:latest

# Konteyner durumu ve logları
echo "9) Konteyner durumu:"
docker ps -a

echo "10) Bot logları:"
sleep 5
docker logs telegram-bot-server

set +x  # Debug modu kapat
echo "=== İŞLEM TAMAMLANDI ===" 