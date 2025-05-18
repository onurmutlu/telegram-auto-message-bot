from telethon import TelegramClient, events
from .config import config
from .logger import logger

import asyncio

class Bot:
    def __init__(self):
        self.client = TelegramClient(
            'telegram_bot',
            config.API_ID,
            config.API_HASH
        )
        
    async def start(self):
        """Bot'u başlat"""
        try:
            await self.client.start(bot_token=config.BOT_TOKEN)
            logger.info("Bot başarıyla başlatıldı")
            await self.setup_handlers()
            await self.client.run_until_disconnected()
        except Exception as e:
            logger.error(f"Bot başlatılamadı: {str(e)}")
            raise

    async def setup_handlers(self):
        """Mesaj işleyicilerini kur"""
        @self.client.on(events.NewMessage(pattern='/start'))
        async def handle_start(event):
            await event.respond("Merhaba! Ben bir Telegram botuyum.")
            
        @self.client.on(events.NewMessage)
        async def handle_message(event):
            try:
                message = event.message
                logger.info(f"Yeni mesaj alındı: {message.text}")
                
                # Mesaj işleme mantığı buraya gelecek
                await event.respond("Mesajınız alındı!")
                
            except Exception as e:
                logger.error(f"Mesaj işleme hatası: {str(e)}")
                await event.respond("Üzgünüm, bir hata oluştu.")

    def run(self):
        """Bot'u çalıştır"""
        try:
            asyncio.run(self.start())
        except KeyboardInterrupt:
            logger.info("Bot kapatılıyor...")
            self.client.disconnect()
            logger.info("Bot başarıyla kapatıldı")

if __name__ == "__main__":
    bot = Bot()
    bot.run()
