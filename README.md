# MVP SaaS Çözümü: Telegram Marketing Suite

## 📢 Yeni: SaaS Çözümü Artık Hazır!

Telegram Marketing Suite artık çoklu hesap desteğiyle SaaS (Software as a Service) modelinde sizlere sunuluyor! Her müşteriye özel ayarlanmış, izole bir ortamda çalışan, hızlı kuruluma sahip çözümümüzle tanışın.

### 🚀 SaaS Avantajları

- **Hızlı Başlangıç**: 5 dakika içinde kurulum ve kullanıma hazır
- **Çoklu Hesap**: Tek pakette 3 farklı Telegram hesabı desteği
- **İzole Ortam**: Her müşteri için ayrı Docker container ve veritabanı
- **Aylık Abonelik**: Yüksek ilk yatırım maliyeti olmadan başlayın
- **7/24 Destek**: Teknik ekibimizden sürekli destek

### 📋 Kullanım Senaryoları

1. **Pazarlama Ekipleri**: Telegram gruplarında markanızı tanıtın
2. **Topluluk Yöneticileri**: Binlerce kullanıcıyla etkileşimde kalın
3. **E-ticaret İşletmeleri**: Ürünlerinizi doğrudan potansiyel müşterilere tanıtın
4. **İçerik Üreticileri**: İçeriklerinizi daha geniş kitlelere ulaştırın
5. **Affiliate Pazarlamacıları**: Komisyon bazlı ürünlerin tanıtımını yapın

### 🛠️ Teknik Mimari

Telegram Marketing Suite, modüler bir servis mimarisi üzerine kurulmuştur:

- **UserService**: Kullanıcı yönetimi ve veritabanı işlemleri
- **GroupService**: Grup mesajlaşma ve yönetim
- **DirectMessageService**: Özel mesajlaşma ve otomatik yanıtlar
- **InviteService**: Kullanıcılara grup davetleri gönderme
- **AnnouncementService**: Gruplarda duyuru ve tanıtım mesajları
- **MessageService**: Merkezi mesaj gönderim servisi
- **PromoService**: Tanıtım kampanyaları yönetimi
- **GptService**: Yapay zeka entegrasyonu
- **AnalyticsService**: Detaylı grup ve kullanıcı etkileşim analizi (YENİ)
- **ErrorService**: Kategori bazlı hata izleme ve raporlama (YENİ)

Tüm servisler, merkezi bir ServiceManager tarafından koordine edilmekte ve PostgreSQL veritabanı desteğiyle çalışmaktadır.

### 💼 Paketler ve Fiyatlandırma

| Özellik | Başlangıç | Profesyonel | Kurumsal |
|---------|-----------|-------------|----------|
| Hesap Sayısı | 1 | 2 | 3 |
| Aylık Mesaj Limiti | 10,000 | 50,000 | Sınırsız |
| Grup Sayısı | 20 | 100 | Sınırsız |
| Özel Şablonlar | 5 | 20 | Sınırsız |
| Analitik | Temel | Gelişmiş | Premium |
| Öncelikli Destek | ❌ | ✅ | ✅ |
| Özel Geliştirmeler | ❌ | ❌ | ✅ |
| **Aylık Fiyat** | **₺499** | **₺999** | **₺1999** |

### 🛒 Hemen Başlamak İçin

1. [satış@siyahkare.com](mailto:satış@siyahkare.com) adresine mail atın
2. Size özel oluşturulan Docker kurulum dosyalarını alın
3. Kurulum kılavuzunu takip ederek 5 dakikada sistemi kurun
4. Hesap bilgilerinizi girerek hemen kullanmaya başlayın

### 🔜 Yakında Gelecek Özellikler (v4.0)

- **Yapay Zeka Asistanı**: GPT ile otomatik mesaj üretimi ve analizi
- **Tam Otomatik Satış**: Kullanıcılarla etkileşime geçen satış botları
- **İleri Analitik**: Detaylı kullanıcı davranışı ve grup analizi
- **Web Arayüzü**: Tarayıcı üzerinden tüm sistemi yönetme

### 📦 Sistem Gereksinimleri

- Docker ve Docker Compose
- 2GB RAM (minimum)
- 20GB Disk Alanı
- Internet Bağlantısı
- PostgreSQL 13+

## Veritabanı Optimizasyon ve Performans İyileştirmeleri

Telegram botundaki veritabanı performansını artırmak ve PostgreSQL geçişini tamamlamak için bir dizi iyileştirme yapılmıştır:

