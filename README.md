# Telegram Bot

Bu proje, Telegram gruplarına otomatik mesajlar gönderen, DM'ler aracılığıyla kullanıcı etkileşimine cevap veren ve tanıtım mesajları ileten bir bot uygulamasıdır.

## 🚀 Özellikler

- **Gruplara Otomatik Mesaj Gönderimi**: Önceden tanımlanmış şablonları kullanarak gruplara otomatik mesajlar gönderir
- **DM Yönetimi**: Kullanıcılara özel mesajlar gönderir, tanıtım ve hizmet bilgileri paylaşır
- **Grup Tanıtım Mesajları**: Farklı gruplarda tanıtım mesajları paylaşır
- **Health Monitoring**: Sistem ve servislerin durumunu sürekli izler
- **Veritabanı Entegrasyonu**: PostgreSQL ile tüm verileri düzenli ve etkili şekilde saklar
- **API Erişimi**: FastAPI tabanlı API arayüzü ile uzaktan yönetim

## 📋 Gereksinimler

- Python 3.9+
- PostgreSQL 12+
- Redis (opsiyonel)
- Docker & Docker Compose (opsiyonel)

## 🔧 Kurulum

### Manuel Kurulum

1. Gerekli paketleri yükleyin:
```
pip install -r requirements.txt
```

2. `.env` dosyasını oluşturun:
```
cp example.env .env
```

3. `.env` dosyasını kendi API ID ve API HASH değerlerinizle düzenleyin.

4. Veritabanını oluşturun:
```
python -m app.scripts.setup_database
```

5. Mesaj şablonlarını yükleyin:
```
python -m app.scripts.load_templates
```

### Docker ile Kurulum

1. `.env` dosyasını oluşturun:
```
cp example.env .env
```

2. `.env` dosyasını düzenleyin.

3. Docker Compose ile başlatın:
```
docker-compose up -d
```

## 🚦 Kullanım

### Bot'u Başlatma

```
python -m app.main
```

veya CLI ile:

```
1a
```

### API'yi Başlatma

```
python -m app.api.main
```

### Durumu Kontrol Etme

```
python -m app.cli status
```

### Şablonları Güncelleme

```
python -m app.cli templates
```

## 🧰 Servisler

- **EngagementService**: Gruplara otomatik mesajlar gönderir
- **DirectMessageService**: Kullanıcılara özel mesajlar gönderir
- **PromoService**: Tanıtım mesajları iletir
- **ActivityService**: Kullanıcı etkileşimlerini izler
- **HealthService**: Sistem ve servislerin durumunu izler

## 📜 API Endpointleri

- `GET /api/v1/bot/status`: Bot durumunu getir
- `POST /api/v1/bot/start`: Botu başlat
- `POST /api/v1/bot/stop`: Botu durdur
- `GET /api/v1/bot/services`: Servis listesini al
- `POST /api/v1/bot/services/{service_name}/restart`: Belirli bir servisi yeniden başlat
- `GET /api/v1/bot/logs`: Son logları getir
- `GET /api/v1/bot/stats`: İstatistikleri getir

## 🔗 Bağlantılar

- API Dokümantasyonu: `http://localhost:8000/docs`
- Admin Paneli: `http://localhost:8000/admin`

## 📊 Monitoring

Sistem ve servis durumunu izlemek için:

1. API üzerinden durumu kontrol edin:
```
curl http://localhost:8000/api/v1/bot/status
```

2. CLI ile kontrol edin:
```
python -m app.cli status
```

## 📝 Mesaj Şablonları

Mesaj şablonları `data/templates` dizininde JSON formatında tutulur. Bu şablonlar, `app.scripts.load_templates` scripti ile veritabanına yüklenir.

### Şablon Örneği

```json
{
  "content": "Merhaba! Ben bir bot mesajıyım!",
  "type": "engagement",
  "engagement_rate": 0.3,
  "is_active": true
}
```

## 🔒 Güvenlik

- API erişimi JWT token tabanlı yetkilendirme kullanır
- Veritabanı bağlantıları şifrelidir
- Telegram API anahtarları güvenli bir şekilde saklanır

## 🏗️ Yapı

```
telegram-bot/
├── app/                # Ana uygulama
│   ├── api/            # API endpointleri
│   ├── core/           # Çekirdek fonksiyonlar
│   ├── db/             # Veritabanı işlemleri
│   ├── models/         # Veritabanı modelleri
│   ├── services/       # Servisler
│   │   ├── analytics/  # Analitik servisleri
│   │   ├── messaging/  # Mesajlaşma servisleri
│   │   └── monitoring/ # İzleme servisleri
│   ├── scripts/        # Yardımcı betikler
│   └── utils/          # Yardımcı fonksiyonlar
├── data/               # Veri dosyaları
├── logs/               # Log dosyaları
├── runtime/            # Çalışma zamanı verileri
└── tests/              # Test dosyaları
```

## 🛠️ Sorun Giderme

### Sık Karşılaşılan Sorunlar

1. **Veritabanı Bağlantı Hatası**
   - `.env` dosyasında DB_ değişkenlerinin doğru olduğundan emin olun
   - PostgreSQL servisinin çalıştığından emin olun

2. **Telegram Bağlantı Hatası**
   - API ID ve API HASH değerlerinin doğru olduğundan emin olun
   - Oturum dosyasını yeniden oluşturun: `python -m app.cli session`

3. **Servis Başlatma Hatası**
   - Gerekli paketlerin yüklü olduğundan emin olun
   - Logları kontrol edin: `cat logs/bot.log`

## 🤝 Katkıda Bulunma

Katkı sağlamak için lütfen şu adımları izleyin:

1. Bu repo'yu fork edin
2. Özellik dalınızı oluşturun (`git checkout -b feature/amazing-feature`)
3. Değişikliklerinizi commit edin (`git commit -m 'feat: add some amazing feature'`)
4. Dalınızı push edin (`git push origin feature/amazing-feature`)
5. Bir Pull Request oluşturun

## 📄 Lisans

Bu proje MIT lisansı altında lisanslanmıştır. Daha fazla bilgi için `LICENSE` dosyasına bakın.