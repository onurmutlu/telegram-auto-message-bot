#!/bin/bash
# Tek konteynerde PostgreSQL, Redis ve Telegram Bot kurulumu

# Renk kodları
GREEN="\033[0;32m"
YELLOW="\033[0;33m"
RED="\033[0;31m"
NC="\033[0m" # Normal renk

echo -e "${GREEN}=== TEK KONTEYNER TELEGRAM BOT KURULUMU ===${NC}"

# Docker çalışıyor mu?
echo -e "${YELLOW}1. Docker Desktop durumu kontrol ediliyor...${NC}"
if ! docker system info > /dev/null 2>&1; then
  echo -e "${RED}HATA: Docker Desktop çalışmıyor. Lütfen Docker Desktop uygulamasını açın.${NC}"
  exit 1
fi
echo -e "${GREEN}Docker Desktop çalışıyor.${NC}"

# Eski konteyneri temizle
echo -e "${YELLOW}2. Eski konteynerler temizleniyor...${NC}"
docker stop all-in-one-bot 2>/dev/null || true
docker rm all-in-one-bot 2>/dev/null || true
echo -e "${GREEN}Eski konteynerler temizlendi.${NC}"

# Ortam değişkenlerini yükle
echo -e "${YELLOW}3. Ortam değişkenlerini yükleme...${NC}"
if [ -f .env ]; then
  set -a
  source .env
  set +a
  echo -e "${GREEN}Ortam değişkenleri .env dosyasından yüklendi.${NC}"
else
  echo -e "${RED}UYARI: .env dosyası bulunamadı! Devam etmek için gerekli ortam değişkenleri manuel olarak girilmelidir.${NC}"
  read -p "Devam etmek istiyor musunuz? (e/h): " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Ee]$ ]]; then
    echo -e "${RED}İşlem iptal edildi.${NC}"
    exit 1
  fi
  
  # Temel değişkenleri al
  echo -e "${YELLOW}Lütfen gerekli bilgileri girin:${NC}"
  read -p "API_ID: " API_ID
  read -p "API_HASH: " API_HASH
  read -p "BOT_TOKEN: " BOT_TOKEN
fi

# Ortam değişkenlerini göster
echo -e "${YELLOW}Kullanılacak ortam değişkenleri:${NC}"
echo "API_ID        : ${API_ID}"
echo "API_HASH      : ${API_HASH}"
echo "BOT_TOKEN     : ${BOT_TOKEN}"

# Dizinleri hazırla
echo -e "${YELLOW}4. Çalışma dizinleri hazırlanıyor...${NC}"
mkdir -p data logs sessions
chmod -R 777 data logs sessions
echo -e "${GREEN}Dizinler hazırlandı.${NC}"

# Docker imajını oluştur
echo -e "${YELLOW}5. Docker imajı oluşturuluyor... (Bu işlem biraz zaman alabilir)${NC}"
docker build -f Dockerfile.minimal -t all-in-one-bot:latest .
if [ $? -ne 0 ]; then
  echo -e "${RED}HATA: Docker imajı oluşturulamadı!${NC}"
  exit 1
fi
echo -e "${GREEN}Docker imajı başarıyla oluşturuldu: all-in-one-bot:latest${NC}"

# Konteyneri başlat
echo -e "${YELLOW}6. Tüm servisler tek bir konteynerde başlatılıyor...${NC}"
docker run -d \
  --name all-in-one-bot \
  -p 8000:8000 \
  -p 5432:5432 \
  -p 6379:6379 \
  -e API_ID="${API_ID}" \
  -e API_HASH="${API_HASH}" \
  -e BOT_TOKEN="${BOT_TOKEN}" \
  -e TELEGRAM_API_ID="${API_ID}" \
  -e TELEGRAM_API_HASH="${API_HASH}" \
  -e TELEGRAM_BOT_TOKEN="${BOT_TOKEN}" \
  -e SESSION_NAME="telegram_session" \
  -e ENV="production" \
  -e DEBUG="true" \
  -e LOG_LEVEL="DEBUG" \
  -v "$(pwd)/data:/data" \
  -v "$(pwd)/logs:/app/logs" \
  -v "$(pwd)/sessions:/app/sessions" \
  all-in-one-bot:latest

if [ $? -ne 0 ]; then
  echo -e "${RED}HATA: Konteyner başlatılamadı!${NC}"
  exit 1
fi

echo -e "${GREEN}Konteyner başarıyla başlatıldı.${NC}"

# Başlangıcı göster
echo -e "${YELLOW}7. Konteyner Logları (başlangıç):${NC}"
echo -e "${YELLOW}Not: Servislerin başlaması biraz zaman alabilir...${NC}"
sleep 5
docker logs all-in-one-bot

# Özet
echo ""
echo -e "${GREEN}=== TEK KONTEYNER KURULUM TAMAMLANDI ===${NC}"
echo -e "${GREEN}API URL     :${NC} http://localhost:8000"
echo -e "${GREEN}PostgreSQL  :${NC} localhost:5432 (User: postgres, Password: postgres, DB: telegram_bot)"
echo -e "${GREEN}Redis       :${NC} localhost:6379"
echo -e "${GREEN}Konteyner Adı:${NC} all-in-one-bot"
echo -e "${YELLOW}Logları görüntüle  :${NC} docker logs all-in-one-bot"
echo -e "${YELLOW}Konteyneri durdur  :${NC} docker stop all-in-one-bot"
echo -e "${YELLOW}Konteynere bağlan  :${NC} docker exec -it all-in-one-bot bash"
echo -e "${YELLOW}Docker Desktop'ta konteyneri görmek için uygulamayı yenileyin.${NC}" 