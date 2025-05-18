# PostgreSQL Geçiş Rehberi (Güncel)

Bu belge, SQLite veritabanından PostgreSQL veritabanına geçiş sürecini açıklamaktadır.

## Hızlı Geçiş Adımları

Tüm geçiş adımlarını tek komutla gerçekleştirmek için:

```bash
make full-migrate
```

Bu komut, aşağıdaki adımları otomatik olarak gerçekleştirir:
1. Çevre değişkenlerini günceller
2. PostgreSQL bağlantısını test eder
3. PostgreSQL tablolarını oluşturur
4. SQLite'dan PostgreSQL'e veri taşıma işlemini başlatır
5. PostgreSQL veritabanı işlemlerini test eder
6. Kullanıcı aktivitelerini günceller

## Detaylı Adımlar

1. **PostgreSQL Kurulumu**

   Eğer kurulu değilse, PostgreSQL veritabanını sisteminize kurun:
   
   ```bash
   # Ubuntu/Debian
   sudo apt-get update
   sudo apt-get install postgresql postgresql-contrib
   
   # macOS (Homebrew)
   brew install postgresql
   ```

2. **Veritabanı Oluşturma**

   PostgreSQL'de telegram_bot veritabanını oluşturun:
   
   ```bash
   sudo -u postgres psql
   
   # PostgreSQL shell içinde:
   CREATE DATABASE telegram_bot;
   CREATE USER botuser WITH PASSWORD 'botpass';
   GRANT ALL PRIVILEGES ON DATABASE telegram_bot TO botuser;
   
   # PostgreSQL 12+ sürümü kullanıyorsanız şema hakları da verin:
   \c telegram_bot
   GRANT ALL ON SCHEMA public TO botuser;
   \q
   ```

3. **.env Dosyasını Güncelleme**

   Makefile ile .env dosyasını otomatik olarak güncelleyebilirsiniz:
   
   ```bash
   make update_env
   ```
   
   Veya manuel olarak aşağıdaki bilgileri .env dosyasına ekleyin:
   
   ```
   # PostgreSQL bağlantı bilgileri
   POSTGRES_HOST=localhost
   POSTGRES_PORT=5432
   POSTGRES_DB=telegram_bot
   POSTGRES_USER=botuser
   POSTGRES_PASSWORD=botpass
   DB_CONNECTION=postgresql://botuser:botpass@localhost:5432/telegram_bot
   ```

4. **PostgreSQL Bağlantısını Test Etme**

   ```bash
   make test_pg_connection
   ```

5. **PostgreSQL Tablolarını Oluşturma**

   ```bash
   make setup_pg
   ```

6. **Veri Taşıma İşlemi**

   SQLite'dan PostgreSQL'e verileri taşıyın:
   
   ```bash
   make migrate
   ```

7. **Veritabanı İşlevselliğini Test Etme**

   ```bash
   make test-pg
   ```

8. **Kullanıcı Aktivite Loglarını Güncelleme**

   ```bash
   make update_user_activities
   ```

9. **Geçiş Sonrası Kontroller**

   Geçişin başarılı olduğunu doğrulamak için veritabanı işlevselliğini test edin:
   
   ```bash
   # PostgreSQL veritabanını kontrol et
   psql -U botuser -h localhost -d telegram_bot
   
   # PostgreSQL shell içinde:
   SELECT COUNT(*) FROM users;
   SELECT COUNT(*) FROM groups;
   SELECT COUNT(*) FROM user_activity_log;
   \q
   ```

## Yapılan Değişiklikler

Bu geçiş sürecinde yapılan değişiklikler:

1. **Kodda PostgreSQL uyumluluğu**
   - `UserDatabase` sınıfı artık otomatik olarak veritabanı tipini tanır
   - SQL sorguları parametreleri (`?` veya `%s`) veritabanı tipine göre otomatik olarak ayarlanır
   - Boolean değerler PostgreSQL için uygun biçime dönüştürülür

