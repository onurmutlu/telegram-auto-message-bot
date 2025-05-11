#!/bin/bash
set -e

echo -e "\033[0;32m[INFO]\033[0m Docker konteynerlerini başlatma scripti..."

# Ortam değişkenlerini ayarla
export TELEGRAM_API_ID=12345678
export TELEGRAM_API_HASH=abcdef1234567890abcdef1234567890
export TELEGRAM_BOT_TOKEN=1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZ

# Geçici ortam değişkenleri dosyası oluştur
echo -e "\033[0;32m[INFO]\033[0m Geçici ortam değişkenleri dosyası oluşturuluyor..."
cat << EOF > .env.temp
# Telegram API bilgileri
TELEGRAM_API_ID=${TELEGRAM_API_ID}
TELEGRAM_API_HASH=${TELEGRAM_API_HASH}
TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}

# Veritabanı
POSTGRES_USER=botuser
POSTGRES_PASSWORD=botpass
POSTGRES_DB=botdb
EOF

# Konteynerleri durdur ve temizle
echo -e "\033[0;32m[INFO]\033[0m Önceki konteynerler durduruluyor..."
docker compose -f docker-compose.staging.yml down 2>/dev/null || true
docker rm -f $(docker ps -a -q -f name=telegram-bot) 2>/dev/null || true

# Önce veritabanı ve redis konteynerlerini başlat
echo -e "\033[0;32m[INFO]\033[0m Veritabanı ve Redis konteynerleri başlatılıyor..."
docker compose -f docker-compose.staging.yml --env-file .env.temp up -d postgres redis

# Birkaç saniye bekle
echo -e "\033[0;32m[INFO]\033[0m Veritabanı ve Redis'in başlaması bekleniyor..."
sleep 10

# Şimdi uygulama konteynerini başlat
echo -e "\033[0;32m[INFO]\033[0m Bot konteyneri başlatılıyor..."
docker compose -f docker-compose.staging.yml --env-file .env.temp up -d app

# Durumu gör
echo -e "\033[0;32m[INFO]\033[0m Konteyner durumları:"
docker ps

# Logları kontrol et
echo -e "\033[0;32m[INFO]\033[0m Bot logları (5 sn sonra):"
sleep 5
docker logs telegram-bot-staging

# Geçici dosyayı temizle
rm .env.temp

echo -e "\033[0;32m[INFO]\033[0m İşlem tamamlandı." 