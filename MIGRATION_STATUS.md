# Telegram Bot Klasör Yapısı Taşıma Durumu

Bu belge, eski klasör yapısından yeni modüler `/app` yapısına taşınan dosyaların durumunu göstermektedir.

## Genel Yapı

```
app/
├── api/            # FastAPI API 
├── config/         # Yapılandırma dosyaları
├── core/           # Çekirdek bileşenler
│   ├── tdlib/      # TDLib entegrasyonu
│   ├── tdlib-db/   # TDLib veritabanı
│   └── unified/    # Birleşik çalıştırma sistemi
├── data/           # Veri dosyaları (JSON, Config vb.)
├── db/             # Veritabanı bağlantıları ve migrationlar
├── handlers/       # Telegram mesaj işleyicileri
├── maintenance/    # Bakım ve düzeltme betikleri
├── models/         # SQLModel modelleri
├── scripts/        # Yardımcı scriptler
├── services/       # Bot servisleri
│   ├── analytics/  # Analitik servisleri
│   └── messaging/  # Mesajlaşma servisleri
├── sessions/       # Telegram oturum dosyaları
├── tests/          # Test dosyaları
├── tools/          # Geliştirme araçları
├── utils/          # Yardımcı fonksiyonlar
│   └── dashboard/  # Dashboard araçları
├── client.py       # Client entry point
├── scheduler.py    # Zamanlayıcı entry point
├── integration_test.py # Entegrasyon testleri
├── main.py         # Ana entry point
├── message_service.py  # Mesaj servisi
├── run_bot.py      # Bot çalıştırıcı
└── unified_runner.py # Birleşik çalıştırıcı
```

## Taşınan Dosyalar

### Servisler

| Eski Konum | Yeni Konum | Durum |
|------------|------------|-------|
| `bot/services/base_service.py` | `app/services/base_service.py` | ✅ |
| `bot/services/announcement_service.py` | `app/services/messaging/announcement_service.py` | ✅ |
| `bot/services/reply_service.py` | `app/services/messaging/reply_service.py` | ✅ |
| `bot/services/dm_service.py` | `app/services/messaging/dm_service.py` | ✅ |
| `bot/services/invite_service.py` | `app/services/messaging/invite_service.py` | ✅ |
| `bot/services/promo_service.py` | `app/services/messaging/promo_service.py` | ✅ |
| `bot/services/analytics_service.py` | `app/services/analytics/analytics_service.py` | ✅ |
| `bot/services/datamining_service.py` | `app/services/analytics/datamining_service.py` | ✅ |
| `bot/services/error_service.py` | `app/services/analytics/error_service.py` | ✅ |
| `bot/services/gpt_service.py` | `app/services/gpt_service.py` | ✅ |
| `bot/services/event_service.py` | `app/services/event_service.py` | ✅ |
| `bot/services/group_service.py` | `app/services/group_service.py` | ✅ |
| `bot/services/service_factory.py` | `app/services/service_factory.py` | ✅ |
| `bot/services/user_service.py` | `app/services/user_service.py` | ✅ |
| `bot/services/message_service.py` | `app/services/message_service.py` | ✅ |
| `bot/services/service_manager.py` | `app/services/service_manager.py` | ✅ |
| `src/services/user_service.py` | `app/services/user_service.py` | ✅ |

### Bakım Araçları

