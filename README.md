# Telegram Bot Platform

Modern Telegram bot platformu - grup yönetimi, analitik ve otomatik mesajlaşma özellikleri

## Genel Bakış

Bu proje, çeşitli servisleri ve araçları içeren kapsamlı bir Telegram bot platformudur. Bot, grup yönetimi, kullanıcı takibi, otomatik mesajlaşma ve analitik gibi özelliklere sahiptir.

## Mevcut Sürüm

### 3.9.5 - Güvenilirlik ve Performans Geliştirmeleri 

Platformun güvenilirliği ve performansını artırmaya odaklanan 3.9.5 sürümündeki geliştirmeler:

#### Gelişmiş Konfigürasyon Yönetimi
`app/core/config.py` tamamen yeniden yazıldı:
- Güvenli çevre değişkeni yükleme sistemi 
- Yorum ve boşluk temizleme ile daha sağlam yapılandırma
- Otomatik tip dönüşümleri ve varsayılan değerler
- Kapsamlı zaman aşımı ve bağlantı ayarları

#### Akıllı Mesaj Gönderimi
FloodWait yönetimi ve gönderim optimizasyonları (`event_listener.py`):
- Grup yoğunluğuna göre dinamik gecikme stratejisi
- Grup büyüklüğü ve etkinliğine dayalı önceliklendirme
- Otomatik hata kurtarma ve yeniden deneme mekanizmaları
- İstatistiksel analiz ile optimal gönderim zamanları

#### Veritabanı Hata Düzeltmeleri
Veritabanı bağlantı sorunları ve tutarlılık hataları giderildi:
- InFailedSqlTransaction hatalarına karşı koruma
- Eksik tablo oluşturma ve şema güncelleme araçları
- Otomatik bağlantı sıfırlama ve kurtarma
- Transaction izolasyon seviyesi optimizasyonları

#### Telegram Oturum Yönetimi İyileştirmeleri
Oturum kararlılığı ve süreklilik sorunları çözüldü:
- Oturum dosyalarının yedekleme ve kurtarma mekanizmaları
- Bağlantı yeniden kurma stratejileri
- API hatalarına karşı akıllı bekleme ve yeniden deneme
- Çoklu oturum yönetimi geliştirmeleri

## Gelecek Sürüm

### 4.0.0 - Mikro Servis Mimarisi

4.0.0 sürümü, platformun tamamen mikro servis mimarisine geçişini kapsamaktadır:

- **Mikro Servis Dönüşümü**: Monolitik yapıdan bulut tabanlı mikro servislere geçiş.
- **Asenkron Mesaj Kuyrukları**: RabbitMQ veya Kafka ile servisler arası iletişim.
- **Konteyner Orkestrasyonu**: Docker ve Kubernetes ile servis yönetimi.
- **Yeni Kullanıcı Arayüzü**: Tamamen yeniden tasarlanmış web tabanlı yönetim paneli.
- **Gelişmiş Analitik**: ELK Stack ve veri ambarı ile kapsamlı analitik ve raporlama yetenekleri.
- **Yapay Zeka Entegrasyonu**: OpenAI API entegrasyonu ile akıllı içerik oluşturma ve analiz.

Detaylı sürüm notları ve planlar için [CHANGELOG.md](CHANGELOG.md) ve [ROADMAP.md](ROADMAP.md) dosyalarını inceleyebilirsiniz.

## Klasör Yapısı

```
app/
├── api/            # FastAPI API 
├── core/           # Çekirdek bileşenler
│   └── tdlib/      # TDLib entegrasyonu
├── db/             # Veritabanı bağlantıları ve migrationlar
├── maintenance/    # Bakım ve düzeltme betikleri
├── models/         # SQLModel modelleri
├── services/       # Bot servisleri
│   ├── analytics/  # Analitik servisleri
│   ├── monitoring/ # İzleme servisleri
│   ├── error_handling/ # Hata yönetimi
│   └── messaging/  # Mesajlaşma servisleri
├── sessions/       # Telegram oturum dosyaları
├── tests/          # Test dosyaları
├── utils/          # Yardımcı fonksiyonlar
│   └── dashboard/  # Dashboard araçları
├── client.py       # Client entry point
├── scheduler.py    # Zamanlayıcı entry point
└── main.py         # Ana entry point
```

## Servisler

Platform aşağıdaki servisleri içerir:

