# CHANGELOG.md

# Telegram Auto Message Bot - Değişiklik Günlüğü

Bu belge, Telegram Auto Message Bot'un tüm önemli değişikliklerini içerir.

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