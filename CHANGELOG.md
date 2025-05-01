# Changelog

## v3.6.1 (2023-06-xx)

### Düzeltilen

- **ServiceManager** stop_services metodu eklendi
  - CLI arayüzünde servisleri durdurma hatası giderildi
  - Servis kapatma işlemlerinde oluşan hatalar giderildi

- **GroupHandler** send_message metodu eklendi
  - Gruplara mesaj gönderme işlevi düzeltildi
  - Grup varlığı kontrolü eklendi
  - Hata yakalama geliştirildi

## v3.6.0 (2023-06-xx)

### Eklenen

- **Grup Analitik Sistemi** eklendi
  - Grup aktivite ve etkileşim metrikleri
  - En aktif gruplar, en hızlı büyüyen gruplar ve en etkileşimli grupları tespit etme
  - Kullanıcı etkileşim analizi ve en aktif kullanıcıları tespit etme
  - Haftalık detaylı rapor oluşturma ve CSV/JSON formatlarında dışa aktarma

- **Gelişmiş Hata İzleme** iyileştirmeleri
  - Hataları kategorilere ayıran (DATABASE, NETWORK, TELEGRAM_API, GENERAL) sistem
  - Her kategori için özel eşikler ve izleme pencereleri 
  - Kategori bazlı log dosyaları ve JSON formatında detaylı kayıt
  - Otomatik hata kategorizasyonu ve istatistik raporlama

- **Config Adapter Sistemi** eklendi
  - Farklı yapılardaki config nesnelerini uyumlu hale getiren adaptör
  - Dict yapısındaki, get_setting metodlu veya get metodlu config nesneleri ile uyumlu
  - İç içe yapıya sahip konfigürasyon değerlerini nokta notasyonu ile çekebilme

- **CLI arayüzüne** yeni komutlar eklendi
  - 'a' komutu: Grup analitik raporları ve istatistikleri 
  - 'e' komutu: Hata izleme ve kategori bazlı hata yönetimi

### Düzeltilen

- Config nesnesi ile ilgili çeşitli hatalar düzeltildi
- `BaseService` sınıfının config kullanımı iyileştirildi
- Servis iletişim sorunları çözüldü
- Veritabanı bağlantı sorunları çözüldü

### Geliştirilen

- Servisler arası iletişim ve entegrasyon geliştirildi
- Telemetri ve izleme kabiliyetleri artırıldı
- Performans ve bellek kullanımı iyileştirildi
- Test kapsamı genişletildi
