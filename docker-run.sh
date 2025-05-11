#!/bin/bash
# Ultra basit Docker kurulum scripti - Sadece minimum gerekli komutlarla
set -e

# Renk tanımları
GREEN="\033[0;32m"
YELLOW="\033[0;33m"
RED="\033[0;31m"
NC="\033[0m"

echo -e "${GREEN}=== TELEGRAM BOT KURULUMU (MİNİMAL) ===${NC}"

# Docker durumunu kontrol et
echo -e "${YELLOW}Docker durumu kontrol ediliyor...${NC}"
docker --version || { echo -e "${RED}Docker yüklü değil veya çalışmıyor!${NC}"; exit 1; }
echo -e "${GREEN}Docker hazır.${NC}"

# .env dosyasını yükle
echo -e "${YELLOW}.env dosyası yükleniyor...${NC}"
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
  echo -e "${GREEN}.env dosyası yüklendi.${NC}"
else
  echo -e "${RED}.env dosyası bulunamadı!${NC}"
  exit 1
fi

# Docker imajını oluştur - ultra basit 
echo -e "${YELLOW}Bot imajı oluşturuluyor...${NC}"
cat > Dockerfile.ultra << EOF
FROM python:3.10-slim

WORKDIR /app

# Sadece gerekli paketleri yükle
RUN apt-get update && apt-get install -y libpq-dev && apt-get clean

# Bağımlılıkları yükle
COPY requirements.txt /app/
RUN pip install -r requirements.txt

# Kod kopyala
COPY app/ /app/app/
COPY alembic.ini /app/

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["python", "-m", "app.main"]
EOF

# requirements.txt kontrolü
if [ ! -f requirements.txt ] && [ -f requirements.staging.txt ]; then
  cp requirements.staging.txt requirements.txt
  echo -e "${GREEN}requirements.staging.txt → requirements.txt olarak kopyalandı.${NC}"
fi

# İmajı oluştur
docker build --progress=plain -f Dockerfile.ultra -t bot-ultra:latest . || { echo -e "${RED}İmaj oluşturulamadı!${NC}"; exit 1; }
echo -e "${GREEN}İmaj başarıyla oluşturuldu.${NC}"

# PostgreSQL başlat
echo -e "${YELLOW}PostgreSQL başlatılıyor...${NC}"
docker run -d --name postgres-db \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=telegram_bot \
  -p 5432:5432 \
  postgres:14-alpine || { echo -e "${RED}PostgreSQL başlatılamadı!${NC}"; exit 1; }
echo -e "${GREEN}PostgreSQL başlatıldı.${NC}"

# Redis başlat
echo -e "${YELLOW}Redis başlatılıyor...${NC}"
docker run -d --name redis-cache \
  -p 6379:6379 \
  redis:7-alpine || { echo -e "${RED}Redis başlatılamadı!${NC}"; exit 1; }
echo -e "${GREEN}Redis başlatıldı.${NC}"

# Servislerin hazır olmasını bekle
echo -e "${YELLOW}Servisler hazırlanıyor (5 sn)...${NC}"
sleep 5

# Bot konteynerini başlat
echo -e "${YELLOW}Bot başlatılıyor...${NC}"
docker run -d --name telegram-bot \
  -p 8000:8000 \
  -e API_ID="${API_ID}" \
  -e API_HASH="${API_HASH}" \
  -e BOT_TOKEN="${BOT_TOKEN}" \
  -e TELEGRAM_API_ID="${API_ID}" \
  -e TELEGRAM_API_HASH="${API_HASH}" \
  -e TELEGRAM_BOT_TOKEN="${BOT_TOKEN}" \
  -e DATABASE_URL="postgresql://postgres:postgres@host.docker.internal:5432/telegram_bot" \
  -e REDIS_URL="redis://host.docker.internal:6379/0" \
  -e DB_HOST="host.docker.internal" \
  -e DB_PORT="5432" \
  -e DB_USER="postgres" \
  -e DB_PASSWORD="postgres" \
  -e DB_NAME="telegram_bot" \
  -e SESSION_NAME="telegram_session" \
  -e ENV="production" \
  -v "$(pwd)/logs:/app/logs" \
  -v "$(pwd)/sessions:/app/sessions" \
  bot-ultra:latest || { echo -e "${RED}Bot başlatılamadı!${NC}"; exit 1; }

echo -e "${GREEN}Bot başlatıldı.${NC}"

# Konteyner durumlarını göster
echo -e "${YELLOW}Çalışan konteynerler:${NC}"
docker ps

# Logları göster
echo -e "${YELLOW}Bot logları:${NC}"
docker logs telegram-bot

echo -e "${GREEN}=== KURULUM TAMAMLANDI ===${NC}"
echo -e "${GREEN}Bot API: http://localhost:8000${NC}"
echo -e "${GREEN}Bot Logları: docker logs telegram-bot${NC}" 