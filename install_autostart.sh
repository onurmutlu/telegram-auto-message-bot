#!/bin/bash
# Telegram botunun sistem açılışında otomatik başlatılması için kurulum scripti

# Renkler tanımla
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Başlık yazdır
echo -e "${BLUE}====================================================${NC}"
echo -e "${BLUE}     TELEGRAM BOT OTOMATİK BAŞLATMA KURULUMU        ${NC}"
echo -e "${BLUE}====================================================${NC}"

# Çalışma dizinini kontrol et
if [ ! -f "./start_auto.sh" ]; then
    echo -e "${RED}HATA: Bu script telegram-bot ana dizininde çalıştırılmalıdır!${NC}"
    echo -e "${RED}Lütfen 'cd /Users/siyahkare/code/telegram-bot' komutunu çalıştırın ve tekrar deneyin.${NC}"
    exit 1
fi

# Tam yolları elde et
BOT_DIR=$(pwd)
START_SCRIPT="$BOT_DIR/start_auto.sh"

echo -e "${BLUE}Bot dizini: $BOT_DIR${NC}"
echo -e "${BLUE}Başlatma scripti: $START_SCRIPT${NC}"

# Launch Agent dosyasını oluştur (macOS için)
PLIST_PATH="$HOME/Library/LaunchAgents/com.telegram.bot.plist"
PLIST_DIR="$HOME/Library/LaunchAgents"

echo -e "${BLUE}Launch Agent dosyası oluşturuluyor: $PLIST_PATH${NC}"

# LaunchAgents dizini var mı kontrol et
if [ ! -d "$PLIST_DIR" ]; then
    echo -e "${YELLOW}LaunchAgents dizini bulunamadı. Oluşturuluyor...${NC}"
    mkdir -p "$PLIST_DIR"
    echo -e "${GREEN}✓ LaunchAgents dizini oluşturuldu.${NC}"
fi

# plist dosyasını oluştur
cat > "$PLIST_PATH" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.telegram.bot</string>
    <key>ProgramArguments</key>
    <array>
        <string>$START_SCRIPT</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
    <key>StandardErrorPath</key>
    <string>$BOT_DIR/logs/launchd_error.log</string>
    <key>StandardOutPath</key>
    <string>$BOT_DIR/logs/launchd_output.log</string>
    <key>WorkingDirectory</key>
    <string>$BOT_DIR</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
</dict>
</plist>
EOF

echo -e "${GREEN}✓ Launch Agent dosyası oluşturuldu.${NC}"

# Log dizinini oluştur
if [ ! -d "$BOT_DIR/logs" ]; then
    echo -e "${YELLOW}Log dizini bulunamadı. Oluşturuluyor...${NC}"
    mkdir -p "$BOT_DIR/logs"
    echo -e "${GREEN}✓ Log dizini oluşturuldu.${NC}"
fi

# Dosya izinlerini ayarla
echo -e "${BLUE}Dosya izinleri ayarlanıyor...${NC}"
chmod 644 "$PLIST_PATH"
echo -e "${GREEN}✓ Dosya izinleri ayarlandı.${NC}"

# Launch Agent'ı yükle
echo -e "${BLUE}Launch Agent yükleniyor...${NC}"
launchctl unload "$PLIST_PATH" 2>/dev/null || true
launchctl load -w "$PLIST_PATH"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Launch Agent başarıyla yüklendi.${NC}"
    echo -e "${BLUE}====================================================${NC}"
    echo -e "${GREEN}KURULUM TAMAMLANDI!${NC}"
    echo -e "${BLUE}Sistem açılışında bot otomatik olarak başlatılacak.${NC}"
    echo -e "${BLUE}Manual başlatmak için:${NC}"
    echo -e "${YELLOW}./start_auto.sh${NC}"
    echo -e "${BLUE}Durdurmak için:${NC}"
    echo -e "${YELLOW}./stop_auto.sh${NC}"
    echo -e "${BLUE}====================================================${NC}"
else
    echo -e "${RED}HATA: Launch Agent yüklenemedi!${NC}"
    echo -e "${YELLOW}Lütfen manuel olarak yüklemeyi deneyin:${NC}"
    echo -e "${YELLOW}launchctl load -w $PLIST_PATH${NC}"
    exit 1
fi

# Hemen başlat
echo -e "${BLUE}Bot şimdi başlatılıyor...${NC}"
"$START_SCRIPT"
