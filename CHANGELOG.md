# Changelog

Tüm önemli değişiklikler bu dosyada belgelenecektir.

Bu proje [Keep a Changelog](https://keepachangelog.com/tr/1.0.0/) kurallarına uymaktadır ve 
[Semantic Versioning](https://semver.org/spec/v2.0.0.html) kullanmaktadır.

## [Yayımlanmamış]

### Eklenenler
- Kubernetes ile ölçeklendirme için Helm chart'ları
- E2E testler için otomatik Telethon mock'ları
- OAuth2 yetkilendirme desteği (hazırlık aşamasında)

## [3.9.0] - 2025-04-05

### Mimari Geliştirmeler
- **Modüler Servis Mimarisi**: Bağımsız çalışabilen servis yapısı gerçekleştirildi
- **Servis Kayıt Sistemi**: ServiceFactory ile dinamik servis kaydı ve yönetimi
- **Merkezi API Katmanı**: Servisler arası iletişim standardizasyonu sağlandı
- **Circuit Breaker Pattern**: Hata durumlarında akıllı servis yönetimi eklendi

### Eklenenler
- **Asenkron Veritabanı Bağlantı Havuzu**: asyncpg ile optimize edilmiş bağlantı havuzu (app/db/async_connection_pool.py)
- **Servis Sağlığı İzleme Sistemi**: HealthMonitor servisi ve API endpoint'leri (app/services/monitoring/health_monitor.py)
- **Gerçek Zamanlı Telemetri**: Servis performans metriklerinin toplanması ve izlenmesi
- **Sağlık Kontrol API'si**: Tüm servisler için /health endpoint'leri eklendi
- **Demo Servisi**: Yeni özellikleri test eden örnek uygulama (app/services/demo_service.py)

### Geliştirilenler
- **Merkezi Hata Yönetimi**: ErrorManager ile hata yönetimi merkezi hale getirildi (app/services/error_handling/)
- **Otomatik Kurtarma Stratejileri**: Retry ve Circuit Breaker desenleri uygulandı
- **Transaction Yönetimi**: Dekoratör tabanlı transaction yönetimi eklendi
- **Akıllı Watchdog**: Servis sağlığı bazlı yeniden başlatma sistemi 
- **Servis Factory**: Servis oluşturma ve yönetimi iyileştirildi (app/services/service_factory.py)

### İyileştirmeler
- PostgreSQL veritabanı bağlantı yönetimi optimize edildi
- Servisler arası bağımlılıklar azaltıldı
- Sistem izleme ve raporlama yetenekleri geliştirildi
- Servis başlangıç sırası ve bağımlılık yönetimi iyileştirildi

## [4.0.0] - Planlanan Tarih: 2025 Q2

### Mimari Değişiklikler
- **Mikro Servis Mimarisine Geçiş**: Monolitik yapıdan mikro servislere dönüşüm
- **Servis Keşif Mekanizması**: Consul veya etcd ile dinamik servis kaydı ve keşfi
- **API Gateway**: Tüm servisler için merkezi erişim noktası
- **Konteyner Orkestrasyonu**: Docker ve Kubernetes ile yönetim

### Eklenenler
- **Asenkron Mesaj Kuyrukları**: RabbitMQ veya Kafka entegrasyonu
- **Web Tabanlı Yönetim Paneli V2**: Tamamen yeniden tasarlanmış kullanıcı deneyimi
- **Gerçek Zamanlı Analitik**: ELK Stack entegrasyonu
- **İş Zekası Araçları**: Veri ambarı ve raporlama yetenekleri
- **OAuth2 ve JWT Yetkilendirme**: Güçlendirilmiş kimlik doğrulama sistemi

### Geliştirilenler
- **Yatay Ölçeklenebilirlik**: Paralel çalışan servis kümesi
- **Otomatik Ölçeklendirme**: Talebe göre kaynak artırımı
- **Stateless Servis Tasarımı**: Tüm servislerin durum bilgisiz hale getirilmesi
- **Ölçeklenebilir Veritabanı Katmanı**: Sharding ve read replica desteği
- **Blue-Green Deployment**: Kesintisiz güncelleme stratejisi

## [2.0.0] - 2023-11-17

### Mimari Değişiklikler
- **Modüler, Paketlenebilir Core**: Bot/, scripts/, utils/ karmaşası `app/` altında toplandı
- **Tek Scheduler'a Geçiş**: Tüm zamanlayıcılar APScheduler (async) altında birleştirildi
- **Model-Driven Database**: SQLModel/SQLAlchemy modelleri ve Alembic migrationları eklendi
- **Docker Multi-Account Orkestrasyonu**: Çoklu hesap desteği için Docker orkestrasyon modeli yenilendi
- **Config & Secret Yönetimi**: Tüm yapılandırmalar Pydantic BaseSettings üzerine aktarıldı

### Eklenenler
- **Web Management Panel**: Next.js tabanlı yönetim paneli
- **WebSocket Canlı Log Akışı**: API üzerinden gerçek zamanlı log akışı
- **FastAPI API**: Modern REST API arayüzü
- **Gözlemlenebilirlik & Güvenlik**: Structlog ve Prometheus metrics entegrasyonu
- **FloodWait Akıllı Backoff Stratejisi**: Telegram API limitleri için otomatik, adaptif gecikme mekanizması
- **Poetry Tabanlı Bağımlılık Yönetimi**: requirements.txt yerine daha güvenli dependency management

### Geliştirilenler
- **Servis Mimarisi**: Tüm servisler BaseService'ten türetildi, yapılandırılabilir hale getirildi
- **Rate Limiter**: Gelişmiş Telegram API rate limiting ve FloodWait yönetimi
- **Hata Yönetimi**: Hata ayıklama ve izleme geliştirmeleri
- **Mesaj Servisi**: Zamanlanmış mesajları daha etkili işleyen servis yeniden yazıldı

### Çözülen Sorunlar
- **Servis Başlatma Sorunları**: ServiceManager düzgün çalışmıyordu, tamamen yeniden yapılandırıldı
- **Veritabanı Bağlantı Hataları**: PostgreSQL bağlantı ve yönetimi geliştirildi
- **Zamanlanmış Görev Çatışmaları**: Tek zamanlayıcı ile çatışmalar elimine edildi

## [1.2.0] - 2023-10-15

### Eklenenler
- Grup Analitik Sistemi 
- Gelişmiş Hata İzleme Sistemi
- Config Adapter Sistemi

### Geliştirilenler
- Veritabanı Optimizasyon ve Performans İyileştirmeleri
- PostgreSQL Bağlantı Yönetimi
- Veritabanı Şema İyileştirmeleri

## [1.1.0] - 2023-09-20

### Eklenenler
- Çoklu hesap desteği
- Gruplar arası otomatik içerik paylaşımı
- Gelişmiş hata yakalama ve işleme

### Geliştirilenler
- Servis mimarisinde optimizasyonlar
- Daha verimli mesaj gönderme algoritması
- Bellek kullanımında iyileştirmeler

### Çözülen Sorunlar
- Uzun çalışma sürelerinde bellek sızıntısı sorunu giderildi
- Telegram API hata yönetimi geliştirildi
- Grup üye listesi güncellemelerindeki hatalar düzeltildi

## [1.0.0] - 2023-08-05

### İlk Sürüm
- Temel Telegram bot fonksiyonları
- Grup mesajlaşma özellikleri
- Zamanlanmış mesajlar
- Otomatik grup üyeliği yönetimi
