"""
# ============================================================================ #
# Dosya: __init__.py
# Yol: /Users/siyahkare/code/telegram-bot/app/db/__init__.py
# İşlev: Veritabanı modülü için başlatma dosyası.
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""

# Bu modülü aktif et
__all__ = ['UserDatabase', 'PgDatabase']

# Kullanılan sınıfları içe aktar
try:
    from app.db.user_db import UserDatabase
    from app.db.pg_db import PgDatabase
except ImportError:
    # Doğrudan içe aktarma yapalım (göreceli import)
    from .user_db import UserDatabase
    from .pg_db import PgDatabase