| Eski Konum | Yeni Konum | Durum |
|------------|------------|-------|
| `fix_database.py` | `app/maintenance/fix_database.py` | ✅ |
| `fix_db_locks.py` | `app/maintenance/fix_db_locks.py` | ✅ |
| `fix_user_storage.py` | `app/maintenance/fix_user_storage.py` | ✅ |
| `fix_db_tables.py` | `app/maintenance/fix_db_tables.py` | ✅ |
| `fix_group_tables.py` | `app/maintenance/fix_group_tables.py` | ✅ |
| `fix_mining_tables.py` | `app/maintenance/fix_mining_tables.py` | ✅ |
| `fix_user_ids.py` | `app/maintenance/fix_user_ids.py` | ✅ |
| `fix_permissions.py` | `app/maintenance/fix_permissions.py` | ✅ |
| `fix_all_tables.py` | `app/maintenance/fix_all_tables.py` | ✅ |
| `fix_all_permissions.py` | `app/maintenance/fix_all_permissions.py` | ✅ |
| `fix_settings_and_backup.py` | `app/maintenance/fix_settings_and_backup.py` | ✅ |
| `fix_telethon_session.py` | `app/maintenance/fix_telethon_session.py` | ✅ |
| `fix_db_locks_auto.py` | `app/maintenance/fix_db_locks_auto.py` | ✅ |
| `fix_db_ownership.py` | `app/maintenance/fix_db_ownership.py` | ✅ |
| `fix_group_members_constraint.py` | `app/maintenance/fix_group_members_constraint.py` | ✅ |
| `fix_groups_table.py` | `app/maintenance/fix_groups_table.py` | ✅ |
| `fix_pg_specific_tables.py` | `app/maintenance/fix_pg_specific_tables.py` | ✅ |
| `fix_specific_table_permissions.py` | `app/maintenance/fix_specific_table_permissions.py` | ✅ |
| `fix_telethon_session_auto.py` | `app/maintenance/fix_telethon_session_auto.py` | ✅ |
| `fix_user_invites.py` | `app/maintenance/fix_user_invites.py` | ✅ |
| `fix_yedekleme.py` | `app/maintenance/fix_yedekleme.py` | ✅ |
| `bot_maintenance.py` | `app/maintenance/bot_maintenance.py` | ✅ |
| `optimize_database.py` | `app/maintenance/optimize_database.py` | ✅ |
| `create_missing_tables.py` | `app/maintenance/create_missing_tables.py` | ✅ |
| `grant_privileges.py` | `app/maintenance/grant_privileges.py` | ✅ |
| `manual_migration.py` | `app/maintenance/manual_migration.py` | ✅ |
| `run_migration.py` | `app/maintenance/run_migration.py` | ✅ |
| `check_database_runner.py` | `app/maintenance/check_database_runner.py` | ✅ |
| `count_users.py` | `app/maintenance/count_users.py` | ✅ |
| `update_user_activities.py` | `app/maintenance/update_user_activities.py` | ✅ |

### Telegram İşleyicileri (Handlers)

| Eski Konum | Yeni Konum | Durum |
|------------|------------|-------|
| `bot/handlers/group_handler.py` | `app/handlers/group_handler.py` | ✅ |
| `bot/handlers/invite_handler.py` | `app/handlers/invite_handler.py` | ✅ |
| `bot/handlers/message_handler.py` | `app/handlers/message_handler.py` | ✅ |
| `bot/handlers/user_handler.py` | `app/handlers/user_handler.py` | ✅ |
| `bot/handlers/handlers.py` | `app/handlers/handlers.py` | ✅ |

### Oturum Dosyaları

| Eski Konum | Yeni Konum | Durum |
|------------|------------|-------|
| `telegram_session.*` | `app/sessions/telegram_session.*` | ✅ |
| `telegram_session_new.*` | `app/sessions/telegram_session_new.*` | ✅ |
| `telegram_session_new_new.*` | `app/sessions/telegram_session_new_new.*` | ✅ |
| `telegram_session_new_new_new.*` | `app/sessions/telegram_session_new_new_new.*` | ✅ |
| `telegram_session_new_new_new_new.*` | `app/sessions/telegram_session_new_new_new_new.*` | ✅ |
| `telegram_session_new_new_new_new_new.*` | `app/sessions/telegram_session_new_new_new_new_new.*` | ✅ |

### Test Dosyaları

