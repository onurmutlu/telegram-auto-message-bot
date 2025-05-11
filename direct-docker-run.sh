#!/bin/bash
set -e

echo "Telegram Bot - Docker Kurulumu"
echo "=============================="

# Temizlik yap
echo "[1] Mevcut konteynerleri temizleme..."
docker stop telegram-bot-app telegram-bot-db telegram-bot-redis 2>/dev/null || true
docker rm telegram-bot-app telegram-bot-db telegram-bot-redis 2>/dev/null || true

# Ortam değişkenlerini ayarla
if [ -f .env ]; then
  echo "[2] .env dosyası bulundu, kullanılıyor..."
  export $(grep -v '^#' .env | xargs)
elif [ -f example.env ]; then
  echo "[2] example.env dosyası bulundu, kullanılıyor..."
  export $(grep -v '^#' example.env | xargs)
else
  echo "[2] .env dosyası bulunamadı, örnek değerler kullanılıyor..."
  # Örnek değerler
  export TELEGRAM_API_ID="12345678"
  export TELEGRAM_API_HASH="abcdef1234567890abcdef1234567890"
  export TELEGRAM_BOT_TOKEN="1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZ"
fi

echo "API ID: $TELEGRAM_API_ID"
echo "API HASH: $TELEGRAM_API_HASH (maskelenmiş)"
echo "BOT TOKEN: $TELEGRAM_BOT_TOKEN (maskelenmiş)"

# Docker ağı oluştur
echo "[3] Docker ağı oluşturuluyor..."
docker network create telegram-bot-network 2>/dev/null || true

# Veritabanı ve Redis başlat
echo "[4] PostgreSQL ve Redis konteynerleri başlatılıyor..."
docker run -d --name telegram-bot-db \
  --network telegram-bot-network \
  -e POSTGRES_USER=botuser \
  -e POSTGRES_PASSWORD=botpass \
  -e POSTGRES_DB=botdb \
  -p 5432:5432 \
  postgres:14-alpine

docker run -d --name telegram-bot-redis \
  --network telegram-bot-network \
  -p 6379:6379 \
  redis:7-alpine

echo "[5] Veritabanı ve Redis başlaması bekleniyor..."
sleep 10

# Docker imajı oluştur
echo "[6] Docker imajı oluşturuluyor..."
docker build -f Dockerfile.minimal -t telegram-bot:latest .

# Uygulama konteyneri başlat
echo "[7] Uygulama konteyneri başlatılıyor..."
docker run -d --name telegram-bot-app \
  --network telegram-bot-network \
  -p 8000:8000 \
  -v $(pwd)/runtime:/app/runtime \
  -e TELEGRAM_API_ID="${TELEGRAM_API_ID}" \
  -e TELEGRAM_API_HASH="${TELEGRAM_API_HASH}" \
  -e TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN}" \
  -e API_ID="${TELEGRAM_API_ID}" \
  -e API_HASH="${TELEGRAM_API_HASH}" \
  -e BOT_TOKEN="${TELEGRAM_BOT_TOKEN}" \
  -e DATABASE_URL="postgresql://botuser:botpass@telegram-bot-db:5432/botdb" \
  -e REDIS_URL="redis://telegram-bot-redis:6379/0" \
  -e SESSION_NAME="telegram_session" \
  -e LOG_LEVEL="INFO" \
  -e ENV="staging" \
  telegram-bot:latest

echo "[8] Konteyner durumunu kontrol ediliyor..."
docker ps

echo "[9] Konteyner logları kontrol ediliyor (5 saniye sonra)..."
sleep 5
docker logs telegram-bot-app

echo ""
echo "Kurulum tamamlandı! Bot http://localhost:8000 adresinde çalışıyor." 