#!/bin/bash
# Telegram botunu otomatik başlatma scripti
# Bu script gerekli ortamı hazırlar ve bot'u başlatır

# Hata izleme
set -e

# Renkler tanımla
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Başlık yazdır
echo -e "${BLUE}====================================================${NC}"
echo -e "${BLUE}            TELEGRAM BOT OTOMATİK BAŞLATMA          ${NC}"
echo -e "${BLUE}====================================================${NC}"

# Çalışma dizinini kontrol et
if [ ! -f "./app/main.py" ]; then
    echo -e "${RED}HATA: Bu script telegram-bot ana dizininde çalıştırılmalıdır!${NC}"
    echo -e "${RED}Lütfen 'cd /Users/siyahkare/code/telegram-bot' komutunu çalıştırın ve tekrar deneyin.${NC}"
    exit 1
fi

# Python sanal ortamı kontrol et
echo -e "${BLUE}Python sanal ortamı kontrol ediliyor...${NC}"

if [ -d "./.venv" ]; then
    echo -e "${GREEN}✓ Sanal ortam (.venv) bulundu.${NC}"
    
    # Sanal ortamı aktifleştir
    echo -e "${BLUE}Sanal ortam aktifleştiriliyor...${NC}"
    source ./.venv/bin/activate
    
    # Python sürümünü kontrol et
    PYTHON_VERSION=$(python -c "import sys; print('.'.join(map(str, sys.version_info[:3])))")
    echo -e "${GREEN}✓ Python sürümü: ${PYTHON_VERSION}${NC}"
    
    # Gerekli paketleri kontrol et
    echo -e "${BLUE}Gerekli paketler kontrol ediliyor...${NC}"
    python -c "import telethon, fastapi, sqlalchemy, pydantic, sqlmodel" 2>/dev/null || {
        echo -e "${YELLOW}⚠ Bazı gerekli paketler eksik. Paketler yükleniyor...${NC}"
        pip install -r requirements.txt
    }
    echo -e "${GREEN}✓ Gerekli Python paketleri yüklü.${NC}"
else
    echo -e "${YELLOW}⚠ Sanal ortam (.venv) bulunamadı. Oluşturuluyor...${NC}"
    
    # Python varlığını kontrol et
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}HATA: Python3 bulunamadı. Lütfen Python 3.7 veya üstünü yükleyin.${NC}"
        exit 1
    fi
    
    # Sanal ortam oluştur
    python3 -m venv .venv
    
    # Sanal ortamı aktifleştir
    source ./.venv/bin/activate
    
    # pip güncellemesi
    pip install --upgrade pip
    
    # Gerekli paketleri yükle
    echo -e "${BLUE}Gerekli paketler yükleniyor...${NC}"
    pip install -r requirements.txt
    
    echo -e "${GREEN}✓ Sanal ortam oluşturuldu ve paketler yüklendi.${NC}"
fi

# Oturum dizinini kontrol et
echo -e "${BLUE}Oturum dizini kontrol ediliyor...${NC}"
if [ ! -d "./app/sessions" ]; then
    echo -e "${YELLOW}⚠ Oturum dizini bulunamadı. Oluşturuluyor...${NC}"
    mkdir -p ./app/sessions
    echo -e "${GREEN}✓ Oturum dizini oluşturuldu.${NC}"
else  
    echo -e "${GREEN}✓ Oturum dizini mevcut.${NC}"
fi

# .env dosyasını kontrol et
echo -e "${BLUE}.env dosyası kontrol ediliyor...${NC}"
if [ ! -f "./.env" ]; then
    echo -e "${YELLOW}⚠ .env dosyası bulunamadı. Örnek dosyadan kopyalanıyor...${NC}"
    
    if [ -f "./example.env" ]; then
        cp ./example.env ./.env
        echo -e "${GREEN}✓ .env dosyası oluşturuldu. Lütfen içeriğini kontrol edin.${NC}"
    else
        echo -e "${RED}HATA: example.env dosyası bulunamadı!${NC}"
        echo -e "${YELLOW}Basit bir .env dosyası oluşturuluyor...${NC}"
        echo "API_ID=23692263" > ./.env
        echo "API_HASH=ff5d6053b266f78d1293f9343f40e77e" >> ./.env
        echo "PHONE=+905382617727" >> ./.env
        echo "SESSION_NAME=telegram_session" >> ./.env
        echo -e "${GREEN}✓ Basit .env dosyası oluşturuldu.${NC}"
    fi
