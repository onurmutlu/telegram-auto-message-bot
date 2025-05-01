FROM python:3.10-slim

WORKDIR /

# Sistem paketlerini güncelle ve gerekli paketleri kur
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Gerekli Python paketlerini kur
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Uygulama kodlarını kopyala
COPY . .

# Çalışma dizinini oluştur (varsa)
RUN mkdir -p logs session

# Uygulamayı çalıştır
CMD ["python", "-m", "bot.main"] 