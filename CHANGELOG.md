# CHANGELOG.md

# Telegram Auto Message Bot - Değişiklik Günlüğü

Bu belge, Telegram Auto Message Bot'un tüm önemli değişikliklerini içerir.

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

### İyileştirmeler
- Veritabanı performans optimizasyonları
- Hata ayıklama için günlük sistemi güncellendi
- Daha ayrıntılı konsol çıktıları
- Grup gönderim algoritması iyileştirildi
- Bellek kullanımı ve önbellek temizleme mekanizmaları
- Güvenlik için hata grupları veritabanında saklanıyor
- Son davet zamanına dayalı akıllı kullanıcı davet filtresi (4 saat aralıklı)

### Düzeltmeler
- Veritabanı şema güncelleme hatası düzeltildi
- Tekrarlanan kullanıcı aktivitesi bildirimlerini engelleyen değişiklikler
- Hata veren grupları tespit edip dışlama mekanizması iyileştirildi
- Geçersiz veritabanı durumlarını tespit edip kurtarma işlevi
- Çoklu ortam (Windows/Mac/Linux) desteği için konsolda düzeltmeler
- Güvenli kapatma mekanizması geliştirildi

### Veritabanı Değişiklikleri
- `error_groups` tablosu eklendi
- `users` tablosuna `blocked` ve `is_admin` alanları eklendi
- Veritabanı indeks yapısı iyileştirildi

### Dokümantasyon
- README.md güncellendi
- Dosya yapısı dokümantasyonu eklendi
- Lisans belgeleri güncellendi
- Bot komutları için yardım bilgileri eklendi

### Teknik Değişiklikler
- Telethon istemcisine yeni metadata bilgileri eklendi
- Logging yapısı modülerleştirildi
- Asenkron yapı iyileştirildi
- Periyodik temizleme görevleri eklendi
- Veritabanı yedekleme sistemi eklendi

## [3.0.0] - 2025-01-15

### İlk Sürüm
- Temel bot yapısı
- Grup mesaj gönderme
- Kullanıcı takibi ve davet sistemi
- Basit komut satırı arayüzü