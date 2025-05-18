#!/bin/bash

# ============================================================================ #
# Dosya: start.sh
# Yol: /Users/siyahkare/code/telegram-bot/start.sh
# İşlev: Telegram botunu başlatır ve durumunu izler
#
# Versiyon: v2.0.0
# ============================================================================ #

set -e

# Renk tanımları
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Telegram Bot başlatılıyor...${NC}"

# PID dosyası
PID_FILE=".bot_pids"

# Mevcut PID'leri temizle
echo "" > $PID_FILE

# Veritabanı bağlantısını kontrol et
echo -e "${YELLOW}Veritabanı bağlantısı kontrol ediliyor...${NC}"

# PostgreSQL'e bağlantı kontrolü
max_attempts=30
attempt=0
DB_HOST=${DB_HOST:-localhost}
DB_PORT=${DB_PORT:-5432}
DB_USER=${DB_USER:-postgres}
DB_NAME=${DB_NAME:-telegram_bot}

while [ $attempt -lt $max_attempts ]
do
    attempt=$((attempt+1))
    echo -e "${YELLOW}Veritabanı bağlantısı deneniyor (${attempt}/${max_attempts})...${NC}"
    
    if pg_isready -h $DB_HOST -p $DB_PORT -U $DB_USER; then
        echo -e "${GREEN}Veritabanı bağlantısı başarılı!${NC}"
        break
    fi
    
    if [ $attempt -eq $max_attempts ]; then
        echo -e "${RED}Veritabanı bağlantısı kurulamadı, uygulama başlatılamıyor.${NC}"
        exit 1
    fi
    
    sleep 2
done

# Veritabanı kontrol ve oluşturma
echo -e "${YELLOW}Veritabanı şeması kontrol ediliyor...${NC}"
python -m app.scripts.setup_database

# Şablonları yükle
echo -e "${YELLOW}Mesaj şablonları kontrol ediliyor...${NC}"
python -m app.scripts.load_templates

# Redis bağlantısını kontrol et (eğer etkinleştirilmişse)
if [ "$REDIS_ENABLED" = "true" ]; then
    echo -e "${YELLOW}Redis bağlantısı kontrol ediliyor...${NC}"
    
    REDIS_HOST=${REDIS_HOST:-localhost}
    REDIS_PORT=${REDIS_PORT:-6379}
    
    redis-cli -h $REDIS_HOST -p $REDIS_PORT ping > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Redis bağlantısı başarılı!${NC}"
    else
        echo -e "${RED}Redis bağlantısı kurulamadı, uygulama devam ediyor ama Redis özellikleri çalışmayabilir.${NC}"
    fi
fi

# Oturum dosyasını kontrol et
SESSION_NAME=${SESSION_NAME:-telegram_session}
SESSION_FILE="${SESSION_NAME}.session"

if [ ! -f "$SESSION_FILE" ]; then
    if [ -f "session/$SESSION_FILE" ]; then
        echo -e "${YELLOW}Oturum dosyası session/ dizininde bulundu, kök dizine taşınıyor...${NC}"
        cp "session/$SESSION_FILE" .
    else
        echo -e "${YELLOW}Oturum dosyası bulunamadı, login işlemi gerekebilir.${NC}"
    fi
fi

# Environment kontrolü
ENV=${ENV:-development}
if [ "$ENV" = "production" ]; then
    echo -e "${GREEN}Uygulama production modunda başlatılıyor...${NC}"
else
    echo -e "${YELLOW}Uygulama $ENV modunda başlatılıyor...${NC}"
fi

# Ana uygulamayı başlat
echo -e "${BLUE}Bot başlatılıyor...${NC}"

# PID'i kaydet
echo $$ >> $PID_FILE

# API etkinse, ayrı bir süreçte API'yi başlat
if [ "$ENABLE_API" = "true" ]; then
    echo -e "${YELLOW}API etkinleştirildi, ayrı bir süreçte başlatılıyor...${NC}"
    python -m app.api.main &
    API_PID=$!
    echo $API_PID >> $PID_FILE
    echo -e "${GREEN}API başlatıldı (PID: $API_PID)${NC}"
fi

# Botu başlat
exec python -m app.main 