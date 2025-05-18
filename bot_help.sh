#!/bin/bash
# Telegram Bot Yardım Scripti
# Bu script Telegram bot kullanımı hakkında bilgi verir

# Renkler tanımla
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Başlık yazdır
echo -e "${BLUE}====================================================${NC}"
echo -e "${BLUE}            TELEGRAM BOT YARDIM MENÜSÜ              ${NC}"
echo -e "${BLUE}====================================================${NC}"

echo -e "${GREEN}Bu script, Telegram botunuzu yönetmenize yardımcı olacak komutları listeler.${NC}"
echo -e ""

echo -e "${YELLOW}1. BOT BAŞLATMA KOMUTLARI${NC}"
echo -e "   ${BLUE}./start_auto.sh${NC}"
echo -e "   ${GREEN}Botu standart modda başlatır. İnteraktif kimlik doğrulama gerektirebilir.${NC}"
echo -e ""
echo -e "   ${BLUE}./start_auto.sh -c \"DOĞRULAMA_KODU\"${NC}"
echo -e "   ${GREEN}Botu, belirtilen Telegram doğrulama koduyla başlatır.${NC}"
echo -e ""
echo -e "   ${BLUE}./start_auto.sh -c \"DOĞRULAMA_KODU\" -p \"2FA_ŞİFRESİ\"${NC}"
echo -e "   ${GREEN}Botu, doğrulama kodu ve 2FA şifresiyle başlatır.${NC}"
echo -e ""

echo -e "${YELLOW}2. BOT DURDURMA KOMUTU${NC}"
echo -e "   ${BLUE}./stop_auto.sh${NC}"
echo -e "   ${GREEN}Çalışan botu durdurur.${NC}"
echo -e ""

echo -e "${YELLOW}3. KONTROL KOMUTLARI${NC}"
echo -e "   ${BLUE}python simple_bot_check.py${NC}"
echo -e "   ${GREEN}Botun bağlantı durumunu ve erişebildiği grupları listeler.${NC}"
echo -e ""
echo -e "   ${BLUE}python test_telegram_groups.py --only-list${NC}"
echo -e "   ${GREEN}Telegram gruplarını listeler.${NC}"
echo -e ""
echo -e "   ${BLUE}python test_telegram_groups.py --message \"Mesajınız\" --target GRUP_INDEKSI${NC}"
echo -e "   ${GREEN}Belirli bir gruba mesaj gönderir.${NC}"
echo -e ""

echo -e "${YELLOW}4. OTOMATİK BAŞLATMA KURULUMU${NC}"
echo -e "   ${BLUE}./install_autostart.sh${NC}"
echo -e "   ${GREEN}Botu sistem başlangıcında otomatik olarak başlatacak şekilde yapılandırır.${NC}"
echo -e ""

echo -e "${YELLOW}5. SORUN GİDERME${NC}"
echo -e "   ${GREEN}Sorun yaşıyorsanız, lütfen şunları kontrol edin:${NC}"
echo -e "   ${GREEN}- .env dosyasının doğru yapılandırıldığından emin olun${NC}"
echo -e "   ${GREEN}- app/sessions dizininde oturum dosyasının varlığını kontrol edin${NC}"
echo -e "   ${GREEN}- bot_autostart.log dosyasını inceleyerek hata mesajlarını görün${NC}"
echo -e ""

echo -e "${BLUE}====================================================${NC}"
echo -e "${GREEN}Daha fazla bilgi için USAGE.md dosyasını inceleyebilirsiniz.${NC}"
echo -e "${BLUE}====================================================${NC}"
