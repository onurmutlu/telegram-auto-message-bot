#!/bin/bash

# ============================================================================ #
# Dosya: start.sh
# İşlev: Telegram botunu ve event listener'ı başlatan yardımcı script.
#
# Kullanım: ./start.sh [--debug]
# ============================================================================ #

# Renk tanımlamaları
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # Renk yok

# Debug parametresi kontrolü
DEBUG_MODE=0
if [ "$1" == "--debug" ]; then
    DEBUG_MODE=1
    echo -e "${YELLOW}Debug modu aktif${NC}"
fi

# Çalışan uygulamaları bulup sonlandırma
echo -e "${BLUE}Çalışan bot süreçleri kontrol ediliyor...${NC}"
PIDS=$(ps aux | grep -E "app\.core\.unified\.main|event_listener|python.*telegram" | grep -v grep | awk '{print $2}')

if [ -n "$PIDS" ]; then
    echo -e "${YELLOW}Çalışan bot süreçleri bulundu. Sonlandırılıyor...${NC}"
    for PID in $PIDS; do
        echo "PID $PID sonlandırılıyor..."
        kill -9 $PID 2>/dev/null
    done
    echo -e "${GREEN}Tüm süreçler sonlandırıldı.${NC}"
else
    echo -e "${GREEN}Çalışan bot süreci bulunamadı.${NC}"
fi

# PID dosyasını temizle (varsa)
if [ -f ".bot_pids" ]; then
    rm -f .bot_pids
    echo -e "${BLUE}PID dosyası temizlendi.${NC}"
fi

# Oturum kontrol ve otomatik yapılandırma
check_telegram_session() {
    echo -e "${BLUE}Telegram oturumu kontrol ediliyor...${NC}"
    
    # settings tablosunda session_string var mı kontrol et
    SESSION_CHECK=$(python3 -c "
import psycopg2
import os
from dotenv import load_dotenv
load_dotenv()

try:
    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=os.getenv('POSTGRES_PORT', '5432'),
        dbname=os.getenv('POSTGRES_DB', 'telegram_bot'),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', '')
    )
    cursor = conn.cursor()
    cursor.execute(\"SELECT value FROM settings WHERE key = 'session_string'\")
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    print('1' if result else '0')
except Exception as e:
    print('0')
")

    if [ "$SESSION_CHECK" == "1" ]; then
        echo -e "${GREEN}Telegram oturumu bulundu. Bot başlatılabilir.${NC}"
        return 0
    else
        echo -e "${YELLOW}Telegram oturumu bulunamadı. Oturum açma gerekiyor.${NC}"
        
        # telegram_login.py çalıştır
        echo -e "${BLUE}Oturum açma işlemi başlatılıyor...${NC}"
        python telegram_login.py
        
        # Oturum açma başarılı mı kontrol et
        SESSION_CHECK=$(python3 -c "
import psycopg2
import os
from dotenv import load_dotenv
load_dotenv()

try:
    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=os.getenv('POSTGRES_PORT', '5432'),
        dbname=os.getenv('POSTGRES_DB', 'telegram_bot'),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', '')
    )
    cursor = conn.cursor()
    cursor.execute(\"SELECT value FROM settings WHERE key = 'session_string'\")
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    print('1' if result else '0')
except Exception as e:
    print('0')
")

        if [ "$SESSION_CHECK" == "1" ]; then
            echo -e "${GREEN}Telegram oturumu başarıyla oluşturuldu. Bot başlatılabilir.${NC}"
            return 0
        else
            echo -e "${RED}Telegram oturumu açılamadı. Bot başlatılamıyor.${NC}"
            return 1
        fi
    fi
}

# Veritabanı bağlantısını temizleme
echo -e "${BLUE}Veritabanı bağlantısı temizleniyor...${NC}"
if [ -f "fix_database.py" ]; then
    python fix_database.py
else
    echo -e "${YELLOW}fix_database.py bulunamadı, veritabanı temizleme atlanıyor.${NC}"
fi

# Veritabanı analitik tablolarını oluşturma/kontrol etme
echo -e "Veritabanı analitik tablolarını oluşturma/kontrol etme..."
if [ -f "app/db/migrations/create_analytics_tables.py" ]; then
    python app/db/migrations/create_analytics_tables.py
else
    echo -e "${YELLOW}create_analytics_tables.py bulunamadı, tablo oluşturma atlanıyor.${NC}"
fi

# Telegram oturumunu kontrol et
check_telegram_session
TELEGRAM_OK=$?

if [ $TELEGRAM_OK -eq 1 ]; then
    echo -e "${RED}Bot başlatılamıyor: Telegram oturumu bulunamadı.${NC}"
    echo -e "Lütfen 'python telegram_login.py' komutu ile oturum açın."
    exit 1
fi

# Ana uygulama başlatılıyor
echo -e "${BLUE}Ana uygulama başlatılıyor...${NC}"
if [ $DEBUG_MODE -eq 1 ]; then
    python -m app.core.unified.main --debug > runtime/logs/app.log 2>&1 &
else
    python -m app.core.unified.main > runtime/logs/app.log 2>&1 &
fi
MAIN_PID=$!
echo $MAIN_PID >> .bot_pids
echo -e "${GREEN}Main process başlatıldı (PID: $MAIN_PID)${NC}"

# Event listener başlatılıyor 
echo -e "${BLUE}Event listener başlatılıyor...${NC}"
python event_listener.py > runtime/logs/event_listener.log 2>&1 &
LISTENER_PID=$!
echo $LISTENER_PID >> .bot_pids
echo -e "${GREEN}Event listener başlatıldı (PID: $LISTENER_PID)${NC}"

# Çalışan süreçleri göster
echo -e "${BLUE}Çalışan bot süreçleri:${NC}"
ps aux | grep -E "app\.core\.unified\.main|event_listener|python.*telegram" | grep -v grep

# Başarı mesajı
echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}Bot başarıyla başlatıldı!${NC}"
echo -e "${GREEN}================================${NC}"
echo -e "Bot'u durdurmak için ${YELLOW}./stop.sh${NC} komutunu kullanın" 