#!/bin/bash

# ============================================================================ #
# Dosya: stop.sh
# Yol: /Users/siyahkare/code/telegram-bot/stop.sh
# İşlev: Telegram botunu ve ilgili servisleri güvenli bir şekilde durdurur
#
# Versiyon: v2.0.0
# ============================================================================ #

# Renk tanımları
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Telegram Bot durduruluyor...${NC}"

# PID dosyası
PID_FILE=".bot_pids"

# PID dosyası var mı kontrol et
if [ ! -f "$PID_FILE" ]; then
    echo -e "${YELLOW}PID dosyası bulunamadı. Bot çalışmıyor olabilir.${NC}"
    exit 0
fi

# PID listesi
pids=$(cat $PID_FILE)

# Hata sayacı
error_count=0

# Her PID için
for pid in $pids; do
    if [ -n "$pid" ]; then
        echo -e "${YELLOW}PID: $pid durduruluyor...${NC}"
        
        # Süreç hala çalışıyor mu kontrol et
        if ps -p $pid > /dev/null 2>&1; then
            # SIGTERM gönder (graceful shutdown)
            kill -15 $pid 2>/dev/null
            
            # 5 saniye bekle
            echo "Bekleniyor..."
            sleep 5
            
            # Hala çalışıyor mu kontrol et
            if ps -p $pid > /dev/null 2>&1; then
                echo -e "${YELLOW}PID: $pid SIGTERM ile durdurulamadı, SIGKILL deneniyor...${NC}"
                # SIGKILL gönder (zorla durdur)
                kill -9 $pid 2>/dev/null
                
                # 2 saniye bekle
                sleep 2
                
                # Son kontrol
                if ps -p $pid > /dev/null 2>&1; then
                    echo -e "${RED}PID: $pid durdurulamadı.${NC}"
                    error_count=$((error_count+1))
                else
                    echo -e "${GREEN}PID: $pid durduruldu.${NC}"
                fi
            else
                echo -e "${GREEN}PID: $pid durduruldu.${NC}"
            fi
        else
            echo -e "${YELLOW}PID: $pid zaten çalışmıyor.${NC}"
        fi
    fi
done

# PID dosyasını temizle
echo "" > $PID_FILE

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