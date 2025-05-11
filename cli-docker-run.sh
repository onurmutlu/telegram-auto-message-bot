#!/bin/bash
# CLI Arayüzünden adım adım takip edilebilen Docker Kurulum Scripti

# Renk tanımlamaları
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Fonksiyonlar
log_step() {
    echo -e "${BLUE}[ADIM $1]${NC} $2"
    echo -e "----------------------------------------------------------------------"
}

log_info() {
    echo -e "${GREEN}[BİLGİ]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[UYARI]${NC} $1"
}

log_error() {
    echo -e "${RED}[HATA]${NC} $1"
}

log_command() {
    echo -e "${YELLOW}$ $1${NC}"
}

# Başlık
echo -e "${GREEN}==========================================================${NC}"
echo -e "${GREEN}              TELEGRAM BOT DOCKER KURULUMU               ${NC}"
echo -e "${GREEN}==========================================================${NC}"
echo ""

# ADIM 1: Konteyner temizliği
log_step "1" "Önceki konteynerleri temizleme"
log_command "docker stop telegram-bot postgres-db redis-cache 2>/dev/null || true"
docker stop telegram-bot postgres-db redis-cache 2>/dev/null || true
log_command "docker rm telegram-bot postgres-db redis-cache 2>/dev/null || true"
docker rm telegram-bot postgres-db redis-cache 2>/dev/null || true
echo ""

# ADIM 2: Docker durumunu kontrol et
log_step "2" "Docker servisinin durumunu kontrol etme"
if ! docker info > /dev/null 2>&1; then
    log_error "Docker servisi çalışmıyor. Lütfen Docker Desktop'ı başlatın."
    exit 1
else
    log_info "Docker servisi çalışıyor."
fi
echo ""

# ADIM 3: Ortam değişkenlerini yükleme
log_step "3" "Ortam değişkenlerini yükleme"
if [ -f .env ]; then
    log_info ".env dosyası bulundu."
    log_command "source .env"
    set -a
    source .env
    set +a
    log_info "Ortam değişkenleri yüklendi."
else
    log_warn ".env dosyası bulunamadı! Örnek değerler kullanılacak."
    # Örnek değerler
    API_ID="12345678"
    API_HASH="abcdef1234567890abcdef1234567890"
    BOT_TOKEN="1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    DB_USER="botuser"
    DB_PASSWORD="botpass"
    DB_NAME="botdb"
fi

# Ortam değişkenlerini göster
echo "Kullanılacak Ortam Değişkenleri:"
echo -e "${GREEN}API_ID:${NC} ${API_ID:-Tanımlanmamış}"
echo -e "${GREEN}API_HASH:${NC} ${API_HASH:-Tanımlanmamış}"
echo -e "${GREEN}BOT_TOKEN:${NC} ${BOT_TOKEN:-Tanımlanmamış}"
echo -e "${GREEN}DB_USER:${NC} ${DB_USER:-botuser}"
echo -e "${GREEN}DB_PASSWORD:${NC} ${DB_PASSWORD:-botpass}"
echo -e "${GREEN}DB_NAME:${NC} ${DB_NAME:-botdb}"
echo ""

# Devam etmek istiyor mu?
read -p "Devam etmek istiyor musunuz? (e/h): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Ee]$ ]]; then
    log_error "İşlem kullanıcı tarafından iptal edildi."
    exit 1
fi
echo ""

# ADIM 4: Docker ağı oluştur
log_step "4" "Docker ağı oluşturma"
log_command "docker network create telegram-network || true"
docker network create telegram-network 2>/dev/null || true
log_info "telegram-network ağı oluşturuldu veya zaten mevcut."
echo ""

# ADIM 5: Dizin yapısı oluştur
log_step "5" "Çalışma dizinleri oluşturma"
log_command "mkdir -p data/postgres data/redis logs sessions"
mkdir -p data/postgres data/redis logs sessions
log_command "chmod -R 777 data logs sessions"
chmod -R 777 data logs sessions
log_info "Çalışma dizinleri oluşturuldu ve izinleri ayarlandı."
echo ""

# ADIM 6: PostgreSQL konteyneri başlat
log_step "6" "PostgreSQL veritabanı konteyneri başlatma"
log_command "docker run --name postgres-db \\
    --network telegram-network \\
    -e POSTGRES_USER=${DB_USER:-botuser} \\
    -e POSTGRES_PASSWORD=${DB_PASSWORD:-botpass} \\
    -e POSTGRES_DB=${DB_NAME:-botdb} \\
    -v \$(pwd)/data/postgres:/var/lib/postgresql/data \\
    -p 5432:5432 \\
    -d postgres:14-alpine"