2. **Tablo Yapıları**:
   - SQLite'de `TEXT` ve `INTEGER` tipinde alanlar PostgreSQL'de daha spesifik veri tiplerine dönüştürüldü
   - JSON veriler için `JSONB` tipi eklendi
   - Tarih alanları için `TIMESTAMP` tipi kullanıldı
   - İlişkisel veri bütünlüğü için foreign key tanımlamaları eklendi

3. **Indeksleme**:
   - Performans iyileştirmesi için tüm kritik alanlara indeksler eklendi
   - Sorgu hızını artırmak için birleşik indeksler tanımlandı

4. **Veri Taşıma Araçları**:
   - SQLite'dan PostgreSQL'e veri taşımak için kapsamlı bir araç geliştirildi
   - Tarih formatları ve JSON dönüşümü için özel işlevler eklendi

## Performans İyileştirmeleri

PostgreSQL'e geçtikten sonra, veritabanı performansını optimize etmek için:

1. **Düzenli bakım işlemleri**:
   ```sql
   -- İndeksleri analiz et
   ANALYZE user_activity_log;
   
   -- Vakumla temizlik yap
   VACUUM ANALYZE;
   ```

2. **Bağlantı havuzu optimizasyonu**:
   Yoğun kullanım için `db_connection.py` dosyasında bağlantı havuzu boyutunu artırabilirsiniz:
   ```python
   # Örnek bağlantı havuzu boyutunu artırma
   db_manager = DatabaseConnectionManager(pool_size=10)
   ```

## Geriye Dönüş Planı

Eğer PostgreSQL geçişinde sorun yaşarsanız, geçici olarak SQLite kullanmaya geri dönebilirsiniz:

1. `.env` dosyasındaki `DB_CONNECTION` değerini SQLite yoluna geri alın:
   ```
   DB_CONNECTION=sqlite:///data/users.db
   ```

2. Uygulamayı yeniden başlatın.

## Sık Karşılaşılan Sorunlar

1. **PostgreSQL bağlantı hatası**:
   - PostgreSQL servisinin çalıştığından emin olun: `sudo systemctl status postgresql`
   - PostgreSQL kullanıcısı ve parolasını kontrol edin
   - pg_hba.conf dosyasında erişim izinlerini kontrol edin

2. **Veri taşıma hataları**:
   - Tarih formatı sorunları için `sqlite_to_postgres.py` dosyasında tarih dönüşüm kodunu kontrol edin
   - JSON dönüşüm hatası için `json.dumps()`/`json.loads()` çağrılarını doğrulayın

3. **Bağlantı havuzu tükenmesi**:
   - DB_CONNECTION_POOL_SIZE değerini .env dosyasında artırın
   - Bağlantıların kullanım sonrası düzgün şekilde havuza iade edildiğinden emin olun

## İleri Seviye Yapılandırma

1. **Performans için PostgreSQL Ayarları**:
   PostgreSQL yapılandırma dosyasında (postgresql.conf) aşağıdaki değişiklikleri yapabilirsiniz:
   
   ```
   # Bellek ayarları
   shared_buffers = 256MB  # Sistem belleğinin %25'i kadar
   work_mem = 16MB         # Sorgu başına çalışma belleği
   
   # Checkpoint ayarları
   checkpoint_timeout = 15min
   checkpoint_completion_target = 0.9
   
   # Planlayıcı ayarları
   random_page_cost = 1.1  # SSD diskler için
   effective_cache_size = 1GB  # Sistem belleğinin %75'i kadar
   ```

2. **Çoklu İstemci Desteği**:
   PostgreSQL'in çoklu istemci desteğinden faydalanmak için bağlantı havuzunu etkin kullanın.

## Test Aracı

Geçiş sonrası veritabanı işlevlerini test etmek için `test_pg_connection.py` scripti oluşturulmuştur. Bu script, temel veritabanı işlemlerini test eder ve sonuçları raporlar.

## Ek Kaynaklar

- [PostgreSQL Resmi Dokümantasyonu](https://www.postgresql.org/docs/)
- [SQLite'dan PostgreSQL'e Geçiş](https://wiki.postgresql.org/wiki/Converting_from_other_Databases_to_PostgreSQL) 