"""
Telegram Bot Bakım Modülleri

Bu paket, Telegram Bot Platform'un bakım ve düzeltme araçlarını içerir.
"""

# Veritabanı bakım araçları
from app.maintenance.database_maintenance import (
    fix_db_locks,
    fix_permissions,
    optimize_database,
    run_all_maintenance
)

# Veritabanı düzeltme araçları
from app.maintenance.fix_database import fix_database
from app.maintenance.fix_db_locks import fix_db_locks
from app.maintenance.fix_user_storage import fix_user_storage
from app.maintenance.fix_db_tables import fix_db_tables
from app.maintenance.fix_group_tables import fix_group_tables
from app.maintenance.fix_mining_tables import fix_mining_tables
from app.maintenance.fix_user_ids import fix_user_ids
from app.maintenance.fix_permissions import fix_permissions
from app.maintenance.fix_all_tables import fix_all_tables
from app.maintenance.fix_all_permissions import fix_all_permissions
from app.maintenance.fix_settings_and_backup import fix_settings_and_backup
from app.maintenance.fix_telethon_session import fix_telethon_session

# Tüm bakım araçlarını dışa aktar
__all__ = [
    # Veritabanı bakım araçları
    "fix_db_locks",
    "fix_permissions",
    "optimize_database",
    "run_all_maintenance",
    
    # Veritabanı düzeltme araçları
    "fix_database",
    "fix_user_storage",
    "fix_db_tables",
    "fix_group_tables",
    "fix_mining_tables",
    "fix_user_ids",
    "fix_all_tables",
    "fix_all_permissions",
    "fix_settings_and_backup",
    "fix_telethon_session"
] 