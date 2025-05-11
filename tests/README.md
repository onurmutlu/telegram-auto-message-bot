# Telegram Bot API Testleri

Bu dizin, Telegram Bot backend API endpoint'lerinin testlerini içerir. Testler [pytest](https://docs.pytest.org/) ve [pytest-asyncio](https://pytest-asyncio.readthedocs.io/) kullanılarak oluşturulmuştur.

## Kurulum

1. Python bağımlılıklarını yükleyin:

```bash
pip install -r requirements.txt
```

2. Test bağımlılıklarını yükleyin:

```bash
pip install pytest pytest-asyncio pytest-cov httpx
```

## Testleri Çalıştırma

Tüm testleri çalıştırmak için:

```bash
pytest
```

Belirli bir test dosyasını çalıştırmak için:

```bash
pytest tests/test_backend.py
```

Ayrıntılı çıktı ile çalıştırmak için:

```bash
pytest -v tests/test_backend.py
```

Kod kapsama raporu ile çalıştırmak için:

```bash
pytest --cov=app tests/
```

## Test Açıklamaları

Testler şu endpoint'leri kapsar:

1. **GET /api/logs**:
   - Log dosyası varken doğru JSON döndürüldüğünü doğrular
   - Log dosyası yokken "Henüz log yok." mesajının döndürüldüğünü doğrular

2. **POST /api/save-settings**:
   - Geçerli ayarların doğru şekilde kaydedildiğini doğrular
   - Geçersiz ayarlar gönderildiğinde 422 hatası döndürüldüğünü doğrular

3. **Mesaj CRUD İşlemleri**:
   - **POST /api/messages**: Yeni mesaj oluşturma
   - **GET /api/messages**: Mesaj listesini alma
   - **GET /api/messages/{id}**: Belirli bir mesajı görüntüleme
   - **PUT /api/messages/{id}**: Mesaj güncelleme
   - **DELETE /api/messages/{id}**: Mesaj silme

## Fixtures

- **temp_dir**: Test için geçici bir dizin oluşturur ve test sonrası temizler
- **setup_message_db**: Mesaj CRUD testleri için veritabanını hazırlar

## Notlar

- Testler, uygulamanın doğru şekilde yapılandırıldığını varsayar.
- Veritabanı bağlantısı gerektiren testler için test veritabanı kullanılması önerilir.
- Test ortamında hassas verilerin bulunmamasına dikkat edin. 