- **BaseService**: Tüm servisler için temel sınıf
- **UserService**: Kullanıcı yönetimi ve takibi
- **GroupService**: Grup yönetimi ve izleme
- **MessageService**: Genel mesajlaşma işlevleri
- **AnnouncementService**: Grup duyuruları
- **DirectMessageService**: Kullanıcılara özel mesajlar
- **ReplyService**: Otomatik yanıtlar
- **InviteService**: Davet yönetimi
- **PromoService**: Promosyon mesajları
- **AnalyticsService**: Kullanım analizi
- **DataMiningService**: Veri madenciliği ve analizler
- **ErrorService**: Hata takibi ve raporlama
- **HealthMonitor**: Servis sağlığı izleme
- **DemoService**: Test ve örnek uygulama servisi
- **GPTService**: AI tabanlı yanıtlar

## Bakım Araçları

Platformun bakımı için çeşitli araçlar bulunmaktadır:

- **Veritabanı Düzeltmeleri**: fix_database.py, fix_db_locks.py vb.
- **Kullanıcı Veri Düzeltmeleri**: fix_user_storage.py, fix_user_ids.py vb.
- **Grup Verileri Düzeltmeleri**: fix_group_tables.py, fix_groups_table.py vb.
- **Oturum Düzeltmeleri**: fix_telethon_session.py vb.

## Kullanım

### Kurulum

```bash
pip install -r requirements.txt
```

### Yapılandırma

`.env` dosyasında gerekli ayarları yapın:

```
# Telegram API Credentials
API_ID=12345
API_HASH=your_api_hash
BOT_TOKEN=your_bot_token

# Database Connection
DATABASE_URL=postgresql://user:password@localhost:5432/telegram_bot
```

### Çalıştırma

```bash
# Ana bot servisini başlat
python -m app.main

# Sadece istemciyi başlat
python -m app.client

# Zamanlayıcıyı başlat
python -m app.scheduler
```

## Taşınma Durumu

Bu proje, daha modern ve daha bakımı kolay bir mimari için kod tabanı yeniden yapılandırma sürecinden geçmektedir. Mevcut taşınma durumu:

- ✅ Proje yapısı yeniden düzenlendi
- ✅ Servis yönetimi mimarisi tamamen yenilendi
- ✅ Veritabanı modelleri modernize edildi
- ✅ Docker ve Docker Compose desteği eklendi
- ✅ CI/CD pipeline güncellendi
- ✅ Dokümantasyon MkDocs ile iyileştirildi
- ✅ Veritabanı bağlantı havuzu optimize edildi (v3.9.0)
- ✅ Servis sağlığı izleme sistemi eklendi (v3.9.0)
- ✅ Merkezi hata yönetimi ve kurtarma stratejileri eklendi (v3.9.0)
- ✅ Gelişmiş konfigürasyon yönetimi (v3.9.5)
- ✅ Akıllı mesaj gönderim sistemi (v3.9.5)
- 🔄 Unit ve entegrasyon testleri geliştiriliyor
- 🔄 Web panel entegrasyonu devam ediyor
- 🔄 Mikro servis mimarisine geçiş hazırlığı devam ediyor

Detaylı taşınma durumu için [Taşınma Durumu](docs/migration/status.md) sayfasına bakabilirsiniz.

## Bakım İşlemleri

```bash
# Veritabanı kilitlerini düzelt
python -m app.maintenance.fix_db_locks --verbose

# Telethon oturum sorunlarını düzelt
python -m app.maintenance.fix_telethon_session

# Tüm bakım işlemlerini çalıştır
python -m app.maintenance.database_maintenance --run-all
```

## Testler

```bash
# Tüm testleri çalıştır
pytest app/tests

# Belirli bir test dosyasını çalıştır
python -m app.tests.test_services
```

## Dokümantasyon

Tam dokümantasyon için:

```bash
# MkDocs dokümantasyonunu oluştur
pip install mkdocs-material
mkdocs build

# Dokümantasyonu yerel olarak görüntüle
mkdocs serve
```

Oluşturulan dokümantasyona `http://localhost:8000` adresinden erişebilirsiniz.

## Katkıda Bulunma

Katkıda bulunmak için lütfen:

1. Repoyu forklayın
2. Özellik dalınızı oluşturun (`git checkout -b feature/amazing-feature`)
3. Değişikliklerinizi commit edin (`git commit -m 'Add some amazing feature'`)
4. Dalınızı push edin (`git push origin feature/amazing-feature`)
5. Bir Pull Request açın

## Lisans

Bu proje özel lisans altında dağıtılmaktadır - detaylar için LICENSE dosyasına bakın.