### PostgreSQL Bağlantı Yönetimi
- **Connection Pooling**: Bağlantı havuzu ile çoklu bağlantı yönetimi ve kaynakların verimli kullanımı sağlandı.
- **SQLAlchemy Entegrasyonu**: Hem senkron hem asenkron SQLAlchemy desteği ile ORM kullanımı.
- **Transaction Yönetimi**: İşlem bütünlüğünü korumak için gelişmiş transaction mekanizmaları.

### Veritabanı Şema İyileştirmeleri
- **BigInteger Dönüşümü**: Telegram ID'lerinin taşması sorununu çözmek için tüm ID alanları BigInteger'a dönüştürüldü.
- **Unique Constraint'ler**: Veri bütünlüğünü korumak için gerekli kısıtlamaların eklenmesi.
- **İndeksleme Stratejisi**: Performansı artırmak için özelleştirilmiş indeksler ve kompozit indeksler oluşturuldu.

### Servis Mimarisi İyileştirmeleri
- **Event-Tabanlı Mimari**: Servisler arası iletişim için EventService ve EventBus eklendi.
- **Servis Bağımlılık Yönetimi**: Servislerin bağımlılıklarını ve çalışma sırasını yöneten ServiceManager.
- **Servis Yaşam Döngüsü**: Servis başlatma, durdurma ve hata durumları için kapsamlı yönetim.

### Veritabanı Bakım ve İzleme
- **optimize_database.py**: Veritabanını optimize etmek için özel bakım betiği.
- **Performans İzleme**: Yavaş sorguları tespit etme ve indeks kullanımını analiz etme araçları.
- **Düzenli Bakım**: VACUUM, ANALYZE ve REINDEX işlemleri için otomatik betikler.

## Grup Analitik Sistemi (YENİ)

v3.6.0 ile eklenen Grup Analitik Sistemi, Telegram gruplarınızdaki aktiviteleri derinlemesine izlemenizi ve anlamanızı sağlar. Bu sistem, pazarlama stratejilerinizi veri odaklı yönlendirmenize ve grup performansını artırmanıza yardımcı olur.

### Temel Analitik Özellikleri
- **Grup Performans Metrikleri**: Mesaj sayısı, üye sayısı, aktif kullanıcı sayısı, etkileşim oranı, büyüme oranı
- **Trend Analizi**: Grupların zaman içindeki performans değişimlerini gösteren grafik verileri
- **Top Listeler**: En aktif gruplar, en hızlı büyüyen gruplar, en yüksek etkileşimli gruplar
- **İnaktif Grup Tespiti**: Belirli bir süre boyunca düşük aktivite gösteren grupları belirleme

### Kullanıcı Analizi
- **En Aktif Kullanıcılar**: Gruplarda en çok mesaj gönderen ve etkileşimde bulunan kullanıcılar
- **Kullanıcı Etkileşim Profilleri**: Kullanıcıların hangi gruplarda, ne zaman, hangi içerik türleriyle etkileşime girdiği
- **Katılım ve Ayrılma Analizi**: Kullanıcıların gruplara katılma ve ayrılma desenlerinin analizi

### Raporlama ve Dışa Aktarım
- **Haftalık Grup Raporları**: Her grup için veya tüm gruplar için otomatik, detaylı haftalık raporlar
- **CSV ve JSON Dışa Aktarım**: Analitik verilerinin CSV ve JSON formatlarında dışa aktarımı
- **Mesaj Türü Analizi**: Metin, medya, bağlantı gibi farklı mesaj türlerinin dağılımı
- **Zamansal Analiz**: Günün saati ve haftanın günü bazında etkileşim yoğunluğu

### Kullanım Örnekleri

Grup analitik verileri almak için:
```python
from bot.services.analytics_service import AnalyticsService

# Analitik servisi örneği oluştur
analytics_service = AnalyticsService()

# Belirli bir grup için analitik verilerini al
group_analytics = await analytics_service.get_group_analytics(group_id=123456789, days=30)

# En aktif grupları listele
top_active_groups = await analytics_service.get_top_active_groups(limit=10)

# En aktif kullanıcıları bul
active_users = await analytics_service.get_most_interactive_users(group_id=123456789, limit=20)

# Grup aktivite trendlerini analiz et
trends = await analytics_service.get_group_activity_trends(group_id=123456789, days=60)

# Haftalık rapor oluştur
weekly_report = await analytics_service.generate_weekly_report(group_id=123456789)

# Analitik verilerini dışa aktar
export_file = await analytics_service.export_analytics(group_id=123456789, format="json")
```

