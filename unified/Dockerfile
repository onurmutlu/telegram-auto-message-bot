FROM python:3.10-slim

WORKDIR /app

# Sistem paketlerini güncelle ve gerekli paketleri kur
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Gerekli çalışma dizinlerini oluştur
RUN mkdir -p logs session runtime runtime/logs runtime/database runtime/sessions data

# Önce requirements dosyasını kopyala ve bağımlılıkları yükle
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Tüm uygulama dosyalarını kopyala
COPY . .

# Çalıştırma izinleri ver
RUN chmod +x unified/main.py

# Sağlık kontrolü
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD python -c "import socket; import os; s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.connect(('localhost', int(os.environ.get('HEALTH_PORT', 8080))))" || exit 1

# Çalışma zamanı yapılandırması
ENV PYTHONUNBUFFERED=1

# Varsayılan komut: birleştirilmiş ana modülü çalıştır
CMD ["python", "unified/main.py"] 