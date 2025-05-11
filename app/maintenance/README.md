# Telegram Bot Bakım Araçları

Bu dizin, Telegram Bot Platform'un bakım ve düzeltme araçlarını içerir.

## Kullanım

Bakım araçları, veritabanı şemasını düzeltmek, kilitlenme sorunlarını gidermek, sık karşılaşılan hataları çözmek ve performans iyileştirmeleri yapmak için kullanılır.

### Genel Bakım Araçları

```bash
# Veritabanı kilitlerini düzelt
python -m app.maintenance.fix_db_locks --verbose

# Veritabanı tablolarını onar
python -m app.maintenance.fix_database --all --verbose

# Kullanıcı depolama sorunlarını düzelt
python -m app.maintenance.fix_user_storage --verbose

# Telethon oturum sorunlarını düzelt
python -m app.maintenance.fix_telethon_session
```

### Tüm Bakım İşlemlerini Çalıştırma

Tüm bakım işlemlerini otomatik olarak çalıştırmak için:

```bash
python -m app.maintenance.database_maintenance --run-all
```

Bu komut, yaygın sorunları otomatik olarak tespit edip onaracaktır.

## Mevcut Araçlar

### Veritabanı Düzeltme Araçları

- `fix_database.py` - Veritabanı şemasını kontrol edip düzeltir
- `fix_db_locks.py` - PostgreSQL veritabanı kilitlerini temizler
- `fix_db_tables.py` - Veritabanı tablolarını onarır
- `fix_permissions.py` - Veritabanı tablolarının izinlerini düzeltir
- `fix_all_tables.py` - Tüm tabloları düzeltir
- `fix_all_permissions.py` - Tüm tablo izinlerini düzeltir

### Kullanıcı ve Grup Araçları

- `fix_user_storage.py` - Kullanıcı depolama sorunlarını düzeltir
- `fix_user_ids.py` - Bozuk kullanıcı ID'lerini düzeltir
- `fix_user_invites.py` - Kullanıcı davet kayıtlarını onarır
- `fix_group_tables.py` - Grup tablolarını düzeltir
- `fix_groups_table.py` - Ana grup tablosunu onarır
- `fix_group_members_constraint.py` - Grup üyeleri kısıtlamalarını düzeltir

### Diğer Araçlar

- `fix_telethon_session.py` - Telethon oturum dosyalarını onarır
- `fix_telethon_session_auto.py` - Otomatik oturum onarımı yapar
- `fix_mining_tables.py` - Madencilik verileriyle ilgili tabloları düzeltir
- `fix_settings_and_backup.py` - Ayarları ve yedekleri onarır
- `fix_yedekleme.py` - Yedekleme sistemini düzeltir

## Bakım İpuçları

1. Herhangi bir araç çalıştırılmadan önce veritabanının yedeklenmesi önerilir
2. Araçlar, sorunları otomatik olarak tespit edip onarmak için `--auto` parametresiyle çalıştırılabilir
3. Daha ayrıntılı çıktı için `--verbose` veya `-v` parametresini kullanın
4. Sorunları tespit etmek ancak herhangi bir değişiklik yapmamak için `--dry-run` parametresini kullanın
5. Sorunları daha agresif bir şekilde onarmak için `--force` parametresi kullanılabilir (dikkatli kullanın!) 