docker run --name postgres-db \
    --network telegram-network \
    -e POSTGRES_USER=${DB_USER:-botuser} \
    -e POSTGRES_PASSWORD=${DB_PASSWORD:-botpass} \
    -e POSTGRES_DB=${DB_NAME:-botdb} \
    -v $(pwd)/data/postgres:/var/lib/postgresql/data \
    -p 5432:5432 \
    -d postgres:14-alpine

if [ $? -eq 0 ]; then
    log_info "PostgreSQL konteyneri başlatıldı."
else
    log_error "PostgreSQL konteyneri başlatılamadı!"
    exit 1
fi
echo ""

# ADIM 7: Redis konteyneri başlat
log_step "7" "Redis konteyneri başlatma"
log_command "docker run --name redis-cache \\
    --network telegram-network \\
    -v \$(pwd)/data/redis:/data \\
    -p 6379:6379 \\
    -d redis:7-alpine"

docker run --name redis-cache \
    --network telegram-network \
    -v $(pwd)/data/redis:/data \
    -p 6379:6379 \
    -d redis:7-alpine

if [ $? -eq 0 ]; then
    log_info "Redis konteyneri başlatıldı."
else
    log_error "Redis konteyneri başlatılamadı!"
    exit 1
fi
echo ""

# ADIM 8: Servislerin başlamasını bekle
log_step "8" "Veritabanı ve Redis servislerinin başlamasını bekleme"
log_info "10 saniye bekleniyor..."
sleep 10
log_info "Servisler hazır olmalı."
echo ""

# ADIM 9: Dockerfile oluştur
log_step "9" "Dockerfile oluşturma"
log_command "cat > Dockerfile.cli << EOF
FROM python:3.10-slim

WORKDIR /app

