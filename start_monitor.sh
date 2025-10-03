#!/bin/bash
# Servis İzleme Aracı
# Bu script, tüm servislerin durumunu gerçek zamanlı olarak izler

# Renkler tanımla
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Başlık yazdır
echo -e "${BLUE}====================================================${NC}"
echo -e "${BLUE}            TELEGRAM BOT SERVİS İZLEME              ${NC}"
echo -e "${BLUE}====================================================${NC}"

# Çalışma dizinini kontrol et
if [ ! -f "./app/main.py" ]; then
    echo -e "${RED}HATA: Bu script telegram-bot ana dizininde çalıştırılmalıdır!${NC}"
    echo -e "${RED}Lütfen doğru dizine geçin ve tekrar deneyin.${NC}"
    exit 1
fi

# Python sanal ortamı kontrol et
if [ ! -d "./.venv" ]; then
    echo -e "${YELLOW}Python sanal ortamı bulunamadı. Oluşturuluyor...${NC}"
    python -m venv .venv
    echo -e "${GREEN}Python sanal ortamı oluşturuldu.${NC}"
fi

# Sanal ortamı etkinleştir
if [ -f "./.venv/bin/activate" ]; then
    echo -e "${BLUE}Python sanal ortamı etkinleştiriliyor...${NC}"
    source ./.venv/bin/activate
else
    echo -e "${RED}Sanal ortam etkinleştirilemedi. Lütfen manuel olarak etkinleştirin.${NC}"
    exit 1
fi

# Gerekli dizinleri oluştur
mkdir -p runtime/logs

# İzleme aracını başlat
echo -e "${GREEN}Servis izleme aracı başlatılıyor...${NC}"
echo -e "${YELLOW}Çıkmak için Ctrl+C tuşlarına basın.${NC}"
python app/cli/service_monitor_cli.py 