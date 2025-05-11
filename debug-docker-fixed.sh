#!/bin/bash
# Telegram botunun Docker kurulumu için geliştirilmiş debug scripti

# Log fonksiyonları
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[UYARI]${NC} $1"
}

log_error() {
    echo -e "${RED}[HATA]${NC} $1"
}

# Başlangıç mesajı
log_info "Telegram Bot Docker Debug Kurulumu başlatılıyor..."

# Mevcut .env dosyasını kontrol et ve yedekle
if [ -f .env ]; then
    log_info "Mevcut .env dosyası bulundu, yedekleniyor..."
    cp .env .env.bak
    source .env
    log_info ".env dosyasındaki değişkenler yüklendi"
else
    log_warn ".env dosyası bulunamadı, örnek değerler kullanılacak"
    # Örnek değerler - gerçek değerlerle değiştirilmeli
    API_ID="12345678"
    API_HASH="abcdef1234567890abcdef1234567890"
    BOT_TOKEN="1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    DB_USER="botuser"
    DB_PASSWORD="botpass"
    DB_NAME="botdb"
fi

# Önceki konteynerları temizle
log_info "Eski konteynerları temizleme..."
docker stop telegram-bot db-server redis-server 2>/dev/null || true
docker rm telegram-bot db-server redis-server 2>/dev/null || true

# Ağ oluştur
log_info "Docker ağı oluşturuluyor..."
docker network create telegram-net 2>/dev/null || true

# Dizin yapısını oluştur
log_info "Çalışma dizinleri hazırlanıyor..."
mkdir -p runtime/database runtime/logs runtime/sessions
chmod -R 777 runtime

# PostgreSQL konteyneri
log_info "PostgreSQL veritabanı konteyneri başlatılıyor..."
docker run --name db-server \
    --network telegram-net \
    -e POSTGRES_USER=${DB_USER:-botuser} \
    -e POSTGRES_PASSWORD=${DB_PASSWORD:-botpass} \
    -e POSTGRES_DB=${DB_NAME:-botdb} \
    -v "$(pwd)/runtime/database:/var/lib/postgresql/data" \
    -p 5432:5432 \
    -d postgres:14-alpine

# Redis konteyneri
log_info "Redis konteyneri başlatılıyor..."
docker run --name redis-server \
    --network telegram-net \
    -v "$(pwd)/runtime/redis:/data" \
    -p 6379:6379 \
    -d redis:7-alpine

# Servislerin hazır olmasını bekle
log_info "Veritabanı ve cache servislerinin başlaması bekleniyor..."
sleep 10

# Docker imajını oluştur
log_info "Bot imajı oluşturuluyor..."
cat > Dockerfile.debug << EOF
FROM python:3.10-slim

WORKDIR /app

# Sadece gerekli paketleri yükle
RUN apt-get update && apt-get install -y --no-install-recommends \\
    libpq-dev \\
    curl \\
    && apt-get clean \\
    && rm -rf /var/lib/apt/lists/*

# Bağımlılıkları önce kopyala ve yükle (önbellek için)
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Uygulama dosyalarını kopyala
COPY app /app/app
COPY alembic.ini /app/

# Çalışma dizinlerini oluştur
RUN mkdir -p /app/runtime/database /app/runtime/logs /app/runtime/sessions

# Ortam değişkenleri
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# Sağlık kontrolü
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \\
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

CMD ["python", "-m", "app.main"]
EOF

# requirements.txt dosyasını kontrol et
if [ ! -f requirements.txt ]; then
    log_warn "requirements.txt bulunamadı, requirements.staging.txt kullanılacak..."
    if [ -f requirements.staging.txt ]; then
        cp requirements.staging.txt requirements.txt
    else
        log_error "Hiçbir requirements dosyası bulunamadı!"
        exit 1
    fi
fi

# İmajı oluştur
docker build -f Dockerfile.debug -t telegram-bot:debug .

# Ortam değişkenlerini dosyaya yaz (debug için)
log_info "Debug için ortam değişkenleri hazırlanıyor..."
cat > .env.docker << EOF
# Otomatik oluşturulan Docker ortam değişkenleri dosyası
API_ID=${API_ID:-12345678}
API_HASH=${API_HASH:-abcdef1234567890abcdef1234567890}
BOT_TOKEN=${BOT_TOKEN:-1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZ}
TELEGRAM_API_ID=${API_ID:-12345678}
TELEGRAM_API_HASH=${API_HASH:-abcdef1234567890abcdef1234567890}
TELEGRAM_BOT_TOKEN=${BOT_TOKEN:-1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZ}

# Veritabanı bağlantısı
DATABASE_URL=postgresql://${DB_USER:-botuser}:${DB_PASSWORD:-botpass}@db-server:5432/${DB_NAME:-botdb}
DB_HOST=db-server
DB_PORT=5432
DB_USER=${DB_USER:-botuser}
DB_PASSWORD=${DB_PASSWORD:-botpass}
DB_NAME=${DB_NAME:-botdb}

# Redis
REDIS_URL=redis://redis-server:6379/0

# Uygulama ayarları
SESSION_NAME=telegram_session
ENV=development
DEBUG=true
LOG_LEVEL=DEBUG
EOF

# Bot konteynerini başlat
log_info "Telegram bot konteyneri başlatılıyor..."
docker run --name telegram-bot \
    --network telegram-net \
    --env-file .env.docker \
    -v "$(pwd)/runtime:/app/runtime" \
    -v "$(pwd)/app:/app/app" \
    -p 8000:8000 \
    -d telegram-bot:debug

# Konteyner durumunu göster
log_info "Konteyner durumları:"
docker ps -a

# Logları göster
log_info "Bot logları (10 saniye sonra):"
sleep 10
docker logs telegram-bot

log_info "API erişim URL'si: http://localhost:8000"
log_info "Docker kurulumu tamamlandı. Bot çalışmıyorsa logları kontrol edin: docker logs telegram-bot" 