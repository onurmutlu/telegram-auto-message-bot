#!/bin/bash

# ============================================================================ #
# Dosya: stop.sh
# Yol: /Users/siyahkare/code/telegram-bot/stop.sh
# İşlev: Telegram botunu ve ilgili servisleri güvenli bir şekilde durdurur
#
# Versiyon: v2.0.0
# ============================================================================ #

# Renkler tanımla
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}====================================================${NC}"
echo -e "${GREEN}            TELEGRAM BOT DURDURULUYOR              ${NC}"
echo -e "${BLUE}====================================================${NC}"

# Bot PID'sini kontrol et
if [ -f ".bot_pid" ]; then
    PID=$(cat .bot_pid)
    if ps -p $PID > /dev/null; then
        echo -e "${YELLOW}Bot süreci durduruluyor (PID: $PID)...${NC}"
        kill $PID
        sleep 2
        
        # Süreç hala çalışıyorsa zorla kapat
        if ps -p $PID > /dev/null; then
            echo -e "${YELLOW}Bot zorla kapatılıyor...${NC}"
            kill -9 $PID
            sleep 1
        fi
        
        echo -e "${GREEN}✓ Bot durduruldu${NC}"
    else
        echo -e "${YELLOW}Bot süreci zaten çalışmıyor (PID: $PID)${NC}"
    fi
    
    # PID dosyasını temizle
    rm .bot_pid
else
    # PID dosyası yoksa, Python süreçlerini ara
    echo -e "${YELLOW}Bot süreçleri aranıyor...${NC}"
    PIDS=$(ps aux | grep "[p]ython.*autostart_bot.py" | awk '{print $2}')
    
    if [ -n "$PIDS" ]; then
        echo -e "${YELLOW}Bulunan bot süreçleri:${NC}"
        for PID in $PIDS; do
            echo -e "${BLUE}Durduruluyor: PID $PID${NC}"
            kill $PID
            sleep 1
            # Süreç hala çalışıyorsa zorla kapat
            if ps -p $PID > /dev/null; then
                echo -e "${YELLOW}Süreç zorla kapatılıyor: PID $PID${NC}"
                kill -9 $PID
            fi
        done
        echo -e "${GREEN}✓ Tüm bot süreçleri durduruldu${NC}"
    else
        echo -e "${YELLOW}Çalışan bot süreci bulunamadı${NC}"
    fi
fi

echo -e "${BLUE}====================================================${NC}"

# Docker altında çalışıyorsa, Python süreçlerini de temizle
if [ -f "/.dockerenv" ]; then
    echo -e "${YELLOW}Docker ortamında Python süreçleri kontrol ediliyor...${NC}"
    python_procs=$(pgrep -f "python -m app")
    
    if [ -n "$python_procs" ]; then
        echo -e "${YELLOW}Python süreçleri bulundu, durduruluyor...${NC}"
        for proc in $python_procs; do
            echo -e "${YELLOW}Python PID: $proc durduruluyor...${NC}"
            kill -15 $proc 2>/dev/null
            sleep 2
            # Hala çalışıyor mu kontrol et
            if ps -p $proc > /dev/null 2>&1; then
                kill -9 $proc 2>/dev/null
            fi
        done
    fi
fi

# Sonuç
if [ $error_count -eq 0 ]; then
    echo -e "${GREEN}Telegram Bot ve ilgili servisler başarıyla durduruldu.${NC}"
    exit 0
else
    echo -e "${RED}$error_count süreç durdurulamadı, manuel müdahale gerekebilir.${NC}"
    exit 1
fi 