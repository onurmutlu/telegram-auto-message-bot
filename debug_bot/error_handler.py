"""
# ============================================================================ #
# Dosya: error_handler.py
# Yol: /Users/siyahkare/code/telegram-bot/debug_bot/error_handler.py
# Açıklama: Telegram botu için merkezi hata işleme mekanizması.
#
# Bu modül, botun karşılaştığı hataları yakalar, loglar ve geliştiricilere bildirir.
# Hata ayıklama sürecini kolaylaştırır ve botun kararlılığını artırır.
#
# Geliştirme: 2025-04-01
# Versiyon: v3.4.0
# Lisans: MIT
#
# Telif Hakkı (c) 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır.
# ============================================================================ #
"""
import logging
import traceback
from telegram import Update
from telegram.ext import CallbackContext

class ErrorHandler:
    """
    Merkezi hata işleyici sınıfı.

    Bu sınıf, Telegram botunda meydana gelen hataları yakalar, loglar ve yönetir.
    """
    def __init__(self, bot):
        """
        ErrorHandler sınıfının yapılandırıcısı.

        Args:
            bot: Bot nesnesi.
        """
        self.bot = bot
        self.logger = logging.getLogger(__name__)

    def log_error(self, context: CallbackContext, update: Update = None):
        """
        Telegram güncellemelerinden kaynaklanan hataları loglar.

        Args:
            context (CallbackContext): Telegram içerik nesnesi.
            update (Update, optional): Telegram güncelleme nesnesi. Varsayılan olarak None.
        """
        self.logger.error(f"Exception while handling an update: {context.error}")
        trace = traceback.format_exception(None, context.error, context.error.__traceback__)
        self.logger.error("".join(trace))

        # Optionally send the error to the developer
        devs = self.bot.developer_ids  # Assuming developer_ids is defined in TelegramBot
        if devs:
            error_message = f"Exception while handling an update:\n\n{context.error}\n\n{''.join(trace)}"
            for dev_id in devs:
                context.bot.send_message(chat_id=dev_id, text=error_message)

    def log_error(self, error_type, error_msg, extra_data=None):
        """
        Hata logla ve monitör bota gönder.

        Args:
            error_type (str): Hata türü.
            error_msg (str): Hata mesajı.
            extra_data (Any, optional): Ekstra hata bilgisi. Varsayılan olarak None.
        """
        self.logger.error(f"{error_type}: {error_msg}")
        
        # Geliştirici mesajı oluştur
        dev_msg = f"ERROR: {error_type}\n{error_msg}"
        if extra_data:
            dev_msg += f"\nEkstra bilgi: {extra_data}"
        
        # Eğer monitor_bot bağlıysa mesajı gönder
        if hasattr(self.bot, 'send_debug_message'):
            self.bot.send_debug_message(dev_msg)

    def __call__(self, update: Update, context: CallbackContext):
        """
        Varsayılan hata işleyici.

        Args:
            update (Update): Telegram güncelleme nesnesi.
            context (CallbackContext): Telegram içerik nesnesi.
        """
        self.log_error(context, update)