# Gerekli paketleri yükle
RUN apt-get update && apt-get install -y --no-install-recommends \\
    libpq-dev \\
    curl \\
    && apt-get clean \\
    && rm -rf /var/lib/apt/lists/*

# Bağımlılıkları kopyala ve yükle
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Uygulama dosyalarını kopyala
COPY app /app/app
COPY alembic.ini /app/

# Çalışma dizinleri oluştur
RUN mkdir -p /app/logs /app/sessions

# Ortam değişkenleri
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD [\"python\", \"-m\", \"app.main\"]
EOF"

cat > Dockerfile.cli << EOF
FROM python:3.10-slim

WORKDIR /app

# Gerekli paketleri yükle
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Bağımlılıkları kopyala ve yükle
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Uygulama dosyalarını kopyala
COPY app /app/app
COPY alembic.ini /app/

# Çalışma dizinleri oluştur
RUN mkdir -p /app/logs /app/sessions

# Ortam değişkenleri
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["python", "-m", "app.main"]
EOF

log_info "Dockerfile.cli oluşturuldu."
echo ""

# ADIM 10: Requirements.txt kontrolü
log_step "10" "Requirements dosyasını kontrol etme"
if [ ! -f requirements.txt ]; then
    log_warn "requirements.txt bulunamadı, requirements.staging.txt kullanılıyor..."
    if [ -f requirements.staging.txt ]; then
        log_command "cp requirements.staging.txt requirements.txt"
        cp requirements.staging.txt requirements.txt
        log_info "requirements.txt oluşturuldu."
    else
        log_error "Hiçbir requirements dosyası bulunamadı!"
        exit 1
    fi
else
    log_info "requirements.txt mevcut."
fi
echo ""

# ADIM 11: Docker imajını oluştur
log_step "11" "Docker imajını oluşturma"
log_command "docker build -f Dockerfile.cli -t telegram-bot-cli:latest ."
docker build -f Dockerfile.cli -t telegram-bot-cli:latest .

if [ $? -eq 0 ]; then
    log_info "Docker imajı başarıyla oluşturuldu."
else
    log_error "Docker imajı oluşturulamadı!"
    exit 1
fi
echo ""

# ADIM 12: Bot konteynerini başlat
log_step "12" "Bot konteynerini başlatma"
log_command "docker run --name telegram-bot \\
    --network telegram-network \\
    -e API_ID=\"${API_ID}\" \\
    -e API_HASH=\"${API_HASH}\" \\
    -e BOT_TOKEN=\"${BOT_TOKEN}\" \\
    -e TELEGRAM_API_ID=\"${API_ID}\" \\
    -e TELEGRAM_API_HASH=\"${API_HASH}\" \\
    -e TELEGRAM_BOT_TOKEN=\"${BOT_TOKEN}\" \\
    -e DATABASE_URL=\"postgresql://${DB_USER:-botuser}:${DB_PASSWORD:-botpass}@postgres-db:5432/${DB_NAME:-botdb}\" \\
    -e REDIS_URL=\"redis://redis-cache:6379/0\" \\
    -e DB_HOST=\"postgres-db\" \\
    -e DB_PORT=\"5432\" \\
    -e DB_USER=\"${DB_USER:-botuser}\" \\
    -e DB_PASSWORD=\"${DB_PASSWORD:-botpass}\" \\
    -e DB_NAME=\"${DB_NAME:-botdb}\" \\
    -e SESSION_NAME=\"telegram_session\" \\
    -e ENV=\"production\" \\
    -e DEBUG=\"false\" \\
    -e LOG_LEVEL=\"INFO\" \\
    -v \$(pwd)/logs:/app/logs \\
    -v \$(pwd)/sessions:/app/sessions \\
    -p 8000:8000 \\
    -d telegram-bot-cli:latest"

docker run --name telegram-bot \
    --network telegram-network \
    -e API_ID="${API_ID}" \
    -e API_HASH="${API_HASH}" \
    -e BOT_TOKEN="${BOT_TOKEN}" \
    -e TELEGRAM_API_ID="${API_ID}" \
    -e TELEGRAM_API_HASH="${API_HASH}" \
    -e TELEGRAM_BOT_TOKEN="${BOT_TOKEN}" \
    -e DATABASE_URL="postgresql://${DB_USER:-botuser}:${DB_PASSWORD:-botpass}@postgres-db:5432/${DB_NAME:-botdb}" \
    -e REDIS_URL="redis://redis-cache:6379/0" \
    -e DB_HOST="postgres-db" \
    -e DB_PORT="5432" \
    -e DB_USER="${DB_USER:-botuser}" \
    -e DB_PASSWORD="${DB_PASSWORD:-botpass}" \
    -e DB_NAME="${DB_NAME:-botdb}" \
    -e SESSION_NAME="telegram_session" \
    -e ENV="production" \
    -e DEBUG="false" \
    -e LOG_LEVEL="INFO" \
    -v $(pwd)/logs:/app/logs \
    -v $(pwd)/sessions:/app/sessions \
    -p 8000:8000 \
    -d telegram-bot-cli:latest

if [ $? -eq 0 ]; then
    log_info "Bot konteyneri başlatıldı."
else
    log_error "Bot konteyneri başlatılamadı!"
fi
echo ""

# ADIM 13: Konteyner durumlarını göster
log_step "13" "Konteyner durumlarını kontrol etme"
log_command "docker ps -a"
docker ps -a
echo ""

# ADIM 14: Bot loglarını göster
log_step "14" "Bot loglarını kontrol etme"
log_info "5 saniye bekleniyor ve sonra loglar gösterilecek..."
sleep 5
log_command "docker logs telegram-bot"
docker logs telegram-bot
echo ""

# ADIM 15: Özet
log_step "15" "Özet"
CONTAINER_STATUS=$(docker inspect -f '{{.State.Status}}' telegram-bot 2>/dev/null || echo "not_found")

if [ "$CONTAINER_STATUS" == "running" ]; then
    log_info "Telegram Bot başarıyla çalışıyor!"
    echo -e "${GREEN}-----------------------------------------------------${NC}"
    echo -e "${GREEN}API URL:${NC} http://localhost:8000"
    echo -e "${GREEN}Bot Logları:${NC} docker logs telegram-bot"
    echo -e "${GREEN}Konteynerleri Durdurma:${NC} docker stop telegram-bot postgres-db redis-cache"
    echo -e "${GREEN}Konteynerleri Silme:${NC} docker rm telegram-bot postgres-db redis-cache"
    echo -e "${GREEN}-----------------------------------------------------${NC}"
else
    log_error "Bot konteyneri çalışmıyor! Lütfen logları inceleyin."
    echo -e "${RED}-----------------------------------------------------${NC}"
    echo -e "${RED}Hata Ayıklama Komutları:${NC}"
    echo -e "${YELLOW}$ docker logs telegram-bot${NC}"
    echo -e "${YELLOW}$ docker exec -it postgres-db psql -U ${DB_USER:-botuser} -d ${DB_NAME:-botdb}${NC}"
    echo -e "${YELLOW}$ docker exec -it redis-cache redis-cli${NC}"
    echo -e "${RED}-----------------------------------------------------${NC}"
fi 