else
    echo -e "${GREEN}✓ .env dosyası mevcut.${NC}"
fi

# Otomatik mesajlaşma özelliği (her başlangıçta aktif olacak)
export ENABLE_AUTO_MESSAGING=True
export AUTO_MESSAGING_INTERVAL_MIN=180  # 3 dakika
export AUTO_MESSAGING_INTERVAL_MAX=420  # 7 dakika

# Doğrulama kodu ve 2FA için parametreleri kontrol et
AUTH_CODE=""
PASSWORD=""

# Parametreleri oku
while getopts ":c:p:" opt; do
  case $opt in
    c)
      AUTH_CODE="$OPTARG"
      echo -e "${GREEN}Doğrulama kodu verildi: ${AUTH_CODE}${NC}"
      ;;
    p)
      PASSWORD="$OPTARG"
      echo -e "${GREEN}2FA şifresi verildi${NC}"
      ;;
    \?)
      echo -e "${YELLOW}Geçersiz seçenek: -$OPTARG${NC}"
      ;;
    :)
      echo -e "${YELLOW}Seçenek -$OPTARG bir argüman gerektiriyor.${NC}"
      ;;
  esac
done

# Doğrulama kodunu ortam değişkeni olarak ayarla
if [ -n "$AUTH_CODE" ]; then
  export TELEGRAM_AUTH_CODE="$AUTH_CODE"
  echo -e "${BLUE}Doğrulama kodu ortam değişkeni olarak ayarlandı.${NC}"
  
  # Ayrıca dosyaya yazarak interaktif olmayan ortamlarda kullanım için hazırlık yap
  echo "$AUTH_CODE" > ./.telegram_auth_code
  chmod 600 ./.telegram_auth_code
fi

# 2FA şifresini ortam değişkeni olarak ayarla
if [ -n "$PASSWORD" ]; then
  export TELEGRAM_2FA_PASSWORD="$PASSWORD"
  echo -e "${BLUE}2FA şifresi ortam değişkeni olarak ayarlandı.${NC}"
  
  # Ayrıca dosyaya yazarak interaktif olmayan ortamlarda kullanım için hazırlık yap
  echo "$PASSWORD" > ./.telegram_2fa_password
  chmod 600 ./.telegram_2fa_password
fi

# Otomatik mesajlaşmayı aktifleştirme mesajı
echo -e "${BLUE}====================================================${NC}"
echo -e "${GREEN}Otomatik mesajlaşma özelliği etkinleştirildi!${NC}"
echo -e "${BLUE}Bot başlatıldığında otomatik mesajlar aktif olacak${NC}"
echo -e "${BLUE}====================================================${NC}"

# Botu başlat
python autostart_bot.py

# İşlem başarılı mı kontrol et
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Bot başarıyla başlatıldı ve çalışıyor.${NC}"
    echo -e "${BLUE}====================================================${NC}"
    echo -e "${GREEN}BOT HAZIR ve ÇALIŞIYOR!${NC}"
    echo -e "${GREEN}Otomatik mesajlaşma servisi aktif!${NC}"
    echo -e "${BLUE}====================================================${NC}"
else
    echo -e "${RED}HATA: Bot başlatılamadı!${NC}"
    echo -e "${YELLOW}Detaylar için 'bot_autostart.log' dosyasını kontrol edin.${NC}"
    exit 1
fi

# Çıkış mesajı
echo -e "${BLUE}Bot servis olarak arkaplanda çalışıyor. İzlemek için:${NC}"
echo -e "${YELLOW}tail -f bot_autostart.log${NC}"
echo -e "${BLUE}Durdurmak için:${NC}"
echo -e "${YELLOW}./stop.sh${NC}"

# Servis izleme özelliğini etkinleştir
export ENABLE_SERVICE_MONITOR=True
export AUTO_RESTART_SERVICES=True
