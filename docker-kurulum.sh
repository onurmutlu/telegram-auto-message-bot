#!/bin/bash
# Telegram Bot için basit Docker kurulum scripti

# Renk kodları
GREEN="\033[0;32m"
YELLOW="\033[0;33m"
RED="\033[0;31m"
NC="\033[0m" # Normal renk

echo -e "${GREEN}=== TELEGRAM BOT DOCKER KURULUMU ===${NC}"

# 1. Docker çalışıyor mu kontrol et
echo -e "${YELLOW}[1] Docker'ın çalıştığı kontrol ediliyor...${NC}"
if ! docker info > /dev/null 2>&1; then
  echo -e "${RED}HATA: Docker çalışmıyor. Lütfen Docker Desktop'ı başlatın.${NC}"
  exit 1
fi
echo -e "${GREEN}Docker çalışıyor.${NC}"

# 2. Eski konteynerleri ve ağları temizle
echo -e "${YELLOW}[2] Eski konteynerler ve ağlar temizleniyor...${NC}"
docker stop telegram-bot postgres-db redis-cache 2>/dev/null || true
docker rm telegram-bot postgres-db redis-cache 2>/dev/null || true
docker network rm telegram-network 2>/dev/null || true
echo -e "${GREEN}Temizlik tamamlandı.${NC}"

# 3. Ortam değişkenlerini yükle
echo -e "${YELLOW}[3] .env dosyası yükleniyor...${NC}"
if [ -f .env ]; then
  set -a
  source .env
  set +a
  echo -e "${GREEN}.env dosyası başarıyla yüklendi.${NC}"
else
  echo -e "${RED}.env dosyası bulunamadı. Örnek değerler kullanılacak!${NC}"
  API_ID="12345678"
  API_HASH="abcdef1234567890abcdef1234567890"
  BOT_TOKEN="1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZ"
  DB_USER="postgres"
  DB_PASSWORD="postgres" 
  DB_NAME="telegram_bot"
fi

# Ortam değişkenlerini ekranda göster
echo -e "${YELLOW}Yüklenen ortam değişkenleri:${NC}"
echo "API_ID        : ${API_ID}"
echo "API_HASH      : ${API_HASH}"
echo "BOT_TOKEN     : ${BOT_TOKEN}"
echo "DB_USER       : ${DB_USER:-postgres}"
echo "DB_PASSWORD   : ${DB_PASSWORD:-postgres}"
echo "DB_NAME       : ${DB_NAME:-telegram_bot}"

# 4. Dizinleri oluştur
echo -e "${YELLOW}[4] Dizinler oluşturuluyor...${NC}"
mkdir -p data/postgres data/redis logs sessions
chmod -R 777 data logs sessions
echo -e "${GREEN}Dizinler hazır.${NC}"

# 5. Docker ağını oluştur
echo -e "${YELLOW}[5] Docker ağı oluşturuluyor...${NC}"
if ! docker network inspect telegram-network >/dev/null 2>&1; then
  docker network create telegram-network
  if [ $? -eq 0 ]; then
    echo -e "${GREEN}telegram-network ağı oluşturuldu.${NC}"
  else
    echo -e "${RED}HATA: Docker ağı oluşturulamadı!${NC}"
    # Docker ağı oluşturulamadı, ancak 'host' ağıyla devam edebiliriz
    echo -e "${YELLOW}Host ağı kullanılacak.${NC}"
    USE_HOST_NETWORK=true
  fi
else
  echo -e "${GREEN}telegram-network ağı zaten mevcut.${NC}"
fi

# 6. PostgreSQL konteynerini başlat
echo -e "${YELLOW}[6] PostgreSQL konteyneri başlatılıyor...${NC}"
if [ "$USE_HOST_NETWORK" = true ]; then
  # Host ağı kullan
  POSTGRES_CONTAINER_ID=$(docker run --name postgres-db \
    -e POSTGRES_USER="${DB_USER:-postgres}" \
    -e POSTGRES_PASSWORD="${DB_PASSWORD:-postgres}" \
    -e POSTGRES_DB="${DB_NAME:-telegram_bot}" \
    -v "$(pwd)/data/postgres:/var/lib/postgresql/data" \
    -p 5432:5432 \
    -d postgres:14-alpine)
