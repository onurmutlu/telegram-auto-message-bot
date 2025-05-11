# Telegram Bot Web Panel - E2E Testleri

Bu dizin, Telegram Bot Web Panel'in End-to-End (E2E) testlerini içerir. Testler, [Playwright](https://playwright.dev/) kullanılarak oluşturulmuştur.

## Kurulum

1. Bu dizinde Node.js bağımlılıklarını yükleyin:

```bash
cd e2e
npm install
```

2. Playwright tarayıcılarını yükleyin:

```bash
npx playwright install
```

## Testleri Çalıştırma

Tüm testleri çalıştırmak için:

```bash
npm test
```

UI modunda testleri çalıştırmak için:

```bash
npm run test:ui
```

Tarayıcıyı görünür şekilde çalıştırmak için:

```bash
npm run test:headed
```

Test raporunu görüntülemek için:

```bash
npm run report
```

## Test Açıklamaları

Testler şu senaryoları kapsar:

1. **Ayarlar Sayfası Testi**:
   - `/settings` sayfasına git
   - API ID, API Hash ve Bot Token alanlarını doldur
   - "Kaydet" butonuna tıkla
   - Başarı mesajını doğrula

2. **Mesaj Ekleme Testi**:
   - `/add-message` sayfasına git
   - Mesaj içeriği ve saat gir
   - "Ekle" butonuna tıkla
   - Dashboard'da yeni mesajı kontrol et

3. **Log Sayfası Testi**:
   - `/logs` sayfasına git
   - En az bir log öğesinin görünür olduğunu doğrula

4. **Dashboard CRUD İşlemleri Testi**:
   - Yeni bir test mesajı oluştur
   - Mesajı düzenle
   - Mesajı sil

## Yapılandırma

Testlerin yapılandırması `playwright.config.ts` dosyasında tanımlanmıştır. Bu dosya şunları içerir:

- Test dizini ve zaman aşımı ayarları
- Tarayıcı yapılandırması
- Ekran görüntüsü ve video kayıt ayarları
- Farklı tarayıcılar için test projesi tanımları
- Yerel geliştirme sunucusu yapılandırması

## Notlar

- Testler, backend API'nin ve frontend'in düzgün çalıştığını varsayar.
- Testleri çalıştırmadan önce web panel'in localhost:3000 üzerinde çalıştığından emin olun.
- Test verilerinin diğer testlerle çakışmamasına dikkat edin. 