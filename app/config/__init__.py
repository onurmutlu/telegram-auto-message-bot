"""
# ============================================================================ #
# Dosya: __init__.py
# Yol: /Users/siyahkare/code/telegram-bot/app/config/__init__.py
# İşlev: Config modülü için __init__ dosyası.
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""

# Bu modülü aktif et
__all__ = ['Config', 'get_default_config']

# Import modülüne göre düzeltildi
try:
    from app.config.config import Config, get_default_config
except ImportError:
    # Doğrudan içe aktarma yapalım (göreceli import)
    from .config import Config, get_default_config

"""
Telegram Bot - Konfigürasyon Paketi
"""
from app.config.bot_config import settings, get_setting, update_setting, update_env_file

# Dışa aktarılan modüller
__all__ = ["settings", "get_setting", "update_setting", "update_env_file"]