else
  # telegram-network ağını kullan
  POSTGRES_CONTAINER_ID=$(docker run --name postgres-db \
    --network telegram-network \
    -e POSTGRES_USER="${DB_USER:-postgres}" \
    -e POSTGRES_PASSWORD="${DB_PASSWORD:-postgres}" \
    -e POSTGRES_DB="${DB_NAME:-telegram_bot}" \
    -v "$(pwd)/data/postgres:/var/lib/postgresql/data" \
    -p 5432:5432 \
    -d postgres:14-alpine)
fi

if [ $? -eq 0 ] && [ -n "$POSTGRES_CONTAINER_ID" ]; then
  echo -e "${GREEN}PostgreSQL konteyneri başlatıldı: $POSTGRES_CONTAINER_ID${NC}"
else
  echo -e "${RED}HATA: PostgreSQL konteyneri başlatılamadı!${NC}"
  exit 1
fi

# 7. Redis konteynerini başlat
echo -e "${YELLOW}[7] Redis konteyneri başlatılıyor...${NC}"
if [ "$USE_HOST_NETWORK" = true ]; then
  # Host ağı kullan
  REDIS_CONTAINER_ID=$(docker run --name redis-cache \
    -v "$(pwd)/data/redis:/data" \
    -p 6379:6379 \
    -d redis:7-alpine)
else
  # telegram-network ağını kullan
  REDIS_CONTAINER_ID=$(docker run --name redis-cache \
    --network telegram-network \
    -v "$(pwd)/data/redis:/data" \
    -p 6379:6379 \
    -d redis:7-alpine)
fi

if [ $? -eq 0 ] && [ -n "$REDIS_CONTAINER_ID" ]; then
  echo -e "${GREEN}Redis konteyneri başlatıldı: $REDIS_CONTAINER_ID${NC}"
else
  echo -e "${RED}HATA: Redis konteyneri başlatılamadı!${NC}"
  exit 1
fi

# 8. Servislerin başlamasını bekle
echo -e "${YELLOW}[8] Servislerin hazır olması bekleniyor (10 sn)...${NC}"
sleep 10

# 9. Docker imajını oluşturmak için Dockerfile hazırla
echo -e "${YELLOW}[9] Dockerfile hazırlanıyor...${NC}"
cat > Dockerfile.simple << EOF
FROM python:3.10-slim

WORKDIR /app

