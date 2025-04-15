"""
# ============================================================================ #
# Dosya: __init__.py
# Yol: /Users/siyahkare/code/telegram-bot/config/__init__.py
# İşlev: Config modülü için paket başlatıcı.
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""

# Config sınıfını doğrudan dışa aktarır
from .settings import Config
from .config import get_default_config
from config.config import Config, get_default_config

# __all__ tanımlayarak import * kullanıldığında
# sadece bu belirtilen öğeler içe aktarılır
__all__ = ['Config', 'get_default_config']