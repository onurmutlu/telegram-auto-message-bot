CLI Komutları:
d: Demografik analiz raporlarını görüntüleyin
m: Veri madenciliği işlemlerini yönetin
t: Hedefli kampanya araçlarını kullanın

>
Kullanım İpuçları
Veri Madenciliği (m komutu)
İlk olarak "Tam veri toplama başlat" seçeneğini kullanarak başlangıç verileri toplayın
Düzenli olarak "Artırımlı veri toplama başlat" ile yeni verileri güncelleyin
"Kullanıcı segmentlerini göster" ile toplanan verilerin analiz sonuçlarını kontrol edin
Kampanya Yönetimi (t komutu)
"Yeni kampanya oluştur" ile hedef kitlenize göre kampanya tasarlayın
"Kampanya gönder" ile seçtiğiniz segmente özel mesajlar gönderin
Daha büyük gruplar için batch_size değerini daha küçük tutun (10-20)
Demografik Analiz (d komutu)
Kullanıcılarınızın dil dağılımı, aktivite düzeyleri ve grup üyelikleri hakkında grafik raporlar alın
"Grafik olarak görmek ister misiniz?" sorusuna "e" yanıtı vererek görsel analiz yapın
Olası Sorunlar ve Çözümleri
SQLite Kilitlenme Hataları: Veritabanı WAL modunda çalışmalı (main.py içinde ayarlanmış)

RuntimeWarning: coroutine was never awaited:

Bunlar genellikle asenkron fonksiyonların await anahtar kelimesi olmadan çağrılmasından kaynaklanır
Düzeltmelerimizde bu sorun ele alındı ancak yine görürseniz, sorunlu satırdaki fonksiyon çağrısının önüne await eklenmeli
Veritabanı tablolarıyla ilgili hatalar: İlk çalıştırmada bazı tablolar eksik olabilir

Çözüm: Bot çalıştırıldıktan sonra durdurun, hata mesajlarını inceleyin ve tekrar başlatın
İlk çalıştırmada tablolar otomatik oluşacaktır
"No module named" hataları: Eksik bağımlılıklar için pip ile ilgili modülleri yükleyin

Bot güncellemeleriniz sorunsuz çalışmalı ve veritabanı şemaları ilk çalıştırmada otomatik olarak güncellenecektir. Yardıma ihtiyaç duyarsanız CLI arayüzünden "h" komutu ile komut listesini görebilirsiniz.