## Gelişmiş Hata İzleme Sistemi (YENİ)

v3.6.0 ile eklenen Gelişmiş Hata İzleme Sistemi, uygulamanın daha stabil çalışmasını sağlayacak, sorunları daha hızlı tespit etmenize ve çözmenize yardımcı olacak bir altyapı sunmaktadır.

### Kategori Bazlı Hata Sınıflandırma
- **Veritabanı Hataları**: SQL, bağlantı, transaction vb. hatalar
- **Telegram API Hataları**: API limitleri, flood wait, yetkilendirme sorunları
- **Ağ Hataları**: Bağlantı zaman aşımı, socket problemleri
- **Genel Hatalar**: Diğer tüm uygulama hataları

### Gelişmiş İzleme ve Raporlama
- **Otomatik Kategorizasyon**: Hata mesajlarını ve yığın izlerini analiz ederek otomatik sınıflandırma
- **Kategori Bazlı Eşikler**: Her hata kategorisi için farklı izleme eşikleri ve süreleri
- **Gelişmiş Kayıt Tutma**: Kategoriye göre ayrılmış log dosyaları ve detaylı JSON formatında kayıt
- **Çözüm Takibi**: Hataların çözüm durumlarını izleme ve raporlama

### Uyarı ve Bildirim Sistemi
- **Eşik Bazlı Uyarılar**: Belirli bir sürede çok fazla hata oluştuğunda otomatik uyarılar
- **Kategori Özelinde Bildirimler**: Hata kategorisine göre özelleştirilmiş bildirimler
- **Periyodik Raporlar**: Hata eğilimleri ve sorun noktaları hakkında otomatik raporlar

### İstatistik ve Analiz
- **Hata Eğilimleri**: Zaman içindeki hata dağılımlarını ve eğilimlerini analiz etme
- **Kategori İstatistikleri**: Kategori, şiddet ve kaynağa göre hata analizleri
- **Etki Analizi**: Hataların kullanıcı deneyimine etkisini ölçme

### Kullanım Örnekleri

Hata izleme sistemi kullanımı:
```python
from bot.services.error_service import ErrorService

# Hata izleme servisi örneği oluştur
error_service = ErrorService()

# Bir hatayı kaydet
error_id = await error_service.log_error(
    error_type="ConnectionError",
    message="Veritabanına bağlanılamadı",
    source="database_service",
    severity="ERROR",
    # Kategori belirtmezseniz otomatik tespit edilir
)

# Kategori bazlı hata istatistiklerini al
stats = await error_service.get_category_stats(hours=24)

# Belirli bir kategorideki hataları listele
db_errors = await error_service.get_errors_by_category(
    category="DATABASE",
    include_resolved=False,
    limit=50
)

# Bir hatayı çözüldü olarak işaretle
await error_service.resolve_error(
    error_id=12345,
    resolution_info="Veritabanı bağlantı havuzu genişletildi"
)
```

### Veritabanı Optimizasyon ve Performans İyileştirmeleri Kullanım Örnekleri

Veritabanı optimizasyonu için:
```bash
# Basit optimizasyon (ANALYZE)
python optimize_database.py --analyze-only

# Tam optimizasyon (VACUUM, REINDEX, ANALYZE)
python optimize_database.py --vacuum-full --reindex-all

# BigInt kontrolü ve dönüşümü
python optimize_database.py --check-bigint

# Veritabanı kısıtlamalarını kontrol et
python optimize_database.py --add-constraints
```

PostgreSQL bağlantı havuzu kullanımı:
```python
from database.db_connection import get_db_pool

# Bağlantı havuzunu al
db_pool = get_db_pool(min_connections=5, max_connections=20)

# SQL sorgusu çalıştır
result = db_pool.execute("SELECT * FROM users WHERE is_active = %s", (True,), fetchall=True)

# SQLAlchemy session kullan
with db_pool.get_session() as session:
    users = session.query(User).filter(User.is_active == True).all()
```

Event-tabanlı mimari kullanımı:
```python
from bot.services.event_service import EventService, on_event

# Event dinleyici
@on_event("user_joined", service_name="user_service")
async def handle_user_joined(self, event):
    user_data = event.data
    # Kullanıcı işlemlerini gerçekleştir
    
# Event yayınlama
await event_service.emit("message_received", 
                        data={"user_id": user_id, "message": message},
                        source="message_service")
```