| Eski Konum | Yeni Konum | Durum |
|------------|------------|-------|
| `test_admin_groups.py` | `app/tests/test_admin_groups.py` | ✅ |
| `test_analytics_error.py` | `app/tests/test_analytics_error.py` | ✅ |
| `test_config_adapter.py` | `app/tests/test_config_adapter.py` | ✅ |
| `test_group_handler.py` | `app/tests/test_group_handler.py` | ✅ |
| `test_message.py` | `app/tests/test_message.py` | ✅ |
| `test_pg_connection.py` | `app/tests/test_pg_connection.py` | ✅ |
| `test_postgres.py` | `app/tests/test_postgres.py` | ✅ |
| `test_service_loader.py` | `app/tests/test_service_loader.py` | ✅ |
| `test_services.py` | `app/tests/test_services.py` | ✅ |
| `test_services_enhanced.py` | `app/tests/test_services_enhanced.py` | ✅ |
| `integration_test.py` | `app/integration_test.py` | ✅ |

### Veritabanı Dosyaları

| Eski Konum | Yeni Konum | Durum |
|------------|------------|-------|
| `database/user_db.py` | `app/db/user_db.py` | ✅ |
| `database/setup_db.py` | `app/db/setup_db.py` | ✅ |
| `database/db_connection.py` | `app/db/db_connection.py` | ✅ |
| `database/models.py` | `app/db/models.py` | ✅ |
| `database/schema.py` | `app/db/schema.py` | ✅ |
| `database/script.py` | `app/db/script.py` | ✅ |
| `database/sqlite_to_postgres.py` | `app/db/sqlite_to_postgres.py` | ✅ |
| `database/test-db.py` | `app/db/test-db.py` | ✅ |
| `database/pg_db.py` | `app/db/pg_db.py` | ✅ |
| `database/migrate_db.py` | `app/db/migrate_db.py` | ✅ |
| `database/migration.py` | `app/db/migration.py` | ✅ |
| `database/db.py` | `app/db/db.py` | ✅ |
| `database/__init__.py` | `app/db/__init__.py` | ✅ |

### Yapılandırma Dosyaları

| Eski Konum | Yeni Konum | Durum |
|------------|------------|-------|
| `config/config.py` | `app/config/config.py` | ✅ |
| `config/settings.py` | `app/config/settings.py` | ✅ |
| `config/__init__.py` | `app/config/__init__.py` | ✅ |
| `config_helper.py` | `app/config/config_helper.py` | ✅ |

### Yardımcı Araçlar ve Veri Dosyaları

| Eski Konum | Yeni Konum | Durum |
|------------|------------|-------|
| `utils/client_mode.py` | `app/utils/client_mode.py` | ✅ |
| `utils/monitor.py` | `app/utils/monitor.py` | ✅ |
| `utils/session_cleaner.py` | `app/utils/session_cleaner.py` | ✅ |
| `utils/thread_manager.py` | `app/utils/thread_manager.py` | ✅ |
| `utils/logger.py` | `app/utils/logger.py` | ✅ |
| `tools/setup_2fa.py` | `app/tools/setup_2fa.py` | ✅ |
| `tools/test_connection.py` | `app/tools/test_connection.py` | ✅ |
| `tools/minimal_bot.py` | `app/tools/minimal_bot.py` | ✅ |
| `tools/send_test_message.py` | `app/tools/send_test_message.py` | ✅ |
| `tools/create_session.py` | `app/tools/create_session.py` | ✅ |
| `tools/get_string_from_session.py` | `app/tools/get_string_from_session.py` | ✅ |
| `tools/migrate_handlers.py` | `app/tools/migrate_handlers.py` | ✅ |
| `tools/monitor_dashboard.py` | `app/tools/monitor_dashboard.py` | ✅ |
| `tools/bot_starter.py` | `app/tools/bot_starter.py` | ✅ |
| `tools/cleanup.py` | `app/tools/cleanup.py` | ✅ |
| `data/invites.json` | `app/data/invites.json` | ✅ |
| `data/promos.json` | `app/data/promos.json` | ✅ |
| `data/announcements.json` | `app/data/announcements.json` | ✅ |
| `data/campaigns.json` | `app/data/campaigns.json` | ✅ |
| `data/responses.json` | `app/data/responses.json` | ✅ |
| `data/messages.json` | `app/data/messages.json` | ✅ |
| `data/config.json` | `app/data/config.json` | ✅ |
| `data/users.db` | `app/data/users.db` | ✅ |
| `data/bot.db` | `app/data/bot.db` | ✅ |

