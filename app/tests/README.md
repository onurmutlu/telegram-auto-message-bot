# Telegram Bot Test Modülleri

Bu dizin, Telegram Bot Platform'un test modüllerini içerir.

## Test Dosyaları

Bu dizinde aşağıdaki test dosyaları bulunur:

1. `test_services.py` - Servis bileşenlerinin testleri
2. `test_admin_groups.py` - Admin grupları ile ilgili testler
3. `test_analytics_error.py` - Analitik ve hata işleme testleri
4. `test_config_adapter.py` - Yapılandırma adaptörü testleri
5. `test_group_handler.py` - Grup işleyici testleri
6. `test_message.py` - Mesajlaşma testleri
7. `test_pg_connection.py` - PostgreSQL bağlantı testleri
8. `test_postgres.py` - Postgres veritabanı testleri
9. `test_service_loader.py` - Servis yükleyici testleri

## Kullanım

Tüm testleri çalıştırmak için:

```bash
cd /app
python -m unittest discover -s tests
```

Belirli bir test dosyasını çalıştırmak için:

```bash
python -m app.tests.test_services
```

## Test Yapısı

Her test dosyası, belirli bir fonksiyonalite kümesini test eder. Testler genellikle 
unittest çerçevesi kullanılarak yazılmıştır, ancak bazı testler için doğrudan 
assert ifadeleri de kullanılmıştır.

Yeni testler eklerken aşağıdaki yapıya uyunuz:

1. Birim testleri için TestCase sınıfları kullanın
2. Entegrasyon testleri için ayrı modüller oluşturun
3. Mock nesnelerini kullanarak dış bağımlılıkları simüle edin
4. Her testin amacını açıklayan docstring ekleyin 