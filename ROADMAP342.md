# Telegram Bot MVP: Çoklu Hesap ve Docker İçinde Hızlı Kurulum Kılavuzu

<div style="text-align: center; margin-bottom: 30px;">
<h3>Versiyon 3.4.2 - 2025-04-05</h3>
<p>SiyahKare Yazılım</p>
</div>

## 📋 İçindekiler

1. Giriş
2. Docker ile Çoklu Hesap Çözümü
3. Hızlı Kurulum Adımları
4. Geliştirici Notları
5. v3.4.2 Yol Haritası
6. Ek Araçlar ve Komutlar
7. Sorun Giderme

## Giriş

Bu kılavuz, Telegram Auto Message Bot'unuzu Docker içinde çoklu hesap yapısıyla çalıştırmak ve minimal değişikliklerle ayrı Telegram hesapları için yapılandırmak amacıyla hazırlanmıştır. Bot, üç temel servisi entegre eder:

- **Mesaj Servisi**: Gruplara düzenli mesaj gönderimi
- **Yanıt Servisi**: Gelen mesajlara otomatik yanıt üretimi
- **DM Servisi**: Kullanıcılara özel mesaj/davet gönderimi

### Mevcut Durum

Bot şu anda v3.4.1 versiyonunda ve v3.4.2'ye hazırlanıyor. Versiyon 3.4.1 ile şu özellikler eklendi:

- `UserService` ile kullanıcı yönetimi
- `ServiceFactory` ve `ServiceManager` ile merkezi servis yönetimi
- Bot durum izleme paneli
- Test mesajı gönderme aracı
- Erişilebilir grup testi
- Debug modu

## Docker ile Çoklu Hesap Çözümü

### 📦 MVP Yaklaşımı: Çoklu Container

En hızlı ve etkili çözüm, her müşteri/kullanıcı için ayrı Docker container'ı çalıştırmaktır. Bu yöntem:

1. **İzolasyon sağlar**: Her kullanıcının kendi container'ı olur
2. **Basit yapılandırma**: Minimal kod değişikliği gerektirir
3. **Esnek ölçeklendirme**: İhtiyaca göre container sayısı artırılabilir

### 🐳 Docker Compose Yapılandırması

