#!/bin/bash
# Telegram Bot Oturum Kurulum Scripti
# Bu betik, mevcut bir Telegram oturumunu sistem için yapılandırır ve botu otomatik başlatır

# Renkler tanımla
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}====================================================${NC}"
echo -e "${GREEN}            TELEGRAM OTURUM KURULUMU              ${NC}"
echo -e "${BLUE}====================================================${NC}"

# Proje kök dizini
PROJECT_DIR=$(pwd)
SESSIONS_DIR="${PROJECT_DIR}/app/sessions"
ENV_FILE="${PROJECT_DIR}/.env"

# Mevcut oturum dosyasını kontrol et
LATEST_SESSION="test_session_1747844123.session"

if [ ! -f "${LATEST_SESSION}" ]; then
    echo -e "${RED}Hata: ${LATEST_SESSION} dosyası bulunamadı!${NC}"
    
    # Mevcut oturum dosyalarını listele
    echo -e "${YELLOW}Mevcut oturum dosyaları:${NC}"
    ls -la *.session
    
    # Kullanıcıdan dosya adı iste
    read -p "Kullanmak istediğiniz oturum dosyasının adını girin: " LATEST_SESSION
    
    if [ ! -f "${LATEST_SESSION}" ]; then
        echo -e "${RED}Hata: ${LATEST_SESSION} dosyası da bulunamadı!${NC}"
        exit 1
    fi
fi

# Oturum adını al (uzantısız)
SESSION_NAME=$(basename "${LATEST_SESSION}" .session)
echo -e "${GREEN}Kullanılacak oturum: ${SESSION_NAME}${NC}"

# Oturum dizinini oluştur
mkdir -p "${SESSIONS_DIR}"

# Oturum dosyasını taşı
echo -e "${BLUE}Oturum dosyası taşınıyor...${NC}"
cp "${LATEST_SESSION}" "${SESSIONS_DIR}/"
echo -e "${GREEN}✓ Oturum dosyası taşındı: ${SESSIONS_DIR}/${LATEST_SESSION}${NC}"

# Doğrulama kodu ve 2FA şifresi
TELEGRAM_CODE="45908"  # Önceki kimlik doğrulamada kullanılan
TELEGRAM_2FA="sk3441#\$"  # Önceki kimlik doğrulamada kullanılan

# .env dosyasını güncelle
echo -e "${BLUE}.env dosyası güncelleniyor...${NC}"

if [ -f "${ENV_FILE}" ]; then
    # SESSION_NAME değerini güncelle
    grep -q "SESSION_NAME=" "${ENV_FILE}" && 
        sed -i '' "s/SESSION_NAME=.*/SESSION_NAME=${SESSION_NAME}/" "${ENV_FILE}" ||
        echo "SESSION_NAME=${SESSION_NAME}" >> "${ENV_FILE}"
    
    # TELEGRAM_AUTH_CODE ve TELEGRAM_2FA_PASSWORD değişkenlerini ekle/güncelle
    grep -q "TELEGRAM_AUTH_CODE=" "${ENV_FILE}" && 
        sed -i '' "s/TELEGRAM_AUTH_CODE=.*/TELEGRAM_AUTH_CODE=${TELEGRAM_CODE}/" "${ENV_FILE}" ||
        echo "TELEGRAM_AUTH_CODE=${TELEGRAM_CODE}" >> "${ENV_FILE}"
    
    grep -q "TELEGRAM_2FA_PASSWORD=" "${ENV_FILE}" && 
        sed -i '' "s/TELEGRAM_2FA_PASSWORD=.*/TELEGRAM_2FA_PASSWORD=${TELEGRAM_2FA}/" "${ENV_FILE}" ||
        echo "TELEGRAM_2FA_PASSWORD=${TELEGRAM_2FA}" >> "${ENV_FILE}"
    
    # Otomatik mesajlaşma özelliğini aktifleştir
    grep -q "ENABLE_AUTO_MESSAGING=" "${ENV_FILE}" && 
        sed -i '' "s/ENABLE_AUTO_MESSAGING=.*/ENABLE_AUTO_MESSAGING=True/" "${ENV_FILE}" ||
        echo "ENABLE_AUTO_MESSAGING=True" >> "${ENV_FILE}"
    
    echo -e "${GREEN}✓ .env dosyası güncellendi${NC}"
else
    # .env dosyası yoksa oluştur
    echo -e "${YELLOW}⚠ .env dosyası bulunamadı, yeni dosya oluşturuluyor...${NC}"
    
    cat > "${ENV_FILE}" << EOF
SESSION_NAME=${SESSION_NAME}
TELEGRAM_AUTH_CODE=${TELEGRAM_CODE}
TELEGRAM_2FA_PASSWORD=${TELEGRAM_2FA}
ENABLE_AUTO_MESSAGING=True
EOF

    echo -e "${GREEN}✓ Yeni .env dosyası oluşturuldu${NC}"
fi

# Ortam değişkenlerini mevcut bash oturumu için ayarla
export SESSION_NAME="${SESSION_NAME}"
export TELEGRAM_AUTH_CODE="${TELEGRAM_CODE}"
export TELEGRAM_2FA_PASSWORD="${TELEGRAM_2FA}"
export ENABLE_AUTO_MESSAGING=True

echo -e "${BLUE}====================================================${NC}"
echo -e "${GREEN}            KURULUM TAMAMLANDI!                   ${NC}"
echo -e "${BLUE}====================================================${NC}"
echo -e "Oturum Adı: ${SESSION_NAME}"
echo -e "Oturum Dosyası: ${SESSIONS_DIR}/${LATEST_SESSION}"
echo -e "${BLUE}====================================================${NC}"

# Bot'u başlatma seçeneği sun
echo -e "Bot'u şimdi başlatmak istiyor musunuz? (e/h)"
read -p "" START_BOT

if [[ "${START_BOT}" =~ ^[Ee]$ ]]; then
    echo -e "${BLUE}Bot başlatılıyor...${NC}"
    python autostart_bot.py
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Bot başarıyla başlatıldı ve çalışıyor!${NC}"
    else
        echo -e "${RED}✗ Bot başlatılırken bir hata oluştu!${NC}"
    fi
else
    echo -e "${BLUE}Bot'u başlatmak için şu komutu kullanabilirsiniz:${NC}"
    echo -e "${YELLOW}python autostart_bot.py${NC}"
fi

echo -e "${BLUE}====================================================${NC}" 