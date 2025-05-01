# Telegram Bot Bakım Araçları

Bu klasörde bulunan bakım araçları, Telegram botunun veritabanı işlemleri ve genel bakımı için kullanılır. Bu araçlar özellikle veritabanı yetki sorunlarını, kilitlenmeleri ve diğer sistem hatalarını çözmek için tasarlanmıştır.

## Bakım Araçları

### Ana Bakım Aracı

Tüm bakım işlemlerini tek bir yerden yönetmek için:

```bash
python bot_maintenance.py --all        # Tüm bakım işlemlerini çalıştırır
python bot_maintenance.py --minimal    # Sadece temel sorunları çözer
python bot_maintenance.py --test       # Veritabanı erişimini test eder
python bot_maintenance.py --check      # Sistem durumunu kontrol eder
python bot_maintenance.py --session    # Sadece Telethon session sorunlarını gider
python bot_maintenance.py --postgresql # Sadece PostgreSQL veritabanı sorunlarını gider
```

### Özel Bakım Araçları

Özel bakım araçları aşağıdaki gibidir:

1. **fix_telethon_session_auto.py**: Telethon session dosyalarının kilit sorunlarını düzeltir
   ```bash
   python fix_telethon_session_auto.py
   ```

2. **fix_pg_specific_tables.py**: PostgreSQL tablolarının kritik yetki sorunlarını düzeltir
   ```bash
   python fix_pg_specific_tables.py
   ```

3. **fix_db_locks_auto.py**: Veritabanı kilitlerini otomatik olarak temizler
   ```bash
   python fix_db_locks_auto.py
   ```

4. **fix_specific_table_permissions.py**: Sorunlu tablolar için özel yetkileri düzeltir
   ```bash
   python fix_specific_table_permissions.py
   ```

5. **fix_all_permissions.py**: Tüm tablolara tam erişim yetkisi verir
   ```bash
   python fix_all_permissions.py
   ```

6. **fix_yedekleme.py**: Veritabanı yedekleme işlemleri için gerekli izinleri düzenler
   ```bash
   python fix_yedekleme.py
   ```

7. **fix_db_ownership.py**: Veritabanı sahipliğini düzeltir
   ```bash
   python fix_db_ownership.py
   ```

8. **fix_settings_and_backup.py**: Settings tablosu ve yedekleme için özel düzeltmeler yapar
   ```bash
   python fix_settings_and_backup.py
   ```

9. **fix_group_tables.py**: Grup ilişki tablolarını düzeltir
   ```bash
   python fix_group_tables.py
   ```

10. **fix_groups_table.py**: Gruplar tablosunu düzeltir
   ```bash
   python fix_groups_table.py
   ```

11. **create_missing_tables.py**: Eksik tabloları oluşturur
   ```bash
   python create_missing_tables.py
   ```

## Sık Karşılaşılan Sorunlar ve Çözümleri

### Veritabanı Erişim Sorunları

- **"permission denied for table XXX"** hatası:
  ```bash
  python fix_pg_specific_tables.py
  ```

- **"database is locked"** hatası:
  ```bash
  python fix_telethon_session_auto.py
  ```

### PostgreSQL Yedekleme Sorunları

- **pg_dump erişim hatası**:
  ```bash
  python fix_pg_specific_tables.py
  ```
  Bu script, özellikle PostgreSQL veritabanındaki kritik tabloların yetkilerini tek tek düzeltir ve pg_dump işlemlerinin sorunsuz çalışmasını sağlar.

### Telethon Session Sorunları

- **Session dosyası kilitlendi** veya **erişim hatası**:
  ```bash
  python fix_telethon_session_auto.py
  ```
  Bu komut Telethon session dosyalarını tarayıp, kilitlenmeleri temizler ve dosya izinlerini düzeltir.

## Genel Bakım İşlemleri

Genel bakım ve veritabanı optimizasyonu için periyodik olarak (örneğin haftada bir) aşağıdaki komutu çalıştırmanız önerilir:

```bash
python bot_maintenance.py --minimal
```

Eğer sadece PostgreSQL veritabanı sorunlarını çözmek istiyorsanız:

```bash
python bot_maintenance.py --postgresql
```

Eğer sadece Telethon session sorunlarını çözmek istiyorsanız:

```bash
python bot_maintenance.py --session
```

Sistem tam bir bakıma ihtiyaç duyduğunda ise:

```bash
python bot_maintenance.py --all
```

## Önemli Notlar

1. Bu bakım araçları bot çalışmazken kullanılmalıdır. İşlemlerden önce botu durdurun:
   ```bash
   pkill -f "python main.py"
   ```

2. Bakım işlemlerinden sonra botu yeniden başlatın:
   ```bash
   python main.py
   ```

3. Herhangi bir veritabanı işleminden önce mevcut veritabanını yedeklemek iyi bir uygulamadır:
   ```bash
   pg_dump -h localhost -U postgres -d telegram_bot > backup_$(date +%Y%m%d).sql
   ```

4. Bakım araçları superuser yetkisine ihtiyaç duyabilir. Gerekirse PostgreSQL kullanıcınıza superuser yetkisi verin:
   ```sql
   ALTER USER username WITH SUPERUSER;
   ```

5. **"database is locked"** hatası genellikle Telethon'un SQLite veritabanı dosyalarıyla ilgili kilitlenme sorunlarından kaynaklanır. Bu durumda özel olarak Telethon session düzeltme aracını kullanın:
   ```bash
   python fix_telethon_session_auto.py
   ```

6. PostgreSQL ile ilgili "permission denied" hataları için en etkili çözüm şudur:
   ```bash
   python fix_pg_specific_tables.py
   ``` 