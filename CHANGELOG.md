# CHANGELOG.md

# Telegram Auto Message Bot - Değişiklik Günlüğü

Bu belge, Telegram Auto Message Bot'un tüm önemli değişikliklerini içerir.

## [3.4.1] - 2025-04-02

### Eklenen Özellikler
- `UserService` sınıfı ile kullanıcı yönetiminin servis katmanına taşınması
- `ServiceFactory` ve `ServiceManager` sınıfları ile merkezi servis yönetimi
- Bot durum izleme paneli (`monitor_dashboard.py`) eklendi
- Test mesajı gönderme aracı (`send_test_message.py`) eklendi
- `check_groups.py` ile erişilebilir grupların testi eklendi
- Bot'a debug modu eklendi: DEBUG=true ortam değişkeni ile aktifleşir

### İyileştirmeler
- Servis katmanı yapısı güçlendirildi ve daha modüler hale getirildi
- Projenin yapısı düzenlendi, yardımcı araçlar tools/ dizinine taşındı
- TelegramBot.enable_debug_mode() metodu ile detaylı debug çıktıları
- Renkli terminal çıktıları ve tablo formatlaması iyileştirildi
- ServiceManager ile servislerin güvenli başlatılması ve durdurulması sağlandı
- Bot status komutu ile anlık servis durumları görüntülenebilir

### Düzeltmeler
- `'Config' object has no attribute 'API_ID'` hatası çözüldü
- Property çakışmaları nedeniyle oluşan `can't set attribute` hatası düzeltildi
- `NoModuleFoundError` hatalarını çözmek için import yolları düzeltildi
- `requests` ve `colorama` bağımlılıkları requirements.txt'ye eklendi
- Sonsuz Config yapılandırma döngüsü hatası giderildi
- Debug botu düzgün çalışacak şekilde düzeltildi
- Birden fazla main.py arasındaki çakışmalar çözüldü
- Proje kök dizini import yoluna eklenerek modül çözünürlüğü düzeltildi

### Yeniden Yapılandırma
- Eski ve kullanılmayan legacy_handlers klasörü projeden temizlendi
- Config import yapısı düzenlendi ve tutarlı hale getirildi
- settings.py ve config.py arasındaki ilişki yeniden yapılandırıldı
- API bilgilerine hem büyük harfli (API_ID) hem de küçük harfli (api_id) şekilde erişim sağlandı
- Bot başlatma mantığı refactor edildi

### Dokümantasyon
- Bot durum izleme paneli için kapsamlı yardım eklendi
- README.md güncellendi, yeni araçlar ve servis mimarisi eklendi
- Kod içi açıklamalar daha detaylı ve tutarlı hale getirildi

## [3.4.0] - 2025-04-01

### Eklenen Özellikler
- Yeni test modülü: `test_run_tests.py` ile test sürecinin kendisi de test edilebilir hale getirildi.
- Gelişmiş raporlama sistemi ve renkli test çıktıları.
- Zaman aşımı kontrolü ve otomatik test durdurma mekanizması.
- Test sonuçlarını JSON formatında saklama ve analiz etme desteği.
- Kolay test çalıştırılması için yeni `run_tests.py` betiği eklendi.
- Zaman damgalı ayrıntılı test logları.
- `debug_bot` modülü ile ayrı bir python-telegram-bot tabanlı hata izleme botu entegrasyonu.
- `monitor.py` ile ana bot ve debug botun eş zamanlı başlatılması.
- `TelegramBot.set_monitor_bot()` metodu ile ana bot ve debug bot arasında bağlantı kurma.
- `ErrorHandler.log_error()` metodu ile hataları hem loglama hem de debug bota gönderme.

### İyileştirmeler
- Kod yapısının modülerleştirilmesi: servis katmanı uygulandı.
- `DirectMessageService`, `MessageService` ve `ReplyService` sınıfları ayrı modüllere taşındı.
- Test süitlerinin çalışma zamanı performansı iyileştirildi.
- Log formatları standardize edildi ve tüm formatlarda tutarlılık sağlandı.
- Kod kalitesi iyileştirmeleri: alt modüllere ayrılarak okunabilirlik artırıldı.
- Test kapsamı %80'in üzerine çıkarıldı.
- Legacy handlers yeni yapıya migrate edildi ve standartlaştırıldı.
- `BotTasks` sınıfı ile görev yönetimi merkezileştirildi.
- `TelegramBot` sınıfı merkezi bir yapıya kavuşturuldu ve `BaseBot` ile birleştirildi.
- Şablon yükleme ve yönetimi iyileştirildi.
- Hata yönetimi ve `ErrorHandler` sınıfı güncellendi.
- Bot başlatma süreci iyileştirildi ve olay dinleme süreçleri düzenlendi.