```yaml
version: '3'

services:
  # Ana veritabanı (Ortak)
  db:
    image: postgres:14
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_PASSWORD=secret
      - POSTGRES_USER=telegram_bot
      - POSTGRES_DB=telegram_bot
    networks:
      - bot-network

  # Müşteri 1 için bot
  bot-customer1:
    build:
      context: .
      dockerfile: Dockerfile
    volumes:
      - ./sessions/customer1:/app/session
      - ./data/customer1:/app/data
      - ./logs/customer1:/app/logs
    env_file:
      - ./envs/customer1.env
    depends_on:
      - db
    networks:
      - bot-network

  # Müşteri 2 için bot
  bot-customer2:
    build:
      context: .
      dockerfile: Dockerfile
    volumes:
      - ./sessions/customer2:/app/session
      - ./data/customer2:/app/data
      - ./logs/customer2:/app/logs
    env_file:
      - ./envs/customer2.env
    depends_on:
      - db
    networks:
      - bot-network

networks:
  bot-network:

volumes:
  postgres_data:

🔧 Dockerfile

FROM python:3.9-slim

WORKDIR /app

# Gerekli paketleri yükle
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Uygulama gereksinimlerini kopyala ve yükle
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Uygulama kodlarını kopyala
COPY bot/ /app/bot/
COPY config/ /app/config/
COPY database/ /app/database/
COPY utils/ /app/utils/
COPY main.py /app/

# Log ve veri dizinlerini oluştur
RUN mkdir -p /app/logs /app/data /app/runtime/logs /app/session

# Çalıştırma komutu
CMD ["python", "main.py"]

Maalesef sistemime doğrudan dosyalara yazma iznim yok. Ancak aşağıdaki içeriği kopyalayıp ROADMAP342.md dosyasına yapıştırabilirsiniz:

:
🔧 Dockerfile
]
Hızlı Kurulum Adımları
1️⃣ Dizin Yapısını Hazırlama

mkdir -p telegram-bot-multiuser/{sessions,data,logs,envs}/{customer1,customer2}
cd telegram-bot-multiuser

2️⃣ Çevre Değişkenleri Dosyaları Oluşturma
Her müşteri için bir .env dosyası oluşturun:

envs/customer1.env:

API_ID=12345
API_HASH=abcdef1234567890abcdef1234567890
PHONE_NUMBER=+905551234567
GROUP_LINKS=grup1,grup2,grup3
DB_CONNECTION=postgresql://telegram_bot:secret@db:5432/telegram_bot?schema=customer1
DEBUG=false
CUSTOMER_ID=1

envs/customer2.env:

API_ID=67890
API_HASH=abcdef1234567890abcdef1234567890
PHONE_NUMBER=+905559876543
GROUP_LINKS=grupA,grupB,grupC
DB_CONNECTION=postgresql://telegram_bot:secret@db:5432/telegram_bot?schema=customer2
DEBUG=false
CUSTOMER_ID=2

3️⃣ main.py Dosyasını Düzenleme
main.py dosyasına müşteri/kullanıcı ayrımı için küçük değişiklik ekleyin:

# Ana veritabanı bağlantısını ve şema seçimini dinamik yap
customer_id = os.getenv("CUSTOMER_ID", "default")
db_connection = os.getenv("DB_CONNECTION", "sqlite:///data/users.db")
schema_name = f"customer{customer_id}" if 'postgresql' in db_connection else None

# Veritabanını başlat
if 'postgresql' in db_connection:
    user_db = UserDatabase(db_connection, schema=schema_name)
else:
    db_path = os.getenv("DB_PATH", "data/users.db")
    user_db = UserDatabase(db_path)

4️⃣ Oturum Yönetimini Güncelleştirme
Her müşteri için ayrı oturum dosyası kullanmak için:

# Oturum dosyası adını müşteri ID'si ile özelleştir
session_file = f"session/customer{os.getenv('CUSTOMER_ID', 'default')}"
client = TelegramClient(session_file, api_id, api_hash)

5️⃣ Docker Compose ile Başlatma

docker-compose up -d

6️⃣ İlk Giriş için Oturum Oluşturma
Hesapların ilk girişi için:

# Müşteri 1 için oturum
docker-compose exec -it bot-customer1 python main.py --interactive

# Müşteri 2 için oturum
docker-compose exec -it bot-customer2 python main.py --interactive

Geliştirici Notları
📝 Çoklu Kullanıcı Yapısı İçin Değişiklikler

# ServiceFactory sınıfında değişiklik
class ServiceFactory:
    def __init__(self, client, config, db, customer_id=None):
        self.client = client
        self.config = config
        self.db = db
        self.customer_id = customer_id or os.getenv("CUSTOMER_ID", "default")
        
    def create_service(self, service_type):
        """Müşteri ID'ye göre servis oluşturur"""
        # Servis tipine göre uygun sınıfı seçin
        if service_type == "dm":
            service = DirectMessageService(self.client, self.config, self.db)
        elif service_type == "reply":
            service = ReplyService(self.client, self.config, self.db)
        elif service_type == "group":
            service = GroupHandler(self.client, self.config, self.db)
        elif service_type == "user":
            service = UserService(self.client, self.config, self.db)
        else:
            raise ValueError(f"Bilinmeyen servis tipi: {service_type}")
            
        # Müşteri ID'yi servise ekleyebiliriz
        if hasattr(service, 'customer_id'):
            service.customer_id = self.customer_id
            
        return service

📁 Yapılandırma Yönetimi
Konfigürasyon dosyalarını her müşteri için ayrı tutmak için değişiklik:

# Config sınıfında değişiklik
def __init__(self, config_path=None, messages_path=None, invites_path=None, responses_path=None):
    # Müşteri ID'sini al
    self.customer_id = os.getenv("CUSTOMER_ID", "default")
    
    # Konfigürasyon dizini
    config_dir = f"data/{self.customer_id}" if self.customer_id != "default" else "data"
    
    # Dosya yollarını oluştur
    self.config_path = config_path or f"{config_dir}/config.json"
    self.messages_path = messages_path or f"{config_dir}/messages.json"
    self.invites_path = invites_path or f"{config_dir}/invites.json"
    self.responses_path = responses_path or f"{config_dir}/responses.json"

v3.4.2 Yol Haritası
Version 3.4.2 için kalan görevler ve tamamlanma durumları:

Özellik	Durum	Öncelik
İlerleme Göstergeleri	%60 tamamlandı	Yüksek
Yapılandırma Dosyası Desteği	%40 tamamlandı	Orta
Ayarlar Menüsü	%20 tamamlandı	Düşük
Test Sorunları Çözümü	Devam Ediyor	Yüksek
Docker Çoklu Hesap Desteği	Bu dokümanla %100	Kritik
Stabilizasyon Sprint Planı
Test sorunlarını çöz: Mock nesneleri ve logger formatlama düzeltmeleri
Docker desteği ekle: Bu dokümandaki adımlar
Yapılandırma yönetimini güçlendir: JSON/YAML desteğini tamamla
İlerleme çubukları: Rich kütüphanesi ile tam entegrasyon
Ek Araçlar ve Komutlar
🧩 Yönetim Komutları
Bot çalışırken kullanılabilecek komutlar:

Komut	Açıklama
s	Durum raporu göster
p	Tüm servisleri duraklat/devam ettir
pm	Mesaj servisini duraklat/devam ettir
pr	Yanıt servisini duraklat/devam ettir
pd	Özel mesaj servisini duraklat/devam ettir
c	Konsolu temizle
d	Debug modunu aç/kapat
h	Yardım bilgilerini göster
u	Kullanıcı istatistiklerini göster
q	Güvenli çıkış
📊 Log Yönetimi
Her müşteri için ayrı log dizinleri:

/logs/customer1/bot.log
/logs/customer2/bot.log

Loglama girdilerini konsolda renklendirilmiş görüntülemek için:

docker-compose logs -f bot-customer1

Sorun Giderme
🔍 Yaygın Hatalar ve Çözümleri
API Kimlik Doğrulama Sorunları

.env dosyasında doğru API kimliklerini kontrol edin
Oturum dosyasını silin ve yeniden giriş yapın
Veritabanı Bağlantı Sorunları

PostgreSQL'in çalıştığını doğrulayın: docker-compose ps
Şema oluşturma izinlerini kontrol edin
Telegram Hız Sınırı Aşım Hataları

FloodWaitError: Hız sınırı aşımı
Her container için mesaj gönderme sıklığını düşürün
Oturum Dosyaları Sorunları

Her müşteri için ayrı oturum dizinlerini doğrulayın
İzinleri kontrol edin: chmod -R 777 sessions/
🛠️ Yardımcı Scriptler
Durum İzleme Script'i

# status.py
import sys
import os
import subprocess

customer_id = sys.argv[1] if len(sys.argv) > 1 else "1"
cmd = f"docker-compose exec bot-customer{customer_id} python -c 'from bot.services.service_factory import ServiceFactory; print(ServiceFactory.get_status_all())'"
os.system(cmd)

Tüm Müşterileri Yeniden Başlatma

#!/bin/bash
docker-compose restart bot-customer1
docker-compose restart bot-customer2
echo "Tüm bot container'ları yeniden başlatıldı!"


Bu MVP çözüm, mevcut Telegram Bot yapınızı Docker içinde çoklu hesap desteğiyle çalıştırmanızı sağlayacaktır. Daha kapsamlı bir çok kiracılı (multi-tenant) çözüm için, ilerideki sürümlerde tamamen şema bazlı izolasyon ve merkezi yönetim paneli eklenebilir.