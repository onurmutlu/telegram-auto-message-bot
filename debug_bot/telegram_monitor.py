"""
# ============================================================================ #
# Dosya: telegram_monitor.py
# Yol: /Users/siyahkare/code/telegram-bot/debug_bot/telegram_monitor.py
# Amaç: Telegram botunun debug (hata ayıklama) ve izleme işlemlerini yönetir.
#
# Bu modül, ana Telegram botunun çalışma zamanı durumunu (çevrimiçi/çevrimdışı, hatalar, performans)
# sürekli olarak izler ve geliştiricilere anlık bildirimler göndererek botun sağlığını ve
# kararlılığını korumalarına yardımcı olur. Hata raporlarını toplar, analiz eder ve
# geliştiricilere ileterek hızlı müdahale imkanı sağlar.
#
# Geliştirme: 2025-04-01
# Versiyon: v3.4.0
# Lisans: MIT
#
# Telif Hakkı (c) 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır.
# ============================================================================ #
"""

import sys
import os

# Proje kök dizinini Python yoluna ekle
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import logging

# Logger tanımlaması
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
import asyncio
from main import TelegramBot  # Ana TelegramBot sınıfını direk main.py'den al
from database.user_db import UserDatabase
from dotenv import load_dotenv
from config.settings import Config
from debug_bot.handlers.debug_handlers import DebugHandlers
from debug_bot.error_handler import ErrorHandler
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackContext
from telegram.constants import ParseMode
from datetime import datetime

load_dotenv()