### Refactor
- `core.py` sınıfı refactor edildi, görevler `tasks.py` dosyasına taşındı.
- Sinyal işleme iyileştirildi ve tek bir yerde toplandı.
- Kapanış işlemleri geliştirildi ve güvenli kapatma sağlandı.
- Logger formatları standardize edildi ve `levellevelname` hatası düzeltildi.
- Servis sınıfları arasında tutarlı bir arayüz oluşturuldu.
- Bağımlılık enjeksiyonu ile test edilebilirlik artırıldı.
- Asenkron işlemler için tutarlı bir model uygulandı.
- `handlers` ve `services` katmanları arasındaki sorumluluklar netleştirildi.
- `handlers/handlers.py` ve `handlers/message_handler.py` çakışması giderildi.
- Grup mesajı gönderme işlevi `group_handler.py` içinde birleştirildi.

### Düzeltmeler
- `TestRunTests` sınıfındaki mock kullanım hataları düzeltildi.
- Logger formatlarındaki tutarsızlıklar giderildi.
- Testlerde çıkan 'NoneType' hatalarına karşı güvenli kod yapısı.
- Test sonuçlarını depolama ve raporlama sorunları çözüldü.
- Subprocess çağrıları daha güvenli hale getirildi.
- Zaman aşımı ve `KeyboardInterrupt` durumlarında kaynaklar düzgün temizleniyor.
- `handlers` klasörü yapısı düzeltildi ve gereksiz dosyalar temizlendi.
- `ImportError: cannot import name 'MessageHandlers' from 'bot.handlers'` hatası giderildi.

### Yeniden Yapılandırma
- Legacy handlers klasöründeki dosyalar yeni yapıya taşındı.
- `handlers` klasörü yeniden organize edildi.
- `migration_report.md` ile taşıma işlemleri belgelendi.
- Bot yapısı `ROADMAP340.md`'de belirtilen ilkelere göre yeniden düzenlendi.
- `debug_bot` modülü ayrı bir klasöre taşındı ve namespace çakışmaları önlendi.

### Cleanup
- Gereksiz dosyalar temizlendi.
- Kod yapısı düzenlendi ve modüler hale getirildi.
- Eski `.bak` uzantılı dosyalar temizlendi.
- Tutarsız yapılandırma formatları standartlaştırıldı.
- Daha iyi tip kontrolü için type hinting kullanımı yaygınlaştırıldı.
- Kodun okunabilirliği artırıldı.
- Gereksiz servis sınıfları kaldırıldı ve işlevler handler sınıflarına taşındı.

### Dokümantasyon
- `ROADMAP340.md` ile gelecek geliştirmelerin yol haritası eklendi.
- Kapsamlı test dokümantasyonu eklendi.
- Proje yapısı ve mimarisi belgelendi.
- Test koşulları ve test sonuçlarının yorumlanması için kılavuz eklendi.
- `README.md` dosyası güncellendi ve `debug_bot` modülü hakkında bilgi eklendi.
- Kod içi docstringler güncellendi ve eksik açıklamalar tamamlandı.

## [3.3.1] - 2025-03-26

### Düzeltmeler
- Hata gruplarını yönetirken `retry_after` değişkeninin tipine göre güvenli işlem yapma
- `strftime()` metodu hatası giderildi: String türündeki tarih değerleri için güvenli kontrol
- Test sistemi güncellendi ve daha esnek hale getirildi
- GitHub CI/CD entegrasyonu ile otomatik test çalıştırma

## [3.3.0] - 2025-03-28

### Eklenen Özellikler
- Kapsamlı test altyapısı ve pytest entegrasyonu
- Veritabanı ve config testleri için fixtures
- Mock Telegram Client ile izole bot testleri
- GitHub CI/CD entegrasyonu ile otomatik test çalıştırma
- Hata yönetim sistemlerinin test edilebilirliğinin arttırılması
- Makefile ile kolay test çalıştırma ve geliştirme desteği

### İyileştirmeler
- Logger formatı test edilebilirlik için refactored edildi
- Tekrarlanan hataların daha efektif filtrelenmesi için iyileştirmeler
- Bot bileşenlerinin tümü için birim testler eklendi
- Her bir modül için izole testlerle hataların hızlı tespiti
- JSON dosya formatı kontrolü ve doğrulama testleri
- Esnek test yapısı ile mevcut kodu bozmadan test ekleme

### Düzeltmeler
- Test ortamında keşfedilen çeşitli edge case hataları giderildi
- Zaman aşımı sorunlarına karşı daha güvenli kod
- Telethon API exception handling iyileştirildi
- JSON parsing hataları ve format kontrolü geliştirildi
- Farklı ortamlarda test edilebilirlik sağlandı

## [3.2.0] - 2025-03-26

### Eklenen Özellikler
- Acil durum kapatma sistemi (`_emergency_shutdown`) ile kesin kapatma garantisi
- Telethon log mesajları için akıllı gösterim sistemi
- Grup hatalarını görüntüleme ekranında zaman aşımlı seçim mekanizması
- Hata mesajları için sayaç sistemi ve filtreleme
- Daha hızlı ve kesintiye duyarlı duraklatma kontrolü
- Zamanlayıcı ile zorla kapatma özelliği (10 saniye timeout)
- Kaynak temizleme ve veritabanı bağlantısı kapatma iyileştirmeleri

