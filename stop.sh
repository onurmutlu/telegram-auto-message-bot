#!/bin/bash

# ============================================================================ #
# Dosya: stop.sh
# İşlev: Telegram botunu ve event listener'ı durduran yardımcı script.
#
# Kullanım: ./stop.sh
# ============================================================================ #

# Renk tanımlamaları
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # Renk yok

echo -e "${BLUE}Çalışan bot süreçleri kontrol ediliyor...${NC}"

# Kayıtlı PID'leri kontrol et
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$APP_DIR/.bot_pids"

if [ -f "$PID_FILE" ]; then
    echo -e "${YELLOW}PID dosyası bulundu.${NC}"
    SAVED_PIDS=$(cat "$PID_FILE")
    echo -e "Kayıtlı PID'ler: ${YELLOW}$SAVED_PIDS${NC}"
    
    for PID in $SAVED_PIDS; do
        if ps -p $PID > /dev/null; then
            echo -e "PID ${YELLOW}$PID${NC} sonlandırılıyor..."
            kill -9 $PID
            sleep 0.5
        else
            echo -e "PID ${RED}$PID${NC} zaten çalışmıyor."
        fi
    done
    
    # PID dosyasını temizle
    rm -f "$PID_FILE"
    echo -e "${GREEN}PID dosyası temizlendi.${NC}"
else
    # Çalışan süreçleri bul ve sonlandır
    echo -e "${YELLOW}PID dosyası bulunamadı. Süreçler otomatik aranıyor...${NC}"
    PIDS=$(ps aux | grep -E "app\.core\.unified\.main|event_listener|python.*telegram" | grep -v grep | awk '{print $2}')
    
    if [ -n "$PIDS" ]; then
        echo -e "${YELLOW}Çalışan bot süreçleri bulundu. Sonlandırılıyor...${NC}"
        for PID in $PIDS; do
            echo -e "PID ${YELLOW}$PID${NC} sonlandırılıyor..."
            kill -9 $PID
            sleep 0.5
        done
    else
        echo -e "${GREEN}Çalışan bot süreci bulunamadı.${NC}"
    fi
fi

# Son bir kontrol daha yap
REMAINING=$(ps aux | grep -E "app\.core\.unified\.main|event_listener|python.*telegram" | grep -v grep)
if [ -z "$REMAINING" ]; then
    echo -e "${GREEN}Tüm bot süreçleri sonlandırıldı.${NC}"
else
    echo -e "${RED}Bazı süreçler hala çalışıyor olabilir:${NC}"
    echo "$REMAINING"
    echo -e "${YELLOW}Manuel olarak sonlandırmak için:${NC} kill -9 <PID>"
fi 