class TelegramMonitorBot:
    """
    Telegram İzleme Botu Sınıfı

    Bu sınıf, ana Telegram botunun durumunu izler, hata raporları oluşturur
    ve geliştiricilere bildirimler gönderir.
    """
    def __init__(self, token: str, developer_ids: list):
        """
        TelegramMonitorBot sınıfının yapılandırıcısı.

        Args:
            token (str): Telegram bot token'ı (.env dosyasından alınır).
            developer_ids (list): Hata mesajlarını alacak geliştirici ID'leri (.env dosyasından alınır).
        """
        self.token = os.getenv("MONITOR_BOT_TOKEN") or token
        self.developer_ids = [int(dev_id) for dev_id in os.getenv("DEVELOPER_IDS", developer_ids).split(",")]
        self.bot = Bot(token=self.token)
        self.application = ApplicationBuilder().token(self.token).build()
        self.developer_ids_str = os.getenv("DEVELOPER_IDS")
        self.developer_ids = [int(x) for x in self.developer_ids_str.split(",")] if self.developer_ids_str else []

        # Error Handler kurulumu
        self.error_handler = ErrorHandler(self)
        self.application.add_error_handler(self.error_handler)

        # Tüm handlerlar'da bu error_handler kullanılmalı
        self.handlers = DebugHandlers(self)

    async def send_message_to_devs(self, message: str):
        """
        Geliştiricilere mesaj gönderir.

        Args:
            message (str): Gönderilecek mesaj.
        """
        for dev_id in self.developer_ids:
            try:
                await self.bot.send_message(chat_id=dev_id, text=message)
            except Exception as e:
                logging.error(f"Geliştiriciye mesaj gönderme hatası ({dev_id}): {e}")

    def start(self, update: Update, context: CallbackContext):
        """
        /start komutunu işler ve kullanıcıyı debug_bot_users'a kaydeder.
        """
        try:
            # Kullanıcı bilgilerini al
            user = update.effective_user
            user_id = user.id
            username = user.username
            first_name = user.first_name
            last_name = user.last_name
            
            # Kullanıcıyı debug_bot_users tablosuna kaydet
            if self.db and hasattr(self.db, 'add_debug_user'):
                self.db.add_debug_user(
                    user_id=user_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    access_level='basic'
                )
            
            # Geliştirici/süper kullanıcı bilgilerini kontrol et
            is_developer = username in self.developers or str(user_id) in self.developer_ids
            is_superuser = username in self.superusers
            
            # Kullanıcı erişim seviyesine göre karşılama mesajını hazırla
            if is_developer:
                message = (
                    f"👨‍💻 *Geliştirici Modu Etkinleştirildi*\n\n"
                    f"Merhaba {first_name}! Bot yönetim sistemine hoş geldiniz.\n"
                    f"Geliştirici erişiminiz mevcut. Tüm Debug Bot fonksiyonlarına erişebilirsiniz.\n\n"
                    f"User ID: `{user_id}`\n"
                    f"Son erişim: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`"
                )
            elif is_superuser:
                message = (
                    f"🛡️ *Süper Kullanıcı Modu*\n\n"
                    f"Merhaba {first_name}! Bot yönetim paneline hoş geldiniz.\n"
                    f"Süper kullanıcı erişiminiz mevcut. Çoğu fonksiyona erişebilirsiniz.\n\n"
                    f"User ID: `{user_id}`"
                )
            else:
                message = (
                    f"👋 Merhaba {first_name}!\n\n"
                    f"Telegram Bot izleme sistemine hoş geldiniz. "
                    f"Bu bot, ana Telegram botunuzun durumunu takip etmenize yardımcı olur.\n\n"
                    f"User ID: `{user_id}`"
                )
            
            # Karşılama mesajını ve uygun klavye seçeneklerini gönder
            keyboard = self._get_user_keyboard(update.effective_user)
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            update.message.reply_text(
                message,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Start komutunu işlerken hata: {e}")
            self.error_handler(update, context)

    def _get_user_keyboard(self, user):
        """
        Kullanıcının erişim seviyesine göre klavye düğmelerini hazırlar.
        
        Args:
            user: Telegram kullanıcı nesnesi
            
        Returns:
            list: Düğme satırlarının listesi
        """
        # Temel düğmeler (herkes görebilir)
        keyboard = [
            [InlineKeyboardButton("📊 Bot Durumu", callback_data='status'),
             InlineKeyboardButton("ℹ️ Yardım", callback_data='help')]
        ]
        
        # Süper kullanıcılar için ekstra düğmeler
        if user.username in self.superusers:
            keyboard.append([
                InlineKeyboardButton("👥 Kullanıcılar", callback_data='users'),
                InlineKeyboardButton("📱 Gruplar", callback_data='groups')
            ])
        
        # Geliştiriciler için tam yönetim düğmeleri
        if user.username in self.developers or str(user.id) in self.developer_ids:
            keyboard.append([
                InlineKeyboardButton("⚙️ Ayarlar", callback_data='settings'),
                InlineKeyboardButton("🔄 Kontrol Paneli", callback_data='dashboard')
            ])
            keyboard.append([
                InlineKeyboardButton("📝 Loglar", callback_data='logs'),
                InlineKeyboardButton("🚨 Acil Durum", callback_data='emergency')
            ])
        
        return keyboard

async def main():
    """
    Asenkron ana fonksiyon.

    Bu fonksiyon, ana Telegram botunu ve izleme botunu başlatır,
    aralarında bağlantı kurar ve her iki botun da çalışmasını sağlar.
    """
    # Ana bot yapılandırması
    user_db = {}

    main_bot = TelegramBot(
        api_id=os.getenv("API_ID"),
        api_hash=os.getenv("API_HASH"),
        phone=os.getenv("PHONE_NUMBER"),
        group_links=os.getenv("GROUP_LINKS", "").split(","),
        user_db=user_db,
        config=Config().load_config(),  # Önce instance oluştur, sonra metodu çağır
        debug_mode=os.getenv("DEBUG_MODE", "False").lower() == "true"
    )
    
    # Debug/izleme botu yapılandırması
    monitor_bot = TelegramMonitorBot(
        token=os.getenv("MONITOR_BOT_TOKEN"),
        developer_ids=os.getenv("DEVELOPER_IDS")
    )
    
    # Ana bot ve debug bot arasında bağlantı kur
    main_bot.set_monitor_bot(monitor_bot)
    
    # Her iki botu da başlat
    bot_task = asyncio.create_task(main_bot.start())
    monitor_task = asyncio.create_task(monitor_bot.start())
    
    # Bekle
    await asyncio.gather(bot_task, monitor_task)

if __name__ == "__main__":
    asyncio.run(main())
