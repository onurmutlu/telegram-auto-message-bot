# ===== Build Stage =====
FROM python:3.10-slim-bullseye AS builder

# Çalışma dizini oluşturma
WORKDIR /app

# Sistem bağımlılıklarını kurma
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    python3-dev \
    libpq-dev \
    git \
    curl \
    make \
    zlib1g-dev \
    libssl-dev \
    gperf \
    cmake \
    clang \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Pip'i yükseltme ve poetry kurma
RUN pip install --no-cache-dir --upgrade pip && pip install poetry

# Bağımlılıkları kopyalama
COPY pyproject.toml poetry.lock* ./

# Wheel'ları oluştur
RUN poetry export -f requirements.txt --output requirements.txt && \
    pip wheel --no-cache-dir --wheel-dir=/app/wheels -r requirements.txt

# TDLib kurma
RUN git clone https://github.com/tdlib/td.git && \
    cd td && \
    mkdir build && \
    cd build && \
    cmake -DCMAKE_BUILD_TYPE=Release .. && \
    cmake --build . -j$(nproc) && \
    make install && \
    cd ../.. && \
    rm -rf td

# ===== Runtime Stage =====
FROM python:3.10-slim-bullseye AS runtime

LABEL maintainer="Telegram Bot <info@telegram-bot.com>"
LABEL description="Telegram Bot Multi-Account Container"

# Çalışma dizini oluşturma
WORKDIR /app

# Timezone ayarları ve gerekli çalışma zamanı kütüphaneleri
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    tzdata \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Builder stage'den TDLib'i kopyala
COPY --from=builder /usr/local/lib/libtdjson.so /usr/local/lib/
COPY --from=builder /usr/local/lib/libtdjson.so.* /usr/local/lib/
RUN ldconfig

# Builder stage'den wheels'ları kopyala
COPY --from=builder /app/wheels /app/wheels
COPY --from=builder /app/requirements.txt /app/requirements.txt

# Bağımlılıkları wheel'lardan kur
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --no-index --find-links=/app/wheels -r requirements.txt && \
    rm -rf /app/wheels /app/requirements.txt

# Uygulama kodunu kopyalama
COPY . .

# Ortam değişkenleri
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV TZ=Europe/Istanbul
ENV SESSION_NAME=telegram_session

# Uygulama için özel kullanıcı oluştur
RUN useradd -m appuser
USER appuser

# Sağlık kontrolü
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/api/v1/health || exit 1

# Konteyner ayarları
EXPOSE ${PORT:-8000}

# Çalıştırma komutu
CMD ["python", "-m", "app.main"] 