#!/bin/bash

# Renkler tanımla
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}====================================================${NC}"
echo -e "${GREEN}            TELEGRAM BOT DÜZELTME ARACI              ${NC}"
echo -e "${BLUE}====================================================${NC}"

# Veritabanı bağlantısının atlanmasını sağla
echo -e "${YELLOW}PostgreSQL veritabanı bağlantısı devre dışı bırakılıyor...${NC}"
if [ -f ".env" ]; then
    # DB_SKIP değişkenini ekle/güncelle
    grep -q "DB_SKIP=" ".env" && 
        sed -i '' "s/DB_SKIP=.*/DB_SKIP=True/" ".env" ||
        echo "DB_SKIP=True" >> ".env"
    
    # Doğrulama kodu değişkenini ekle/güncelle
    grep -q "TELEGRAM_CODE=" ".env" && 
        sed -i '' "s/TELEGRAM_CODE=.*/TELEGRAM_CODE=45908/" ".env" ||
        echo "TELEGRAM_CODE=45908" >> ".env"
    
    # 2FA şifre değişkenini ekle/güncelle
    grep -q "TELEGRAM_2FA_PASSWORD=" ".env" && 
        sed -i '' "s/TELEGRAM_2FA_PASSWORD=.*/TELEGRAM_2FA_PASSWORD=sk3441#\$/" ".env" ||
        echo "TELEGRAM_2FA_PASSWORD=sk3441#\$" >> ".env"
    
    echo -e "${GREEN}✓ .env dosyası güncellendi${NC}"
else
    echo -e "${RED}Hata: .env dosyası bulunamadı!${NC}"
    exit 1
fi

# app/db/session.py dosyasını düzelt - veritabanı bağlantısını opsiyonel yap
echo -e "${YELLOW}Veritabanı bağlantı kodunu düzeltiyorum...${NC}"
sed -i '' 's/if not DATABASE_URL.startswith/if os.getenv("DB_SKIP") == "True":\n    logger.warning("Veritabanı bağlantısı DB_SKIP=True nedeniyle atlanıyor!")\n    # Dummy engine oluştur\n    engine = create_engine("sqlite:\\/\\/\/:memory:")\n    logger.info("Bellek tabanlı geçici SQLite veritabanı kullanılıyor")\nelse:\n    if not DATABASE_URL.startswith/g' app/db/session.py

# Ortam değişkenlerini ayarla
export DB_SKIP=True
export TELEGRAM_CODE=45908
export TELEGRAM_2FA_PASSWORD="sk3441#$"

echo -e "${BLUE}====================================================${NC}"
echo -e "${GREEN}            DÜZELTME TAMAMLANDI!                   ${NC}"
echo -e "${BLUE}====================================================${NC}"

# Bot'u başlat
echo -e "${YELLOW}Bot başlatılıyor...${NC}"
python autostart_bot.py 