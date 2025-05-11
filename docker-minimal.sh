#!/bin/bash
# MacOS için özel basitleştirilmiş Docker kurulum scripti
set -e # Herhangi bir hata olursa scripti durdur

# Renk kodları
GREEN="\033[0;32m"
YELLOW="\033[0;33m"
RED="\033[0;31m"
NC="\033[0m" # Normal renk

# Adım 1: Docker Desktop durumunu kontrol et
echo -e "${YELLOW}1. Docker Desktop durumu kontrol ediliyor...${NC}"
if ! docker system info > /dev/null 2>&1; then
  echo -e "${RED}HATA: Docker Desktop çalışmıyor. Lütfen Docker Desktop uygulamasını açın.${NC}"
  exit 1
fi
echo -e "${GREEN}Docker Desktop çalışıyor.${NC}"

# Adım 2: Tüm konteynerleri durdur (güvenli)
echo -e "${YELLOW}2. Tüm Docker konteynerleri durduruluyor...${NC}"
docker stop $(docker ps -aq) > /dev/null 2>&1 || true
docker rm $(docker ps -aq) > /dev/null 2>&1 || true
echo -e "${GREEN}Tüm konteynerler durduruldu.${NC}"

# Adım 3: Ortam değişkenlerini yükle
echo -e "${YELLOW}3. Ortam değişkenleri yükleniyor...${NC}"
if [ -f .env ]; then
  set -a
  source .env
  set +a
  echo -e "${GREEN}Ortam değişkenleri .env dosyasından yüklendi.${NC}"
else
  echo -e "${RED}UYARI: .env dosyası bulunamadı! Lütfen .env dosyasını oluşturun.${NC}"
  exit 1
fi

# Ortam değişkenlerini göster
echo "API_ID        : ${API_ID:-YOK}"
echo "API_HASH      : ${API_HASH:-YOK}"
echo "BOT_TOKEN     : ${BOT_TOKEN:-YOK}"
echo "DB_USER       : ${DB_USER:-postgres}"
echo "DB_PASSWORD   : ${DB_PASSWORD:-postgres}"
echo "DB_NAME       : ${DB_NAME:-telegram_bot}"

# Değişkenleri kontrol et
if [ -z "$API_ID" ] || [ -z "$API_HASH" ] || [ -z "$BOT_TOKEN" ]; then
  echo -e "${RED}HATA: API_ID, API_HASH veya BOT_TOKEN değerleri eksik.${NC}"
  exit 1
fi

# Dizinleri oluştur
echo -e "${YELLOW}4. Çalışma dizinleri oluşturuluyor...${NC}"
mkdir -p ./data/db ./data/redis ./logs ./sessions
chmod -R 777 ./data ./logs ./sessions
echo -e "${GREEN}Çalışma dizinleri oluşturuldu.${NC}"

# PostgreSQL veritabanını başlat (macOS için bridge network)
echo -e "${YELLOW}5. PostgreSQL konteyneri başlatılıyor...${NC}"
docker run -d \
  --name postgres-db \
  -e POSTGRES_USER="${DB_USER:-postgres}" \
  -e POSTGRES_PASSWORD="${DB_PASSWORD:-postgres}" \
  -e POSTGRES_DB="${DB_NAME:-telegram_bot}" \
  -v "$(pwd)/data/db:/var/lib/postgresql/data" \
  -p 5432:5432 \
  postgres:14-alpine

# Redis'i başlat
echo -e "${YELLOW}6. Redis konteyneri başlatılıyor...${NC}"
docker run -d \
  --name redis-cache \
  -v "$(pwd)/data/redis:/data" \
  -p 6379:6379 \
  redis:7-alpine

# Servislerin başlaması için biraz bekle
echo -e "${YELLOW}7. Veritabanı ve Redis'in başlaması bekleniyor (5 sn)...${NC}"
sleep 5

