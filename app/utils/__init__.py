"""
# ============================================================================ #
# Dosya: __init__.py
# Yol: /Users/siyahkare/code/telegram-bot/app/utils/__init__.py
# İşlev: Utils modülü için başlatma dosyası.
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""

# Bu modülü aktif et
__all__ = ['setup_logger', 'handle_keyboard_input', 'print_banner', 'show_help']

# Kullanılan fonksiyonları içe aktar
try:
    from app.utils.logger_setup import setup_logger
    from app.utils.cli_interface import handle_keyboard_input, print_banner, show_help
except ImportError:
    # Doğrudan içe aktarma yapalım (göreceli import)
    from .logger_setup import setup_logger
    from .cli_interface import handle_keyboard_input, print_banner, show_help
