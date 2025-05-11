#!/bin/bash
set -e  # Herhangi bir komut hata verirse script duracak

# Renkli çıktı için renk kodları
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Fonksiyonlar
function log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

function log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

function log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Telegram API bilgilerini ayarla
log_info "Ortam değişkenleri ayarlanıyor..."
# Bu değerler örnek amaçlıdır, gerçek değerlerle değiştirilmelidir
export TELEGRAM_API_ID=12345678
export TELEGRAM_API_HASH=abcdef1234567890abcdef1234567890
export TELEGRAM_BOT_TOKEN=1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZ

# .env dosyası varsa kullan
if [ -f .env ]; then
    log_info ".env dosyası bulundu, içeri aktarılıyor..."
    export $(grep -v '^#' .env | xargs)
elif [ -f example.env ]; then
    log_warn ".env dosyası bulunamadı, example.env dosyası kullanılıyor."
    export $(grep -v '^#' example.env | xargs)
else
    log_warn "Hiçbir .env dosyası bulunamadı, varsayılan değerler kullanılacak."
fi

# Kapsamlı test coverage için daha fazla unit test eklendi
log_info "Unit testleri çalıştırılıyor..."
python -m pytest tests/test_message_service.py tests/test_user_service.py tests/test_analytics_service.py tests/test_metrics_service.py -v

# Tüm container'ları durdur ve temizle
log_info "Mevcut Docker containerları temizleniyor..."
docker compose -f docker-compose.staging.yml down || log_warn "Docker compose down başarısız oldu, devam ediliyor..."
docker rm -f $(docker ps -a -q -f name=telegram-bot) 2>/dev/null || log_warn "Önceki konteynerler temizlenemedi, devam ediliyor..."

# Docker imajını yeniden oluştur
log_info "Docker imajı oluşturuluyor..."
docker build -f Dockerfile.staging -t telegram-bot:staging .

# Geçici ortam değişkenleri dosyası oluştur
log_info "Ortam değişkenleri dosyası oluşturuluyor..."
cat << EOF > .env.staging.temp
# Telegram API bilgileri - Otomatik oluşturuldu
TELEGRAM_API_ID=${TELEGRAM_API_ID}
TELEGRAM_API_HASH=${TELEGRAM_API_HASH}
TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}

# Veritabanı
POSTGRES_USER=botuser
POSTGRES_PASSWORD=botpass
POSTGRES_DB=botdb
DATABASE_URL=postgresql://botuser:botpass@postgres:5432/botdb

# Redis
REDIS_URL=redis://redis:6379/0

# Uygulama ayarları
PORT=8000
LOG_LEVEL=INFO
SESSION_NAME=telegram_session
ENV=staging
DEBUG=false
EOF

# Docker compose ile çalıştır (env dosyasını kullanarak)
log_info "Docker Compose ile Staging ortamı başlatılıyor..."
docker compose -f docker-compose.staging.yml --env-file .env.staging.temp up -d

# Geçici env dosyasını temizle
rm .env.staging.temp

# Logları göster
log_info "Servis durumları kontrol ediliyor..."
docker ps

# Konteyner durumunu kontrol et
CONTAINER_STATUS=$(docker inspect -f '{{.State.Status}}' telegram-bot-staging 2>/dev/null || echo "not_found")

if [ "$CONTAINER_STATUS" == "running" ]; then
    log_info "Telegram bot konteyneri başarıyla çalışıyor!"
    log_info "Bot logları:"
    sleep 5
    docker logs telegram-bot-staging
else
    log_error "Bot konteyneri çalışmıyor. Hata ayıklama bilgileri:"
    docker ps -a
    log_error "Bot konteyneri log çıktısı:"
    docker logs telegram-bot-staging 2>/dev/null || echo "Bot konteyneri bulunamadı"
fi

log_info "Deployment tamamlandı. Ortamı kontrol etmek için: http://localhost:8000" 