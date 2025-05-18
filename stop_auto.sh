#!/bin/bash
# Telegram botunu durdurma scripti

# Renkler tanımla
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Başlık yazdır
echo -e "${BLUE}====================================================${NC}"
echo -e "${BLUE}            TELEGRAM BOT DURDURMA                   ${NC}"
echo -e "${BLUE}====================================================${NC}"

# Bot işlemlerini bul
echo -e "${BLUE}Çalışan bot işlemleri aranıyor...${NC}"
BOT_PIDS=$(ps aux | grep "python.*app.main" | grep -v grep | awk '{print $2}')

if [ -z "$BOT_PIDS" ]; then
    echo -e "${YELLOW}Çalışan bot işlemi bulunamadı.${NC}"
else
    # İşlemleri sonlandır
    for PID in $BOT_PIDS; do
        echo -e "${BLUE}Bot işlemi sonlandırılıyor (PID: $PID)...${NC}"
        kill -15 $PID 2>/dev/null || {
            echo -e "${YELLOW}Normal sonlandırma başarısız, zorla sonlandırılıyor...${NC}"
            kill -9 $PID 2>/dev/null || {
                echo -e "${RED}İşlem sonlandırılamadı (PID: $PID)!${NC}"
                continue
            }
        }
        echo -e "${GREEN}✓ Bot işlemi sonlandırıldı (PID: $PID)${NC}"
    done
    
    # Sonlandırma başarılı oldu mu kontrol et
    sleep 2
    REMAINING=$(ps aux | grep "python.*app.main" | grep -v grep | awk '{print $2}')
    
    if [ -z "$REMAINING" ]; then
        echo -e "${GREEN}✓ Tüm bot işlemleri başarıyla sonlandırıldı.${NC}"
    else
        echo -e "${RED}UYARI: Bazı bot işlemleri hala çalışıyor olabilir!${NC}"
        echo -e "${YELLOW}Kalan işlemler: $REMAINING${NC}"
        echo -e "${YELLOW}Manuel olarak sonlandırmak için: kill -9 $REMAINING${NC}"
    fi
fi

# Çıkış mesajı
echo -e "${BLUE}====================================================${NC}"
echo -e "${GREEN}BOT DURDURULDU!${NC}"
echo -e "${BLUE}Yeniden başlatmak için:${NC}"
echo -e "${YELLOW}./start_auto.sh${NC}"
echo -e "${BLUE}====================================================${NC}"