### Çekirdek Dosyalar

| Eski Konum | Yeni Konum | Durum |
|------------|------------|-------|
| `bot/main.py` | `app/main.py` | ✅ |
| `bot/celery_app.py` | `app/core/celery_app.py` | ✅ |
| `bot/tasks.py` | `app/core/tasks.py` | ✅ |
| `bot/tdlib.py` | `app/core/tdlib/tdlib.py` | ✅ |
| `bot/tdlib_integration.py` | `app/core/tdlib/integration.py` | ✅ |
| `bot/tdlib_setup.py` | `app/core/tdlib/setup.py` | ✅ |
| `bot/message_bot.py` | `app/core/message_bot.py` | ✅ |
| `bot/service_starter.py` | `app/core/service_starter.py` | ✅ |
| `main.py` | `app/main.py` | ✅ |
| `message_service.py` | `app/message_service.py` | ✅ |
| `unified/main.py` | `app/core/unified/main.py` | ✅ |
| `unified/run.py` | `app/core/unified/run.py` | ✅ |
| `unified_runner.py` | `app/unified_runner.py` | ✅ |
| `run_bot.py` | `app/run_bot.py` | ✅ |

## Taşıma Durumu

| Dosya Türü | Toplam | Taşınmış | Tamamlanma |
|------------|--------|----------|------------|
| Servisler | 17 | 17 | %100 ✅ |
| Bakım Araçları | 30 | 30 | %100 ✅ |
| İşleyiciler | 5 | 5 | %100 ✅ |
| Oturum Dosyaları | 21 | 21 | %100 ✅ |
| Test Dosyaları | 11 | 11 | %100 ✅ |
| Veritabanı Dosyaları | 13 | 13 | %100 ✅ |
| Yapılandırma Dosyaları | 4 | 4 | %100 ✅ |
| Yardımcı Araçlar ve Veri Dosyaları | 25 | 25 | %100 ✅ |
| Çekirdek Dosyalar | 14 | 14 | %100 ✅ |
| **Toplam** | **140** | **140** | **%100 ✅** |

## Notlar

* Taşınan dosyaların import ifadeleri güncellendi (`bot.` -> `app.`)
* Dosya içindeki yol referansları güncellendi (`/bot/` -> `/app/`)
* Dosya adı referansları güncellendi (`bot.log` -> `app.log`, `bot.db` -> `app.db`)
* Celery yapılandırmasındaki görev yolları güncellendi (`bot.tasks` -> `app.core.tasks`)
* Logger yapılandırması güncellendi (`bot.` -> `app.`)
* Bakım araçları modernize edildi
* Tüm servisler BaseService sınıfını kullanacak şekilde standardize edildi
* Test dosyaları yeni klasör yapısına uygun hale getirildi
* Telegram işleyicileri kendi klasörüne taşındı
* Yardımcı fonksiyonlar ve dashboard araçları taşındı
* Veritabanı modülleri app/db klasörüne taşındı
* Yapılandırma (config) dosyaları app/config klasörüne taşındı
* Çekirdek bileşenler (TDLib, Celery, Unified vb.) yeni yapıya uygun şekilde düzenlendi
* Veri dosyaları (JSON ve DB) app/data klasörüne taşındı
* Klasör yapısı tamamen modernize edildi 🎉 