#!/bin/bash
# Docker Compose ile Telegram botunu başlatma scripti

# Renkli çıktı için renk kodları
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Fonksiyonlar
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
log_info "Docker Compose ile Telegram Bot başlatılıyor..."

# Çalışma dizinleri oluştur
log_info "Çalışma dizinleri hazırlanıyor..."
mkdir -p runtime/database runtime/logs runtime/sessions runtime/redis
chmod -R 777 runtime

# Mevcut .env dosyasını kontrol et
if [ -f .env ]; then
    log_info "Mevcut .env dosyası bulundu, ortam değişkenleri yükleniyor..."
    source .env
else
    log_warn ".env dosyası bulunamadı, örnek değerler kullanılacak."
    # Örnek değerler
    API_ID="12345678"
    API_HASH="abcdef1234567890abcdef1234567890"
    BOT_TOKEN="1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    DB_USER="botuser"
    DB_PASSWORD="botpass"
    DB_NAME="botdb"
fi

# Dockerfile.debug oluştur (eğer mevcut değilse)
if [ ! -f Dockerfile.debug ]; then
    log_info "Dockerfile.debug oluşturuluyor..."
    cat > Dockerfile.debug << EOF
FROM python:3.10-slim

WORKDIR /app

# Sadece gerekli paketleri yükle
RUN apt-get update && apt-get install -y --no-install-recommends \\
    libpq-dev \\
    curl \\
    && apt-get clean \\
    && rm -rf /var/lib/apt/lists/*

# Bağımlılıkları önce kopyala ve yükle
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Uygulama dosyalarını kopyala
COPY app /app/app
COPY alembic.ini /app/

# Çalışma dizinleri
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
fi

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

# Docker için .env dosyası oluştur
log_info "Docker için ortam değişkenleri dosyası oluşturuluyor..."
cat > .env.docker << EOF
# Otomatik oluşturulan Docker ortam değişkenleri dosyası
API_ID=${API_ID:-12345678}
API_HASH=${API_HASH:-abcdef1234567890abcdef1234567890}
BOT_TOKEN=${BOT_TOKEN:-1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZ}
TELEGRAM_API_ID=${API_ID:-12345678}
TELEGRAM_API_HASH=${API_HASH:-abcdef1234567890abcdef1234567890}
TELEGRAM_BOT_TOKEN=${BOT_TOKEN:-1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZ}

# Veritabanı bağlantısı
DATABASE_URL=postgresql://${DB_USER:-botuser}:${DB_PASSWORD:-botpass}@db:5432/${DB_NAME:-botdb}
DB_HOST=db
DB_PORT=5432
DB_USER=${DB_USER:-botuser}
DB_PASSWORD=${DB_PASSWORD:-botpass}
DB_NAME=${DB_NAME:-botdb}

# Redis
REDIS_URL=redis://redis:6379/0

# Uygulama ayarları
SESSION_NAME=${SESSION_NAME:-telegram_session}
ENV=${ENV:-development}
DEBUG=${DEBUG:-true}
LOG_LEVEL=${LOG_LEVEL:-DEBUG}
EOF

# Önceki konteynerları durdur ve temizle
log_info "Önceki konteynerları durdurma ve temizleme..."
docker-compose -f docker-compose.simple.yml down 2>/dev/null || true

# Docker Compose ile başlat
log_info "Docker Compose ile servisleri başlatma..."
docker-compose -f docker-compose.simple.yml up -d

# Konteyner durumlarını göster
log_info "Konteyner durumları:"
docker ps

# Logları göster
log_info "Bot logları (10 saniye sonra):"
sleep 10
docker logs telegram_bot

log_info "====================================================="
log_info "Telegram Bot başarıyla başlatıldı!"
log_info "API erişim URL'si: http://localhost:8000"
log_info "Bot loglarını görmek için: docker logs telegram_bot"
log_info "Servisleri durdurmak için: docker-compose -f docker-compose.simple.yml down"
log_info "=====================================================" 