### İyileştirmeler
- Daha güvenilir bot kapatma mekanizması (çoklu katman güvenliği)
- Tekrarlanan log mesajlarını bastıran filtreleme sistemi
- Grup hata tablosu formatlama ve kolon hizalama iyileştirmeleri
- Yapılandırma dosyası eksikse otomatik oluşturma özelliği
- OS düzeyinde zorla program sonlandırma garantisi
- Kaynakları temizleme ve bellek yönetimi iyileştirmeleri
- Log hatalarına karşı dayanıklı formatlar (levellevel hatası giderildi)

### Düzeltmeler
- `GetDialogsRequest flood wait` mesajlarının tekrarlanması sorunu çözüldü
- Kullanıcı takip hatalarının ('user_activity_new', 'user_activity_exists') düzgün işlenmesi
- Kapatma sırasında thread'lerin takılı kalması engellendi
- Ctrl+C sonrası programın askıda kalma sorunu çözüldü
- Tablo formatının düzgün görünmemesi sorunu çözüldü
- Duraklatma komutundaki (`p`) gecikme sorunu giderildi
- Config dosyası bulunamama uyarıları düzeltildi
- Log formatter'daki 'levellevel' hatası düzeltildi

## [3.1.0] - 2025-03-25

### Eklenen Özellikler
- Session dosyalarını session/ klasöründe saklama desteği
- Grup hata yönetimi ve 8 saatlik erteleme sistemi
- Kullanıcı aktivitesi tekrarlama engelleme
- Debug modu ile gelişmiş loglama
- Detaylı JSON formatında loglar
- Komut satırı argüman desteği (`--debug`, `--reset-errors`, `--optimize-db`, `--env`)
- Kullanıcı dostu konsol arayüzü ve renkli çıktılar
- Oturum sonunda detaylı istatistik raporu
- Ticari lisans ve telif hakkı bildirimleri
- Tabulate kütüphanesi ile formatlı tablo görüntüleme
- Konsol temizleme fonksiyonu (`c` komutu)
- Kullanıcı istatistikleri görüntüleme (`u` komutu)
- Terminal renk desteği otomatik tespit

### İyileştirmeler
- Veritabanı performans optimizasyonları
- Hata ayıklama için günlük sistemi güncellendi
- Daha ayrıntılı konsol çıktıları
- Grup gönderim algoritması iyileştirildi
- Bellek kullanımı ve önbellek temizleme mekanizmaları
- Güvenlik için hata grupları veritabanında saklanıyor
- Son davet zamanına dayalı akıllı kullanıcı davet filtresi (4 saat aralıklı)
- Test altyapısı ve unit test desteği
- Çalışma zamanı monitörü ile performans takibi
- Kod belgelendirmesi ve yorum iyileştirmeleri

### Düzeltmeler
- Veritabanı şema güncelleme hatası düzeltildi
- Tekrarlanan kullanıcı aktivitesi bildirimlerini engelleyen değişiklikler
- Hata veren grupları tespit edip dışlama mekanizması iyileştirildi
- Geçersiz veritabanı durumlarını tespit edip kurtarma işlevi
- Çoklu ortam (Windows/Mac/Linux) desteği için konsolda düzeltmeler
- Güvenli kapatma mekanizması geliştirildi
- SQLite WAL dosyaları .gitignore'a eklendi
- Gereksiz bağımlılıklar requirements.txt dosyasından çıkarıldı
- `utils.logger_setup` import hatası düzeltildi

### Veritabanı Değişiklikleri
- `error_groups` tablosu eklendi
- `users` tablosuna `blocked` ve `is_admin` alanları eklendi
- Veritabanı indeks yapısı iyileştirildi
- Veritabanı otomatik yedekleme sistemi eklendi

### Dokümantasyon
- README.md güncellendi ve test bölümü eklendi
- Dosya yapısı dokümantasyonu güncellendi
- Lisans belgeleri güncellendi
- Bot komutları için yardım bilgileri eklendi
- Komut satırı argümanları belgelendi
- Tarih formatları ISO 8601 standardına uygun hale getirildi

### Teknik Değişiklikler
- Telethon istemcisine yeni metadata bilgileri eklendi
- Logging yapısı modülerleştirildi
- Asenkron yapı iyileştirildi
- Periyodik temizleme görevleri eklendi
- Çalışma zamanı monitörü (runtime monitor) eklendi
- Terminal özellikleri otomatik tespit edildi
- Güvenli hata yakalama ve temizleme mekanizması

## [3.0.0] - 2025-01-15

### İlk Sürüm
- Temel bot yapısı
- Grup mesaj gönderme
- Kullanıcı takibi ve davet sistemi
- Basit komut satırı arayüzü