# Bot imajı için basit Dockerfile oluştur
echo -e "${YELLOW}8. Dockerfile oluşturuluyor...${NC}"
cat > Dockerfile.mac << EOF
FROM python:3.10-slim

WORKDIR /app

# Gerekli paketleri yükle
RUN apt-get update && apt-get install -y \
    libpq-dev \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Bağımlılıkları kopyala ve yükle
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Uygulama dosyalarını kopyala
COPY app/ ./app/
COPY alembic.ini ./

# Çalışma dizinleri oluştur
RUN mkdir -p /app/logs /app/sessions

# Ortam değişkenleri
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["python", "-m", "app.main"]
EOF
echo -e "${GREEN}Dockerfile oluşturuldu.${NC}"

# requirements.txt kontrolü
echo -e "${YELLOW}9. Requirements dosyası kontrol ediliyor...${NC}"
if [ ! -f requirements.txt ]; then
  if [ -f requirements.staging.txt ]; then
    cp requirements.staging.txt requirements.txt
    echo -e "${GREEN}requirements.staging.txt kopyalandı.${NC}"
  else
    echo -e "${RED}HATA: requirements.txt dosyası bulunamadı!${NC}"
    exit 1
  fi
fi

# Docker imajını oluştur
echo -e "${YELLOW}10. Docker imajı oluşturuluyor...${NC}"
docker build -f Dockerfile.mac -t telegram-bot-mac .
echo -e "${GREEN}Docker imajı oluşturuldu.${NC}"

# MacOS için özel host kullanarak bot konteynerini başlat
echo -e "${YELLOW}11. Bot konteyneri başlatılıyor (MacOS için özel ayarlarla)...${NC}"
docker run -d \
  --name telegram-bot \
  -p 8000:8000 \
  -e API_ID="${API_ID}" \
  -e API_HASH="${API_HASH}" \
  -e BOT_TOKEN="${BOT_TOKEN}" \
  -e TELEGRAM_API_ID="${API_ID}" \
  -e TELEGRAM_API_HASH="${API_HASH}" \
  -e TELEGRAM_BOT_TOKEN="${BOT_TOKEN}" \
  -e DATABASE_URL="postgresql://${DB_USER:-postgres}:${DB_PASSWORD:-postgres}@host.docker.internal:5432/${DB_NAME:-telegram_bot}" \
  -e REDIS_URL="redis://host.docker.internal:6379/0" \
  -e DB_HOST="host.docker.internal" \
  -e DB_PORT="5432" \
  -e DB_USER="${DB_USER:-postgres}" \
  -e DB_PASSWORD="${DB_PASSWORD:-postgres}" \
  -e DB_NAME="${DB_NAME:-telegram_bot}" \
  -e SESSION_NAME="telegram_session" \
  -e ENV="production" \
  -e DEBUG="true" \
  -e LOG_LEVEL="DEBUG" \
  -v "$(pwd)/logs:/app/logs" \
  -v "$(pwd)/sessions:/app/sessions" \
  telegram-bot-mac

echo -e "${YELLOW}12. Tüm konteynerler kontrol ediliyor...${NC}"
docker ps

echo -e "${YELLOW}13. Bot logları (5 saniye sonra):${NC}"
sleep 5
docker logs telegram-bot

# Özet
echo ""
echo -e "${GREEN}=== KURULUM TAMAMLANDI ===${NC}"
echo -e "${GREEN}API URL     :${NC} http://localhost:8000"
echo -e "${GREEN}Bot Logları :${NC} docker logs telegram-bot"
echo -e "${YELLOW}Konteynerleri Durdurma:${NC} docker stop telegram-bot postgres-db redis-cache"
echo -e "${YELLOW}Hata durumunda:${NC} docker logs telegram-bot"

# Docker Desktop'ta konteyner listesini tazele
echo -e "${YELLOW}Not: Docker Desktop'ta konteynerleri görmek için lütfen uygulamayı yenileyin.${NC}" 