# Gerekli paketleri yükle
RUN apt-get update && apt-get install -y --no-install-recommends \\
    libpq-dev \\
    curl \\
    && apt-get clean \\
    && rm -rf /var/lib/apt/lists/*

# requirements dosyasını kopyala ve bağımlılıkları yükle
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Uygulama dosyalarını kopyala
COPY app /app/app
COPY alembic.ini /app/

# Çalışma dizinleri
RUN mkdir -p /app/logs /app/sessions

# Ortam değişkenleri
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["python", "-m", "app.main"]
EOF
echo -e "${GREEN}Dockerfile oluşturuldu.${NC}"

# 10. requirements.txt kontrolü
echo -e "${YELLOW}[10] Requirements dosyası kontrol ediliyor...${NC}"
if [ ! -f requirements.txt ]; then
  if [ -f requirements.staging.txt ]; then
    cp requirements.staging.txt requirements.txt
    echo -e "${GREEN}requirements.staging.txt kopyalandı.${NC}"
  else
    echo -e "${RED}HATA: requirements.txt dosyası bulunamadı!${NC}"
    exit 1
  fi
else
  echo -e "${GREEN}requirements.txt mevcut.${NC}"
fi

# 11. Docker imajını oluştur
echo -e "${YELLOW}[11] Docker imajı oluşturuluyor...${NC}"
docker build -f Dockerfile.simple -t telegram-bot:latest .
if [ $? -ne 0 ]; then
  echo -e "${RED}HATA: Docker imajı oluşturulamadı!${NC}"
  exit 1
fi
echo -e "${GREEN}Docker imajı oluşturuldu.${NC}"

# 12. Bot konteynerini başlat
echo -e "${YELLOW}[12] Bot konteyneri başlatılıyor...${NC}"

# DB_HOST değişkenini ayarla
if [ "$USE_HOST_NETWORK" = true ]; then
  DB_HOST="host.docker.internal"
  REDIS_HOST="host.docker.internal"
else
  DB_HOST="postgres-db"
  REDIS_HOST="redis-cache"
fi

# Docker run komutu
if [ "$USE_HOST_NETWORK" = true ]; then
  # Host ağı kullan
  BOT_CONTAINER_ID=$(docker run --name telegram-bot \
    -e API_ID="${API_ID}" \
    -e API_HASH="${API_HASH}" \
    -e BOT_TOKEN="${BOT_TOKEN}" \
    -e TELEGRAM_API_ID="${API_ID}" \
    -e TELEGRAM_API_HASH="${API_HASH}" \
    -e TELEGRAM_BOT_TOKEN="${BOT_TOKEN}" \
    -e DATABASE_URL="postgresql://${DB_USER:-postgres}:${DB_PASSWORD:-postgres}@${DB_HOST}:5432/${DB_NAME:-telegram_bot}" \
    -e REDIS_URL="redis://${REDIS_HOST}:6379/0" \
    -e DB_HOST="${DB_HOST}" \
    -e DB_PORT="5432" \
    -e DB_USER="${DB_USER:-postgres}" \
    -e DB_PASSWORD="${DB_PASSWORD:-postgres}" \
    -e DB_NAME="${DB_NAME:-telegram_bot}" \
    -e SESSION_NAME="telegram_session" \
    -e ENV="production" \
    -e DEBUG="false" \
    -e LOG_LEVEL="INFO" \
    -v "$(pwd)/logs:/app/logs" \
    -v "$(pwd)/sessions:/app/sessions" \
    -p 8000:8000 \
    -d telegram-bot:latest)
else
  # telegram-network ağını kullan
  BOT_CONTAINER_ID=$(docker run --name telegram-bot \
    --network telegram-network \
    -e API_ID="${API_ID}" \
    -e API_HASH="${API_HASH}" \
    -e BOT_TOKEN="${BOT_TOKEN}" \
    -e TELEGRAM_API_ID="${API_ID}" \
    -e TELEGRAM_API_HASH="${API_HASH}" \
    -e TELEGRAM_BOT_TOKEN="${BOT_TOKEN}" \
    -e DATABASE_URL="postgresql://${DB_USER:-postgres}:${DB_PASSWORD:-postgres}@${DB_HOST}:5432/${DB_NAME:-telegram_bot}" \
    -e REDIS_URL="redis://${REDIS_HOST}:6379/0" \
    -e DB_HOST="${DB_HOST}" \
    -e DB_PORT="5432" \
    -e DB_USER="${DB_USER:-postgres}" \
    -e DB_PASSWORD="${DB_PASSWORD:-postgres}" \
    -e DB_NAME="${DB_NAME:-telegram_bot}" \
    -e SESSION_NAME="telegram_session" \
    -e ENV="production" \
    -e DEBUG="false" \
    -e LOG_LEVEL="INFO" \
    -v "$(pwd)/logs:/app/logs" \
    -v "$(pwd)/sessions:/app/sessions" \
    -p 8000:8000 \
    -d telegram-bot:latest)
fi

if [ $? -eq 0 ] && [ -n "$BOT_CONTAINER_ID" ]; then
  echo -e "${GREEN}Bot konteyneri başlatıldı: $BOT_CONTAINER_ID${NC}"
else
  echo -e "${RED}HATA: Bot konteyneri başlatılamadı!${NC}"
  docker logs telegram-bot 2>&1 || true
  exit 1
fi

# 13. Konteyner durumlarını göster
echo -e "${YELLOW}[13] Konteyner durumları kontrol ediliyor...${NC}"
docker ps
echo ""

# 14. Bot loglarını göster
echo -e "${YELLOW}[14] Bot logları (5 saniye sonra)...${NC}"
sleep 5
docker logs telegram-bot

# 15. Özet
echo ""
echo -e "${GREEN}=== KURULUM TAMAMLANDI ===${NC}"
echo -e "${GREEN}API URL     :${NC} http://localhost:8000"
echo -e "${GREEN}Bot Logları :${NC} docker logs telegram-bot"
echo -e "${YELLOW}Konteynerleri Durdurma:${NC} docker stop telegram-bot postgres-db redis-cache"
echo -e "${YELLOW}Konteynerleri Silme:${NC} docker rm telegram-bot postgres-db redis-cache"
echo -e "${YELLOW}Docker Desktop'ta konteyner durumlarını kontrol edebilirsiniz.${NC}" 